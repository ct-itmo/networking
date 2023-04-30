from networking.chapters.dhcp import DHCPChapter
from networking.chapters.ip import IPChapter
from networking.core.chapter.base import BaseChapter

chapters: list[BaseChapter] = [IPChapter(), DHCPChapter()]

__all__ = ["chapters"]
