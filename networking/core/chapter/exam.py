from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Route
from wtforms.fields import IntegerField, RadioField, StringField
from wtforms.validators import DataRequired, Optional

from quirck.auth.model import User
from quirck.core.form import AceEditorField, QuirckForm
from quirck.web.template import TemplateResponse

from networking.core.chapter.base import BaseChapter, ChapterTask
from networking.core.chapter.form import BaseTaskForm, ParsedAttempt, RegexpForm
from networking.core.model import Attempt
from networking.core.util import scope_cached


class ExamShortForm(BaseTaskForm):
    value = StringField(label="", validators=[DataRequired()])

    async def parse(self) -> list[ParsedAttempt]:
        return [ParsedAttempt(task=self.__class__.__name__, is_correct=False)]


class ExamTextForm(BaseTaskForm):
    value = AceEditorField(label="", validators=[DataRequired()])

    async def parse(self) -> list[ParsedAttempt]:
        return [ParsedAttempt(task=self.__class__.__name__, is_correct=False)]


class ExamRegexpForm(RegexpForm):
    """Auto-checkable answer. Correctness is stored but never shown to the student."""


class ExamChoiceForm(BaseTaskForm):
    """Single-choice answer (radio buttons), auto-checked."""

    value = RadioField(label="", validators=[DataRequired()], choices=[])
    choices: list[tuple[str, str]] = []
    answer: str = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value.choices = self.choices

    async def parse(self) -> list[ParsedAttempt]:
        return [
            ParsedAttempt(
                task=self.__class__.__name__,
                is_correct=self.value.data == self.answer,
            )
        ]


class ExamPollForm(BaseTaskForm):
    """Single-choice answer, not graded (oral exam question)."""

    value = RadioField(label="", validators=[Optional()], choices=[])
    choices: list[tuple[str, str]] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value.choices = self.choices

    async def parse(self) -> list[ParsedAttempt]:
        return [ParsedAttempt(task=self.__class__.__name__, is_correct=False)]


class ExamFieldsForm(BaseTaskForm):
    """Several sub-answers in one question, one input (or textarea) per sub-answer.

    If no checkers are supplied the question is checked manually. If every sub-field
    has a checker the question is **auto-checked** with partial credit.
    """

    sub_keys: list[str] = []
    checkers: dict[str, Callable[[str], bool]] = {}
    max_points: Decimal = Decimal(0)

    async def parse(self) -> list[ParsedAttempt]:
        if not self.checkers:
            return [ParsedAttempt(task=self.__class__.__name__, is_correct=False)]

        total = len(self.sub_keys)
        correct = sum(
            1
            for key in self.sub_keys
            if self.checkers[key]((self[key].data or "").strip())
        )
        points = (
            (self.max_points * correct / total).quantize(Decimal("0.01"))
            if total
            else Decimal(0)
        )
        return [
            ParsedAttempt(
                task=self.__class__.__name__,
                is_correct=correct == total,
                points=points,
            )
        ]


def make_fields_form(
    slug: str,
    fields: list[tuple[str, str, Callable[[str], bool] | None]],
    *,
    max_points: Decimal = Decimal(0),
    multiline: bool = False,
) -> type[ExamFieldsForm]:
    """Create an :class:`ExamFieldsForm` subclass with one field per sub-answer.

    ``fields`` is a list of ``(key, label, checker | None)`` tuples. Pass ``None`` for
    every checker to make the question manual; pass a ``Callable[[str], bool]`` for each
    to make it auto-checked. ``multiline`` switches the inputs to rich editors.
    """
    field_cls = AceEditorField if multiline else StringField
    checkers = {key: checker for key, _, checker in fields if checker is not None}
    attrs: dict[str, Any] = {
        "sub_keys": [key for key, _, _ in fields],
        "checkers": checkers,
        "max_points": max_points,
    }
    for key, label, _ in fields:
        attrs[key] = field_cls(label=label, validators=[Optional()])
    return type(slug, (ExamFieldsForm,), attrs)


class ExamSubnetForm(BaseTaskForm):
    """Multi-field question scored holistically by a single ``scorer`` callable."""

    sub_keys: list[str] = []
    scorer: Callable[[dict[str, str]], Decimal] | None = None
    max_points: Decimal = Decimal(0)

    async def parse(self) -> list[ParsedAttempt]:
        values = {key: (self[key].data or "").strip() for key in self.sub_keys}
        points = self.scorer(values) if self.scorer is not None else Decimal(0)
        points = points.quantize(Decimal("0.01"))
        return [
            ParsedAttempt(
                task=self.__class__.__name__,
                is_correct=points == self.max_points,
                points=points,
            )
        ]


