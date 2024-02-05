import re
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from wtforms.fields import StringField
from wtforms.validators import DataRequired

from quirck.auth.model import User
from quirck.core.form import QuirckForm

from networking.core.chapter.base import BaseChapter
from networking.core.model import Attempt


@dataclass
class ParsedAttempt:
    task: str
    is_correct: bool


class BaseTaskForm(QuirckForm):
    async def parse(self) -> list[ParsedAttempt]:
        raise NotImplementedError(f"{self.__class__.__name__} does not implement parse()")

    @classmethod
    def make_task(cls, slug: str, **kwargs) -> type["BaseTaskForm"]:
        return type(slug, (cls, ), kwargs)


class SingleTaskForm(BaseTaskForm):
    async def check(self) -> bool:
        raise NotImplementedError(f"{self.__class__.__name__} does not implement check()")

    async def parse(self) -> list[ParsedAttempt]:
        return [ParsedAttempt(
            task=self.__class__.__name__,
            is_correct=await self.check()
        )]


class RegexpForm(SingleTaskForm):
    value = StringField(label="", validators=[DataRequired()])
    answer: re.Pattern

    async def check(self) -> bool:
        return self.answer.fullmatch(self.value.data.strip()) is not None


class FormTaskProtocol(Protocol):
    form_classes: list[type[BaseTaskForm]]


class FormMixin(BaseChapter[FormTaskProtocol]):
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

                    attempts = [
                        Attempt(
                            user_id=user.id,
                            chapter=self.slug,
                            task=attempt.task,
                            data=form_data,
                            is_correct=attempt.is_correct
                        )
                        for attempt in await form.parse()
                    ]

                    session.add_all(attempts)

                    if any(attempt.is_correct for attempt in attempts):
                        return RedirectResponse(f"{request.url_for(f'networking:{self.slug}:page')}#{name}", status_code=303)
                    else:
                        form.form_errors.append("Неправильный ответ")
            
            forms[name] = form

        context["forms"] = forms

        return await super().chapter_page(request, context)


__all__ = ["FormMixin", "BaseTaskForm", "RegexpForm"]
