from networking.chapters.dhcp import DHCPChapter
from networking.chapters.dhcpd import DHCPDChapter
from networking.chapters.dns import DNSChapter
from networking.chapters.firewall import FirewallChapter
from networking.chapters.ip import IPChapter
from networking.chapters.practice import PracticeChapter
from networking.core.chapter.base import BaseChapter

chapters: list[BaseChapter] = [IPChapter(), DHCPChapter(), DHCPDChapter(), DNSChapter(), FirewallChapter(), PracticeChapter()]

__all__ = ["chapters"]