def make_subnet_form(
    slug: str,
    fields: list[tuple[str, str]],
    scorer: Callable[[dict[str, str]], Decimal],
    max_points: Decimal,
) -> type[ExamSubnetForm]:
    """Create an :class:`ExamSubnetForm` subclass; ``fields`` is ``[(key, label)]``."""
    attrs: dict[str, Any] = {
        "sub_keys": [key for key, _ in fields],
        "scorer": staticmethod(scorer),
        "max_points": max_points,
    }
    for key, label in fields:
        attrs[key] = StringField(label=label, validators=[Optional()])
    return type(slug, (ExamSubnetForm,), attrs)


class GradeForm(QuirckForm):
    user_id = IntegerField(validators=[DataRequired()])
    points = StringField(validators=[Optional()])


@dataclass
class RenderedQuestion:
    prompt: str  # HTML supported
    form_class: type[BaseTaskForm]
    teacher_note: str = ""
    field_labels: dict[str, str] = field(default_factory=dict)


@dataclass
class ExamQuestion:
    """Static metadata for one exam question. Per-user prompt/form live in the variant."""

    slug: str
    name: str
    points: Decimal
    manual: bool = True

    @property
    def label(self) -> str:
        return self.name or self.slug


class ExamChapter(BaseChapter[Any]):
    slug = "exam"
    need_report = False
    deadline = None

    name: str
    start: datetime
    end: datetime
    results_visible: bool
    questions: list[ExamQuestion]
    variant_factory: Callable[[int], Any]

    def __init__(
        self,
        *,
        name: str,
        start: datetime,
        end: datetime,
        results_visible: bool,
        questions: list[ExamQuestion],
        variant_factory: Callable[[int], Any],
    ):
        self.name = name
        self.start = start
        self.end = end
        self.results_visible = results_visible
        self.questions = questions
        self.variant_factory = variant_factory
        self.tasks = [
            ChapterTask(question.slug, question.label, question.points)
            for question in questions
        ]

        self.routes = [
            Route("/", self.page, name="page", methods=["GET", "POST"]),
            Route("/grade", self.grade_index, name="grade_index", methods=["GET"]),
            Route("/grade/{task}", self.grade_task, name="grade_task", methods=["GET"]),
            Route(
                "/grade/{task}/save",
                self.grade_save,
                name="grade_save",
                methods=["POST"],
            ),
        ]

    @scope_cached("variant")
    async def get_variant(self, request: Request) -> Any:
        user: User = request.scope["user"]
        return self.variant_factory(user.id)

    # --- scoring -----------------------------------------------------------

    @staticmethod
    def _answer_text(data: dict[str, Any], labels: dict[str, str] | None = None) -> str:
        """Render a stored answer for display: a single free-text answer as-is, a
        multi-field answer as ``label: value`` lines (falling back to the raw key)."""
        if not data:
            return ""
        if list(data.keys()) == ["value"]:
            return data["value"] or ""
        labels = labels or {}
        return "\n".join(
            f"{labels.get(key, key)}: {value}" for key, value in data.items() if value
        )

    @staticmethod
    def _latest_per_task(attempts: Sequence[Attempt]) -> dict[str, Attempt]:
        latest: dict[str, Attempt] = {}
        for attempt in attempts:
            current = latest.get(attempt.task)
            if (
                current is None
                or attempt.submitted > current.submitted
                or (attempt.submitted == current.submitted and attempt.id > current.id)
            ):
                latest[attempt.task] = attempt
        return latest

    def question_score(self, question: ExamQuestion, last: Attempt | None) -> Decimal:
        # The latest answer wins (no max-over-attempts), so a re-submission or a
        # manually-lowered grade is not inflated by an earlier auto-correct attempt.
        if last is None:
            return Decimal(0)
        if last.points is not None:
            return last.points
        if last.is_correct:
            return question.points
        return Decimal(0)

    def calculate_test_points(self, attempts: Sequence[Attempt]) -> Decimal:
        exam_attempts = [a for a in attempts if a.chapter == self.slug]
        latest = self._latest_per_task(exam_attempts)
        return sum(
            (self.question_score(q, latest.get(q.slug)) for q in self.questions),
            Decimal(0),
        )

    async def page(self, request: Request) -> Response:
        user: User = request.scope["user"]
        session: AsyncSession = request.scope["db"]

        now = datetime.now(timezone.utc)
        if now < self.start and not user.is_admin:
            raise HTTPException(404)

        submittable = self.start <= now <= self.end
        variant = await self.get_variant(request)
        attempts = await self.get_attempts(request)
        latest = self._latest_per_task(attempts)

        items: list[dict[str, Any]] = []
        for question in self.questions:
            rendered: RenderedQuestion = variant.rendered[question.slug]
            last = latest.get(question.slug)
            form = await rendered.form_class.from_formdata(
                request, prefix=question.slug, data=last.data if last else None
            )

            if submittable and form.submit.data:
                if await form.validate_on_submit():
                    form_data = {
                        key: value
                        for key, value in form.data.items()
                        if key not in ["submit", "csrf_token"]
                    }
                    session.add_all(
                        [
                            Attempt(
                                user_id=user.id,
                                chapter=self.slug,
                                task=parsed.task,
                                data=form_data,
                                is_correct=parsed.is_correct,
                                points=parsed.points,
                            )
                            for parsed in await form.parse()
                        ]
                    )

                    return RedirectResponse(
                        f"{request.url_for('networking:exam:page')}#{question.slug}",
                        status_code=303,
                    )

            items.append(
                {
                    "question": question,
                    "prompt": rendered.prompt,
                    "form": form,
                    "answered": last is not None,
                    "answer": self._answer_text(last.data, rendered.field_labels)
                    if last
                    else "",
                    "score": self.question_score(question, last)
                    if self.results_visible
                    else None,
                }
            )

        return TemplateResponse(
            request,
            "exam.html",
            {
                "exam": self,
                "items": items,
                "submittable": submittable,
                "ended": now > self.end,
                "results_visible": self.results_visible,
            },
        )

    @staticmethod
    def _require_admin(request: Request) -> None:
        user: User = request.scope["user"]
        if not user.is_admin:
            raise HTTPException(403)

    async def grade_index(self, request: Request) -> Response:
        self._require_admin(request)
        session: AsyncSession = request.scope["db"]

        latest = (
            select(
                Attempt.task,
                Attempt.points,
            )
            .distinct(Attempt.user_id, Attempt.task)
            .where(Attempt.chapter == self.slug)
            .order_by(
                Attempt.user_id,
                Attempt.task,
                Attempt.submitted.desc(),
                Attempt.id.desc(),
            )
            .subquery()
        )
        counts = (
            await session.execute(
                select(
                    latest.c.task,
                    func.count().label("answered"),
                    func.count(latest.c.points).label("graded"),
                ).group_by(latest.c.task)
            )
        ).all()
        stats = {row.task: row for row in counts}

        rows = [
            {
                "question": question,
                "answered": stats[question.slug].answered
                if question.slug in stats
                else 0,
                "graded": stats[question.slug].graded
                if question.slug in stats
                else 0,
            }
            for question in self.questions
        ]

        return TemplateResponse(
            request, "exam_grade_index.html", {"exam": self, "rows": rows}
        )

    async def grade_task(self, request: Request) -> Response:
        self._require_admin(request)
        task = request.path_params["task"]
        question = next((q for q in self.questions if q.slug == task), None)
        if question is None:
            raise HTTPException(404)

        session: AsyncSession = request.scope["db"]
        latest = (
            await session.scalars(
                select(Attempt)
                .distinct(Attempt.user_id)
                .where(Attempt.chapter == self.slug)
                .where(Attempt.task == task)
                .order_by(
                    Attempt.user_id,
                    Attempt.submitted.desc(),
                    Attempt.id.desc(),
                )
                .options(joinedload(Attempt.user))
            )
        ).all()

        items = []
        for attempt in sorted(latest, key=lambda a: a.user_id):
            rendered: RenderedQuestion = self.variant_factory(attempt.user_id).rendered[
                task
            ]
            prefill = (
                attempt.points
                if attempt.points is not None
                else (question.points if attempt.is_correct else Decimal(0))
            )
            items.append(
                {
                    "attempt": attempt,
                    "answer": self._answer_text(attempt.data, rendered.field_labels),
                    "points": attempt.points,
                    "prefill": prefill,
                    "is_correct": attempt.is_correct,
                    "teacher_note": rendered.teacher_note,
                }
            )

        return TemplateResponse(
            request,
            "exam_grade_task.html",
            {
                "exam": self,
                "question": question,
                "items": items,
                "grade_form": GradeForm(request),
            },
        )

    async def grade_save(self, request: Request) -> Response:
        self._require_admin(request)
        task = request.path_params["task"]

        form = await GradeForm.from_formdata(request)
        if not await form.validate_on_submit():
            return JSONResponse({"ok": False, "error": "invalid"}, status_code=400)

        session: AsyncSession = request.scope["db"]
        attempt = (
            await session.scalars(
                select(Attempt)
                .where(Attempt.chapter == self.slug)
                .where(Attempt.task == task)
                .where(Attempt.user_id == form.user_id.data)
                .order_by(Attempt.submitted.desc())
            )
        ).first()

        if attempt is None:
            return JSONResponse({"ok": False, "error": "no_attempt"}, status_code=404)

        raw = (form.points.data or "").strip().replace(",", ".")
        if raw == "":
            attempt.points = None
        else:
            try:
                attempt.points = Decimal(raw)
            except InvalidOperation:
                return JSONResponse(
                    {"ok": False, "error": "bad_points"}, status_code=400
                )

        return JSONResponse({"ok": True, "points": raw})


__all__ = [
    "ExamChapter",
    "ExamQuestion",
    "RenderedQuestion",
    "ExamShortForm",
    "ExamTextForm",
    "ExamRegexpForm",
    "ExamChoiceForm",
    "ExamPollForm",
    "ExamFieldsForm",
    "make_fields_form",
    "ExamSubnetForm",
    "make_subnet_form",
]
