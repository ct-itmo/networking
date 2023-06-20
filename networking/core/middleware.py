import logging

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ASGIApp, Receive, Send, Scope

from quirck.auth.model import User

logger = logging.getLogger(__name__)


class LoadMetaMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            db: AsyncSession = scope["db"]
            user: User = scope["user"]

            await db.refresh(user, ["docker_meta", "exam"])

        return await self.app(scope, receive, send)


__all__ = ["LoadMetaMiddleware"]
