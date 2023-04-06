import itertools
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Generic, Protocol, Sequence, TypeVar

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Mount, BaseRoute, Route

from quirck.auth.model import User
from quirck.core.form import BaseTaskForm
from quirck.box.docker import launch, lock_meta
from quirck.box.exception import DockerConflict
from quirck.box.meta import Deployment
from quirck.web.template import TemplateResponse

from networking.core.form import ClearProgressForm, ReportForm
from networking.core.model import Attempt, Report
from networking.core.util import scope_cached

Variant = TypeVar("Variant")
logger = logging.getLogger(__name__)


@dataclass
class ChapterTask:
    slug: str
    name: str
    points: Decimal


@dataclass
class ChapherTaskResult:
    task: ChapterTask
    is_solved: bool = False
    score: Decimal | None = None


class BaseChapter(Generic[Variant]):
    slug: str
    name: str
    deadline: datetime | None
    hard_deadline: bool = False
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

    def calculate_task_score(self, task: ChapterTask, attempts: list[Attempt]) -> ChapherTaskResult:
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
                
                    attempt_score *= Decimal('0.75')
                
                if score is None:
                    score = attempt_score
                else:
                    score = max(score, attempt_score)

        return ChapherTaskResult(task, is_solved, score)

    def calculate_score(self, attempts: Sequence[Attempt]) -> list[ChapherTaskResult]:
        chapter_attempts = sorted((attempt for attempt in attempts if attempt.chapter == self.slug), key=lambda attempt: attempt.task)
        grouped_attempts = {key: list(value) for key, value in itertools.groupby(chapter_attempts, key=lambda attempt: attempt.task)}

        return [
            self.calculate_task_score(task, grouped_attempts.get(task.slug, []))
            for task in self.tasks
        ]

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


        context.update(
            report=report_form,
            variant=await self.get_variant(request),
            chapter=self.slug,
            tasks={
                result.task.slug: result
                for result in self.calculate_score(attempts)
            },
            clear_progress=ClearProgressForm(request, prefix="clear-progress")
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


class DockerTaskProtocol(Protocol):
    deployment: Deployment


class DockerMixin(BaseChapter[DockerTaskProtocol]):
    def __init__(self):
        super().__init__()
        self.routes += [
            Route("/launch", self.launch, name="launch", methods=["POST"])
        ]
    
    async def launch(self, request: Request) -> Response:
        session: AsyncSession = request.scope["db"]
        user: User = request.scope["user"]

        variant = await self.get_variant(request)

        try:
            meta = await lock_meta(session, user.id, self.slug)
            task = BackgroundTask(launch, session, meta, user.id, variant.deployment)
        except DockerConflict:
            task = None

        return RedirectResponse(
            request.url_for(f"networking:{self.slug}:page"), status_code=303,
            background=task
        )


class FormTaskProtocol(Protocol):
    form_classes: list[type[BaseTaskForm]]


class FormMixin(BaseChapter[FormTaskProtocol]):
    def __init__(self):
        super().__init__()

    async def chapter_page(self, request: Request, context: dict[str, Any] = {}) -> Response:
        session: AsyncSession = request.scope["db"]
        user: User = request.scope["user"]

        variant = await self.get_variant(request)
        attempts = await self.get_attempts(request)

        forms = {}

        for form_class in variant.form_classes:
            name = form_class.__name__

            last_attempt = next(iter(attempt for attempt in attempts if attempt.task == name), None)
            form = await form_class.from_formdata(request, prefix=name, data=last_attempt and last_attempt.data)

            if form.submit.data:
                if await form.validate_on_submit():
                    form_data = {
                        key: value
                        for key, value in form.data.items()
                        if key not in ["submit", "csrf_token"]
                    }

                    is_correct = await form.check()

                    attempt = Attempt(
                        user_id=user.id,
                        chapter=self.slug,
                        task=name,
                        data=form_data,
                        is_correct=await form.check()
                    )
                    session.add(attempt)

                    if is_correct:
                        return RedirectResponse(f"{request.url_for(f'networking:{self.slug}:page')}#{name}", status_code=303)
                    else:
                        form.form_errors.append("Неправильный ответ")
            
            forms[name] = form

        context["forms"] = forms

        return await super().chapter_page(request, context)


__all__ = ["BaseChapter", "DockerMixin", "FormMixin"]
