import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

import aiodocker
from aiodocker.containers import DockerContainer
from aiohttp import ClientTimeout
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from starlette.background import BackgroundTask
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Route

from quirck.auth.model import User
from quirck.box.docker import lock_meta, run_container
from quirck.box.exception import DockerConflict
from quirck.box.meta import ContainerMeta
from quirck.box.model import DockerMeta, DockerState

from networking.core.chapter.base import BaseChapter, Variant
from networking.core.model import Log

logger = logging.getLogger(__name__)

CHECK_TIMEOUT = ClientTimeout(
    total=30,
    connect=30,
    sock_read=30,
    sock_connect=30
)


def check_default_log_joiner(container_logs: dict[int, str]) -> str:
    return "\n".join(container_logs[i] for i in sorted(container_logs.keys()))


@dataclass
class Check:
    containers: list[ContainerMeta]
    # map from container number to file_path
    logs: dict[int, str]
    # Third argument is a variant itself
    # TODO: get rid of Any here
    check: Callable[[AsyncSession, DockerMeta, list[DockerContainer]], Awaitable[None]] | None = None
    logs_joiner: Callable[[dict[int, str]], str] = check_default_log_joiner


class CheckableTaskProtocol(Protocol):
    checks: dict[str, Check]


class CheckableMixin(BaseChapter[CheckableTaskProtocol]):
    def __init__(self):
        super().__init__()
        self.routes += [
            Route("/check", self.check, name="check", methods=["POST"])
        ]
    
    async def check(self, request: Request) -> Response:
        session: AsyncSession = request.scope["db"]
        user: User = request.scope["user"]

        if self.private and not user.is_admin:
            raise HTTPException(403, "Доступ запрещён")

        variant = await self.get_variant(request)

        form = await request.form()
        check = form.get("check")
        if not isinstance(check, str) or check not in variant.checks:
            return RedirectResponse(f"{request.url_for(f'networking:{self.slug}:page')}", status_code=303)

        try:
            meta = await lock_meta(session, user.id, self.slug, True)
            task = BackgroundTask(self.check_task, session, meta, check, variant)
        except DockerConflict:
            task = None

        return RedirectResponse(request.url_for(f"networking:{self.slug}:page"), status_code=303, background=task)

    async def check_task(self, session: AsyncSession, meta: DockerMeta, check_name: str, variant: CheckableTaskProtocol) -> None:
        check = variant.checks[check_name]
        containers = [await run_container(meta, container) for container in check.containers]

        async with aiodocker.Docker() as client:
            # TODO: get rid of monkey-patch (how?)
            for container in containers:
                container.docker = client

            try:
                await asyncio.gather(*[container.wait(timeout=25) for container in containers])
            except:
                # If got timeout, try to do something anyway
                logger.warning("Timed out when waiting for check %s", check_name)
                pass

            containers_logs: dict[int, str] = {}
            for log_from, log_path in check.logs.items():
                log_container = containers[log_from]
                content = await log_container.get_archive(log_path)

                log_content = ""
                for member in content.getmembers():
                    extracted = content.extractfile(member)
                    if extracted is None:
                        continue

                    try:
                        log_content += extracted.read().decode()
                        log_content += "\n\n"
                    except UnicodeDecodeError:
                        log_content += f"File {member.name} cannot be decoded\n\n"

                containers_logs[log_from] = log_content.strip()

            log = Log(
                user_id=meta.user_id,
                chapter=self.slug,
                check=check_name,
                text=check.logs_joiner(containers_logs),
            )

            session.add(log)

            if check.check is not None:
                await check.check(session, meta, containers)

            for container in containers:
                await container.delete(force=True)

            meta.state = DockerState.READY
            await session.commit()

    # No caching needed yet
    async def get_logs(self, request: Request) -> dict[str, Log]:
        user: User = request.scope["user"]
        session: AsyncSession = request.scope["db"]

        window = func.row_number().over(
            partition_by=(Log.chapter, Log.check),
            order_by=Log.created.desc(),
        ).label("row")

        subquery = select(Log, window).where(Log.user_id == user.id).alias("sq")
        log_entity = aliased(Log, subquery)

        logs = (await session.scalars(select(log_entity).where(subquery.c.row == 1))).all()

        return {log.check: log for log in logs}

    async def chapter_page(self, request: Request, context: dict[str, Any] = {}) -> Response:
        context["logs"] = await self.get_logs(request)
        return await super().chapter_page(request, context)


__all__ = ["CheckableMixin"]
