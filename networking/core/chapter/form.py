from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from quirck.auth.model import User
from quirck.core.form import BaseTaskForm

from networking.core.chapter.base import BaseChapter
from networking.core.model import Attempt
from networking.core.util import scope_cached


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


__all__ = ["FormMixin"]
