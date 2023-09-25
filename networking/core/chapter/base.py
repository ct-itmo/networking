import itertools
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Generic, Sequence, TypeVar

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Mount, BaseRoute, Route

from quirck.auth.model import User
from quirck.web.template import TemplateResponse

from networking.core.form import ClearProgressForm, ReportForm
from networking.core.model import Attempt, Report
from networking.core.util import scope_cached

Variant = TypeVar("Variant")


@dataclass
class ChapterTask:
    slug: str
    name: str
    points: Decimal


@dataclass
class ChapterTaskResult:
    task: ChapterTask
    is_solved: bool = False
    score: Decimal | None = None


class ChapterResult:
    chapter: "BaseChapter"
    results: list[ChapterTaskResult]
    solved_tasks: int
    score: Decimal

    @property
    def total_tasks(self) -> int:
        return len(self.chapter.tasks)

    @property
    def total_score(self) -> Decimal:
        return sum((task.points for task in self.chapter.tasks), Decimal(0))

    @property
    def slug(self) -> str:
        return self.chapter.slug

    def __init__(self, chapter: "BaseChapter", results: list[ChapterTaskResult]):
        self.chapter = chapter
        self.results = results
        self.solved_tasks = sum(1 for result in results if result.is_solved)
        self.score = sum((result.score or Decimal(0) for result in results), Decimal(0))


class BaseChapter(Generic[Variant]):
    slug: str
    name: str
    author: str | None
    deadline: datetime | None
    hard_deadline: bool = False
    private: bool = False
    tasks: list[ChapterTask]

    routes: list[BaseRoute]

    def __init__(self):
        self.routes = [
            Route("/", self.chapter_page, name="page", methods=["GET", "POST"]),
            Route("/clear", self.clear_progress, name="clear", methods=["POST"])
        ]

    def get_mount(self):
        return Mount(
            path=f"/{self.slug}",
            routes=self.routes,
            name=self.slug
        )

    def calculate_task_score(self, task: ChapterTask, attempts: list[Attempt], with_debt: bool) -> ChapterTaskResult:
        is_solved = False
        score: Decimal | None = None

        for attempt in attempts:
            if attempt.is_correct:
                is_solved = True
            
            attempt_score: Decimal | None = None
            if attempt.points is not None:
                attempt_score = attempt.points
            elif attempt.is_correct:
                attempt_score = task.points
            
            if attempt_score is not None:
                if self.deadline is not None and attempt.submitted > self.deadline:
                    if self.hard_deadline:
                        continue
                
                    if not with_debt:
                        attempt_score *= Decimal('0.75')
                
                if score is None:
                    score = attempt_score
                else:
                    score = max(score, attempt_score)

        return ChapterTaskResult(task, is_solved, score)

    def calculate_score(self, attempts: Sequence[Attempt], with_debt: bool = False) -> ChapterResult:
        chapter_attempts = sorted((attempt for attempt in attempts if attempt.chapter == self.slug), key=lambda attempt: attempt.task)
        grouped_attempts = {key: list(value) for key, value in itertools.groupby(chapter_attempts, key=lambda attempt: attempt.task)}

        scores = [
            self.calculate_task_score(task, grouped_attempts.get(task.slug, []), with_debt)
            for task in self.tasks
        ]

        return ChapterResult(self, scores)

    async def get_variant(self, request: Request) -> Variant:
        raise NotImplementedError()

    @scope_cached("attempts")
    async def get_attempts(self, request: Request) -> Sequence[Attempt]:
        user: User = request.scope["user"]
        session: AsyncSession = request.scope["db"]
        attempts = (await session.scalars(
            select(Attempt)
                .where(Attempt.user_id == user.id)
                .where(Attempt.chapter == self.slug)
                .order_by(Attempt.task, Attempt.submitted.desc())
        )).all()

        return attempts

    async def chapter_page(self, request: Request, context: dict[str, Any] = {}) -> Response:
        session: AsyncSession = request.scope["db"]
        user: User = request.scope["user"]

        if self.private and not user.is_admin:
            raise HTTPException(403, "Доступ запрещён")

        attempts = await self.get_attempts(request)
        last_report = (await session.scalars(
            select(Report)
                .where(Report.user_id == user.id)
                .where(Report.chapter == self.slug)
                .order_by(Report.submitted.desc())
        )).first()

        report_form = await ReportForm.from_formdata(
            request,
            prefix="report",
            data={"report": last_report and last_report.text}
        )

        if report_form.submit.data:
            if await report_form.validate_on_submit():
                report = Report(
                    user_id=user.id,
                    chapter=self.slug,
                    text=report_form.report.data
                )
                session.add(report)

                return RedirectResponse(f"{request.url_for(f'networking:{self.slug}:page')}#report", status_code=303)

        chapter_result = self.calculate_score(attempts)

        context.update(
            report=report_form,
            variant=await self.get_variant(request),
            tasks={
                result.task.slug: result
                for result in chapter_result.results
            },
            chapter=chapter_result,
            clear_progress=ClearProgressForm(request, prefix="clear-progress"),
            last_report_time=last_report and last_report.submitted
        )

        return TemplateResponse(request, f"chapters/{self.slug}.html", context)

    async def clear_progress(self, request: Request) -> Response:
        form = await ClearProgressForm.from_formdata(request, prefix="clear-progress")

        if await form.validate_on_submit():
            user: User = request.scope["user"]
            session: AsyncSession = request.scope["db"]

            await session.execute(
                update(Attempt)
                    .where(Attempt.is_correct == True)
                    .where(Attempt.chapter == self.slug)
                    .where(Attempt.user_id == user.id)
                    .values(is_correct=False)
            )

        return RedirectResponse(request.url_for(f"networking:{self.slug}:page"), status_code=303)


__all__ = ["BaseChapter", "ChapterTaskResult"]
