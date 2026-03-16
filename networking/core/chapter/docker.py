from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Route

from quirck.auth.model import User
from quirck.box.docker import launch, lock_meta, stop
from quirck.box.exception import DockerConflict
from quirck.box.meta import Deployment

from networking.core.chapter.base import BaseChapter


class DockerTaskProtocol(Protocol):
    deployment: Deployment


class DockerMixin(BaseChapter[DockerTaskProtocol]):
    def __init__(self):
        super().__init__()
        self.routes += [
            Route("/launch", self.launch, name="launch", methods=["POST"]),
            Route("/stop", self.stop, name="stop", methods=["POST"]),
        ]
    
    async def launch(self, request: Request) -> Response:
        session: AsyncSession = request.scope["db"]
        user: User = request.scope["user"]

        if self.private and not user.is_admin:
            raise HTTPException(403, "Доступ запрещён")

        variant = await self.get_variant(request)

        try:
            meta = await lock_meta(session, user.id, self.slug)
            task = BackgroundTask(launch, session, meta, variant.deployment)
        except DockerConflict:
            task = None

        return RedirectResponse(
            request.url_for(f"networking:{self.slug}:page"), status_code=303,
            background=task
        )

    async def stop(self, request: Request) -> Response:
        session: AsyncSession = request.scope["db"]
        user: User = request.scope["user"]

        if self.private and not user.is_admin:
            raise HTTPException(403, "Доступ запрещён")
    
        try:
            meta = await lock_meta(session, user.id, self.slug)
            task = BackgroundTask(stop, session, user.id)
        except DockerConflict:
            task = None

        meta = await lock_meta(session, user.id, self.slug)
        if meta.state == "READY":
            await meta.stop()

        return RedirectResponse(
            request.url_for(f"networking:{self.slug}:page"), status_code=303,
            background=task
        )


__all__ = ["DockerMixin"]
