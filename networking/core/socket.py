import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
import uvicorn

from quirck.core import config
from quirck.db.middleware import DatabaseMiddleware

from networking.core.config import SOCKET_PATH
from networking.core.model import Attempt

logger = logging.getLogger(__name__)


async def add_attempt(request: Request) -> Response:
    user_id = request.query_params.get("user_id")
    chapter = request.query_params.get("chapter")
    task = request.query_params.get("task")

    if not user_id or not user_id.isdigit() or \
        not chapter or not chapter.isidentifier() or \
        not task or not task.isidentifier():
        return PlainTextResponse("Bad request", status_code=400)

    session: AsyncSession = request.scope["db"]
    try:
        attempt = Attempt(
            user_id=int(user_id),
            chapter=chapter,
            task=task,
            data={},
            is_correct=True
        )
        session.add(attempt)
        await session.commit()

        return PlainTextResponse("OK")
    except IntegrityError:
        return PlainTextResponse("User does not exist", status_code=404)
    except Exception as exc:
        logger.exception("Cannot add attempt")
        return PlainTextResponse("Failed", status_code=500)


def build_app() -> Starlette:
    return Starlette(
        debug=config.DEBUG,
        middleware=[
            Middleware(DatabaseMiddleware, url=config.DATABASE_URL, create_tables=True)
        ],
        routes=[
            Route("/done", add_attempt, methods=["POST"])
        ]
    )


if __name__ == "__main__":
    uvicorn.run(
        "networking.core.socket:build_app",
        factory=True,
        uds=SOCKET_PATH,
        reload=config.DEBUG
    )


__all__ = ["build_app"]
