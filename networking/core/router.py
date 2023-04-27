from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Mount, Route

from quirck.auth.middleware import AuthenticationMiddleware
from quirck.core import config
from quirck.core.s3 import get_url
from quirck.web.template import TemplateResponse

from networking.chapters import chapters
from networking.core.middleware import LoadDockerMetaMiddleware
from networking.core.chapter import BaseChapter, ChapterTaskResult, OverallResult, calculate_overall_result


async def main_page(request: Request) -> Response:
    scores: dict[BaseChapter, list[ChapterTaskResult]] = {}
    chapters_results: dict[BaseChapter, OverallResult] = {}
    for chapter in chapters:
        attempt = await chapter.get_attempts(request)
        scores[chapter] = chapter.calculate_score(attempt)
        chapters_results[chapter] = chapter.calculate_chapter_result(scores[chapter])

    overall_result = calculate_overall_result(chapters_results.values())
    
    return TemplateResponse(
        request,
        "pages/main.html",
        {
            "chapters": chapters,
            "scores": scores,
            "chapter_results": chapters_results,
            "overall_result": overall_result
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
