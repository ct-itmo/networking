import itertools
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, PlainTextResponse, Response
from starlette.routing import Mount, Route

from quirck.auth.middleware import AuthenticationMiddleware
from quirck.auth.model import User
from quirck.core import s3
from quirck.web.template import TemplateResponse, template_env

from networking.chapters import chapters
from networking.core.chapter.base import ChapterResult
from networking.core.middleware import LoadMetaMiddleware
from networking.core.model import Attempt, Exam
from networking.core.config import SECRET_SEED, SCOREBOARD_TOKEN


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
        if not chapter.private
    ]

    overall_chapter_score = sum((chapter.score for chapter in user_chapters), Decimal(0))
    total_chapter_score = sum((chapter.total_score for chapter in user_chapters), Decimal(0))

    exam: Exam | None = user.exam  # type: ignore

    overall_score = overall_chapter_score if exam is None else exam.calculate_points(overall_chapter_score)

    return TemplateResponse(
        request,
        "main.html",
        {
            "chapters": user_chapters,
            "overall_chapter_score": overall_chapter_score,
            "total_chapter_score": total_chapter_score,
            "overall_score": overall_score
        }
    )


@dataclass
class UserScore:
    user: User
    chapters: list[ChapterResult]

    @property
    def score(self) -> Decimal:
        return sum((chapter.score for chapter in self.chapters), Decimal(0))


async def scoreboard_guest(request: Request) -> Response:
    if SCOREBOARD_TOKEN is None or request.query_params.get("token") != str(SCOREBOARD_TOKEN):
        raise HTTPException(403)

    return await scoreboard(request)


async def scoreboard_admin(request: Request) -> Response:
    user: User = request.scope["user"]
    if not user.is_admin:
        raise HTTPException(403)
    
    return await scoreboard(request)


async def scoreboard(request: Request) -> Response:
    session: AsyncSession = request.scope["db"]

    users = (await session.scalars(
        select(User).order_by(User.id).options(joinedload(
            User.exam  # type: ignore
        ))
    )).all()

    attempts = (await session.scalars(
        select(Attempt).order_by(Attempt.user_id, Attempt.chapter, Attempt.task, Attempt.submitted.desc())
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
            chapter.calculate_score(grouped_attempts.get(user.id, {}).get(chapter.slug, []))
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
        await s3.get_url(s3.S3_DEFAULT_BUCKET, "vpn", request.scope["user"].id, "config-linux.ovpn")
    )


async def vpn_win(request: Request) -> Response:
    return RedirectResponse(
        await s3.get_url(s3.S3_DEFAULT_BUCKET, "vpn", request.scope["user"].id, "config-win.ovpn")
    )


def get_user_mount():
    return Mount(
        path="/",
        routes=[
            Route("/", main_page, name="main"),
            Route("/scoreboard", scoreboard_admin, name="scoreboard"),
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
            Middleware(LoadMetaMiddleware)
        ],
        name="networking"
    )


def api_signature(request: Request) -> Response:
    if "message" in request.query_params and "key" in request.query_params:
        message = request.query_params["message"]
        key = request.query_params["key"]
        secret = str(SECRET_SEED)
        if key == sha256(f"{message}_{secret}".encode("utf-8")).hexdigest():
            sign = sha256(f"OK_{message}_{key}_{secret}".encode("utf-8")).hexdigest()
            return PlainTextResponse(sign)

    return PlainTextResponse("Bad key or message", status_code=400)


def get_mount():
    return Mount(
        path="/",
        routes=[
            Route("/scoreboard/guest", scoreboard_guest, name="scoreboard_guest"),
            Route("/api/signature", api_signature, name="signature"),
            get_user_mount(),
        ]
    )


__all__ = ["get_mount"]
