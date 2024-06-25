import re
import string
from datetime import datetime
from decimal import Decimal
from random import Random

from aiodocker.containers import DockerContainer
from netaddr import IPAddress, IPNetwork
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Secret
from starlette.requests import Request

from quirck.box.meta import Deployment, ContainerMeta, NetworkMeta
from quirck.box.model import DockerMeta
from quirck.core.config import config

from networking.core import util
from networking.core.chapter.base import BaseChapter, ChapterTask
from networking.core.chapter.check import Check, CheckableMixin
from networking.core.chapter.docker import DockerMixin
from networking.core.chapter.form import FormMixin, BaseTaskForm, RegexpForm
from networking.core.config import SECRET_SEED

DNS_REGEXP_IP = config("DNS_REGEXP_IP", cast=str)
DNS_REGEXP_SERVERS = config("DNS_REGEXP_SERVERS", cast=str)


class DNSVariant:
    deployment: Deployment
    form_classes: list[type[BaseTaskForm]]

    domain: str
    ip4: IPAddress
    ip6: IPAddress
    subdomain: str
    subip6: IPAddress

    async def check_dns(self, _session: AsyncSession, _meta: DockerMeta, _containers: list[DockerContainer]) -> None:
        # Empty, all points are passed from the bot
        ...

    def __init__(self, user_id: int):
        rnd = Random(f"{SECRET_SEED}-{user_id}-dns")

        self.domain = f"{''.join(rnd.choice(string.ascii_lowercase + string.digits) for _ in range(10))}.localnetwork"
        self.subdomain = "".join(rnd.choice(string.ascii_lowercase + string.digits) for _ in range(5))
        self.ip4 = util.generate_address(rnd, IPNetwork("10.52.1.128/25"))
        self.ip6, self.subip6 = util.generate_distinct(2, util.generate_address, rnd, IPNetwork("fd44:1337::/64"))

        self.deployment = Deployment(
            containers=[
                ContainerMeta.make_vpn(user_id, ["internal"]),
                ContainerMeta(
                    name="domain",
                    image="ct-itmo/labs-networking-nginx",
                    networks={"internal": None},
                    mem_limit=16 * 1024 * 1024,
                    environment={
                        "DOMAIN": self.domain,
                        "IP4": str(self.ip4),
                        "IP6": str(self.ip6)
                    }
                ),
                ContainerMeta(
                    name="subdomain",
                    image="ct-itmo/labs-networking-nginx",
                    networks={"internal": None},
                    mem_limit=16 * 1024 * 1024,
                    environment={
                        "DOMAIN": f"{self.subdomain}.{self.domain}",
                        "IP6": str(self.subip6)
                    }
                )
            ],
            networks=[
                NetworkMeta(name="internal")
            ]
        )

        self.form_classes = [
            RegexpForm.make_task("ip", answer=re.compile(DNS_REGEXP_IP, re.I)),
            RegexpForm.make_task("servers", answer=re.compile(DNS_REGEXP_SERVERS, re.I))
        ]

        self.checks = {
            "dns": Check([
                ContainerMeta(
                    name="bot",
                    image="ct-itmo/labs-networking-dns-bot",
                    networks={"internal": None},
                    ipv6_forwarding=False,
                    volumes=util.socket_volume(),
                    environment={
                        "DOMAIN": self.domain,
                        "SUBDOMAIN": f"{self.subdomain}.{self.domain}",
                        "IP4": str(self.ip4),
                        "IP6": str(self.ip6),
                        "SUBIP6": str(self.subip6),
                        "BOX_IP": "10.52.1.2"
                    }
                )
            ], { 0: "/out/dns.log" }, self.check_dns)
        }


class DNSChapter(CheckableMixin, DockerMixin, FormMixin, BaseChapter[DNSVariant]):
    slug = "dns"
    name = "Протокол DNS"
    deadline = datetime(2024, 4, 26, 21, 0, 0)
    tasks = [
        ChapterTask("ip", "IP-адрес", Decimal(1)),
        ChapterTask("servers", "Список серверов", Decimal(2)),
        ChapterTask("recursive", "Рекурсивный сервер", Decimal(2)),
        ChapterTask("authoritative", "Авторитетный сервер", Decimal(2)),
        ChapterTask("mail", "Почта", Decimal(1)),
        ChapterTask("subdomain", "Поддомен", Decimal(2)),
        ChapterTask("transfer", "Трансфер", Decimal(2))
    ]

    @util.scope_cached("variant")
    async def get_variant(self, request: Request) -> DNSVariant:
        user_id: int = request.scope["user"].id
        return DNSVariant(user_id)


__all__ = ["DNSChapter"]
