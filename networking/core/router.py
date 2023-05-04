import itertools
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Mount, Route

from quirck.auth.middleware import AuthenticationMiddleware
from quirck.auth.model import User
from quirck.core import config
from quirck.core.s3 import get_url
from quirck.web.template import TemplateResponse

from networking.chapters import chapters
from networking.core.chapter.base import ChapterResult
from networking.core.middleware import LoadDockerMetaMiddleware
from networking.core.model import Attempt


async def main_page(request: Request) -> Response:
    user: User = request.scope["user"]
    session: AsyncSession = request.scope["db"]

    attempts = (await session.scalars(
        select(Attempt)
            .where(Attempt.user_id == user.id)
            .order_by(Attempt.chapter, Attempt.task, Attempt.submitted.desc())
    )).all()

    user_chapters = [
        chapter.calculate_score([
            attempt for attempt in attempts
            if attempt.chapter == chapter.slug
        ])
        for chapter in chapters
    ]

    overall_score = sum((chapter.score for chapter in user_chapters), Decimal(0))
    total_score = sum((chapter.total_score for chapter in user_chapters), Decimal(0))

    return TemplateResponse(
        request,
        "main.html",
        {
            "chapters": user_chapters,
            "overall_score": overall_score,
            "total_score": total_score
        }
    )


@dataclass
class UserScore:
    user: User
    chapters: list[ChapterResult]

    @property
    def score(self) -> Decimal:
        return sum((chapter.score for chapter in self.chapters), Decimal(0))


async def scoreboard(request: Request) -> Response:
    user: User = request.scope["user"]
    if not user.is_admin:
        raise HTTPException(403)

    session: AsyncSession = request.scope["db"]

    users = (await session.scalars(
        select(User)
            .order_by(User.id)
    )).all()

    attempts = (await session.scalars(
        select(Attempt)
            .where(Attempt.user_id == user.id)
            .order_by(Attempt.user_id, Attempt.chapter, Attempt.task, Attempt.submitted.desc())
    )).all()

    grouped_attempts = {
        user_id: {
            chapter: list(chapter_attempts)
            for chapter, chapter_attempts in itertools.groupby(user_attempts, key=lambda attempt: attempt.chapter)
        }
        for user_id, user_attempts in itertools.groupby(attempts, key=lambda attempt: attempt.user_id)
    }

    users_with_chapters = [
        UserScore(user, [
            chapter.calculate_score(grouped_attempts[user.id][chapter.slug])
            for chapter in chapters
        ])
        for user in users
    ]

    return TemplateResponse(
        request,
        "scoreboard.html",
        {
            "chapters": chapters,
            "users": users_with_chapters
        }
    )


# TODO: common route for pages
async def setup_page(request: Request) -> Response:
    return TemplateResponse(request, "pages/setup.html")


# TODO: common route for files
async def vpn_linux(request: Request) -> Response:
    return RedirectResponse(
        await get_url(config.S3_DEFAULT_BUCKET, "vpn", request.scope["user"].id, "config-linux.ovpn")
    )


async def vpn_win(request: Request) -> Response:
    return RedirectResponse(
        await get_url(config.S3_DEFAULT_BUCKET, "vpn", request.scope["user"].id, "config-win.ovpn")
    )


def get_mount():
    return Mount(
        path="/",
        routes=[
            Route("/", main_page, name="main"),
            Route("/scoreboard", scoreboard, name="scoreboard"),
            Mount(
                "/vpn",
                routes=[
                    Route("/", setup_page, name="setup"),
                    Route("/win", vpn_win, name="win"),
                    Route("/linux", vpn_linux, name="linux")
                ],
                name="vpn"
            )
        ] + [
            chapter.get_mount()
            for chapter in chapters
        ],
        middleware=[
            Middleware(AuthenticationMiddleware),
            Middleware(LoadDockerMetaMiddleware)
        ],
        name="networking"
    )


__all__ = ["get_mount"]
