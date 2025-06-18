from datetime import datetime
from decimal import Decimal

from starlette.requests import Request

from networking.core import util
from networking.core.chapter.base import BaseChapter, ChapterTask


class PracticeVariant:
    ...


class PracticeChapter(BaseChapter[PracticeVariant]):
    slug = "practice"
    name = "Обжим витой пары"
    deadline = datetime(2025, 5, 24, 21, 0, 0)
    tasks = [
        ChapterTask("practice", "Практическое задание", Decimal(10))
    ]
    need_report = False

    @util.scope_cached("variant")
    async def get_variant(self, request: Request) -> PracticeVariant:
        return PracticeVariant()


__all__ = ["PracticeChapter"]
