import re
from datetime import datetime
from decimal import Decimal
from random import Random

from netaddr import EUI, IPAddress, IPNetwork
from starlette.requests import Request
from wtforms.fields import BooleanField

from quirck.box.meta import Deployment, ContainerMeta, NetworkMeta

from networking.core import util
from networking.core.chapter.base import BaseChapter, ChapterTask
from networking.core.chapter.docker import DockerMixin
from networking.core.chapter.form import FormMixin, BaseTaskForm, RegexpForm, SingleTaskForm
from networking.core.config import SECRET_SEED


class NetcalcForm(SingleTaskForm):
    first = BooleanField("<code>192.168.77.5/24</code> и <code>192.168.77.6/29</code>")
    second = BooleanField("<code>172.19.21.5/23</code> и <code>172.19.20.199/24</code>")

    async def check(self) -> bool:
        return self.first.data and not self.second.data


class IPVariant:
    deployment: Deployment
    form_classes: list[type[BaseTaskForm]]

    ll_mac: EUI
    ip4_client: IPAddress
    ip4_server: IPAddress
    ip6_client: IPAddress
    ip6_server: IPAddress

    def __init__(self, user_id: int):
        rnd = Random(f"{SECRET_SEED}-{user_id}")

        self.ll_mac = util.generate_mac(rnd)

        ip4_network = util.generate_subnet(rnd, IPNetwork("10.0.0.0/8"), 24)
        self.ip4_client, self.ip4_server = util.generate_distinct(2, util.generate_address, rnd, ip4_network)

        ip6_network = util.generate_subnet(rnd, IPNetwork("fd33::/16"), 64)
        self.ip6_client, self.ip6_server = util.generate_distinct(2, util.generate_address, rnd, ip6_network)

        mtu = rnd.randint(1000, 1100)

        mac4 = util.generate_mac(rnd)
        mac6 = util.generate_mac(rnd)

        self.deployment = Deployment(
            containers=[
                ContainerMeta.make_vpn(user_id, ["internal"]),
                ContainerMeta(
                    name="ping4",
                    image="ct-itmo/labs-networking-ping",
                    networks={"internal": str(mac4)},
                    environment={
                        "BOX_IP": str(self.ip4_server),
                        "STUDENT_IP": str(self.ip4_client),
                        "CHAPTER": "ip",
                        "TASK": "ping4"
                    },
                    volumes=util.socket_volume()
                ),
                ContainerMeta(
                    name="ping-ll",
                    image="ct-itmo/labs-networking-ping",
                    networks={"internal": str(self.ll_mac)},
                    environment={
                        "STUDENT_IP": "any",
                        "CHAPTER": "ip",
                        "TASK": "ping_ll"
                    },
                    volumes=util.socket_volume()
                ),
                ContainerMeta(
                    name="ping6",
                    image="ct-itmo/labs-networking-ping",
                    networks={"internal": str(mac6)},
                    environment={
                        "BOX_IP": str(self.ip6_server),
                        "STUDENT_IP": str(self.ip6_client),
                        "MTU": str(mtu),
                        "CHAPTER": "ip",
                        "TASK": "ping6"
                    },
                    volumes=util.socket_volume()
                )
            ],
            networks=[
                NetworkMeta(name="internal")
            ]
        )

        self.form_classes = [
            NetcalcForm.make_task("netcalc"),
            RegexpForm.make_task("mac4", answer=re.compile(f"^{str(mac4).replace('-', '[-:]?')}$", re.I)),
            RegexpForm.make_task("mac6", answer=re.compile(f"^{str(mac6).replace('-', '[-:]?')}$", re.I)),
            RegexpForm.make_task("mtu", answer=re.compile(f"^{mtu}$", re.I))
        ]


class IPChapter(DockerMixin, FormMixin, BaseChapter[IPVariant]):
    slug = "ip"
    name = "Протокол IP"
    deadline = datetime(2024, 4, 5, 21, 0, 0)
    tasks = [
        ChapterTask("netcalc", "Локальные сети", Decimal(1)),
        ChapterTask("ping4", "Пинг!", Decimal(1)),
        ChapterTask("mac4", "MAC-адрес", Decimal(2)),
        ChapterTask("ping_ll", "Link-local", Decimal(2)),
        ChapterTask("ping6", "IPv6-пинг", Decimal(1)),
        ChapterTask("mac6", "MAC-адрес (v6)", Decimal(1)),
        ChapterTask("mtu", "MTU", Decimal(3))
    ]

    @util.scope_cached("variant")
    async def get_variant(self, request: Request) -> IPVariant:
        user_id: int = request.scope["user"].id
        return IPVariant(user_id)


__all__ = ["IPChapter"]
