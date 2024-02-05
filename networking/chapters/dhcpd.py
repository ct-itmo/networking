import re
from datetime import datetime
from decimal import Decimal
from random import Random

from aiodocker.containers import DockerContainer
from aiodocker.exceptions import DockerError
from netaddr import IPNetwork, AddrFormatError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from quirck.box.meta import Deployment, ContainerMeta, NetworkMeta
from quirck.box.model import DockerMeta

from networking.core import util
from networking.core.chapter.base import BaseChapter, ChapterTask
from networking.core.chapter.check import Check, CheckableMixin
from networking.core.chapter.docker import DockerMixin
from networking.core.chapter.form import FormMixin, BaseTaskForm, RegexpForm
from networking.core.config import SECRET_SEED
from networking.core.model import Attempt


class DHCPDVariant:
    deployment: Deployment
    form_classes: list[type[BaseTaskForm]]
    checks: dict[str, Check]

    ip4_net: IPNetwork
    ip6_net: IPNetwork

    async def check_dhcpd(self, session: AsyncSession, meta: DockerMeta, containers: list[DockerContainer]) -> None:
        container, = containers

        try:
            tar = await container.get_archive("/out/addresses")
        except DockerError:
            return

        extracted = tar.extractfile("addresses")
        if extracted is None:
            return
            
        try:
            addresses = extracted.read().decode().split()
        except UnicodeDecodeError:
            return
        
        extracted.close()

        for address in addresses:
            try:
                ip = IPNetwork(address)
            except AddrFormatError:
                continue

            if ip == self.ip4_net:
                attempt = Attempt(
                    user_id=meta.user_id,
                    chapter=DHCPDChapter.slug,
                    task="ip4",
                    data={},
                    is_correct=True
                )
                session.add(attempt)

            if ip == self.ip6_net:
                attempt = Attempt(
                    user_id=meta.user_id,
                    chapter=DHCPDChapter.slug,
                    task="ip6",
                    data={},
                    is_correct=True
                )
                session.add(attempt)
        
        await session.commit()

    def __init__(self, user_id: int):
        rnd = Random(f"{SECRET_SEED}-{user_id}-dhcpd")

        self.ip4_net = util.generate_subnet(rnd, IPNetwork("10.0.0.0/8"), 24)
        self.ip6_net = util.generate_subnet(rnd, IPNetwork("fdb0::/16"), 64)
        host_mac = util.generate_mac(rnd)

        self.deployment = Deployment(
            containers=[
                ContainerMeta.make_vpn(user_id, ["internal"])
            ],
            networks=[
                NetworkMeta(name="internal")
            ]
        )

        self.form_classes = [
            RegexpForm.make_task("mac", answer=re.compile(f"^{str(host_mac).replace('-', '[-:]?')}$", re.I))
        ]

        self.checks = {
            "dhcpd": Check([
                ContainerMeta(
                    name="bot",
                    image="ct-itmo/labs-networking-dhcpd-bot",
                    networks={"internal": str(host_mac)},
                    ipv6_forwarding=False
                )
            ], { 0: "/out/dhcpcd.log" }, self.check_dhcpd)
        }


class DHCPDChapter(CheckableMixin, DockerMixin, FormMixin, BaseChapter[DHCPDVariant]):
    slug = "dhcpd"
    name = "DHCP-сервер"
    deadline = datetime(2023, 5, 24, 21, 0, 0)
    tasks = [
        ChapterTask("ip4", "Выдайте IPv4-адрес", Decimal(6)),
        ChapterTask("ip6", "Настройте SLAAC", Decimal(6)),
        ChapterTask("mac", "MAC-адрес", Decimal(1.5))
    ]

    @util.scope_cached("variant")
    async def get_variant(self, request: Request) -> DHCPDVariant:
        user_id: int = request.scope["user"].id
        return DHCPDVariant(user_id)


__all__ = ["DHCPDChapter"]
