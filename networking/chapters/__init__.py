from networking.chapters.ip import IPChapter
from networking.core.chapter import BaseChapter

chapters: list[BaseChapter] = [IPChapter()]

__all__ = ["chapters"]
