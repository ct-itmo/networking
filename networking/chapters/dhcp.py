import re
import string
from datetime import datetime
from decimal import Decimal
from random import Random

from netaddr import IPNetwork
from starlette.requests import Request

from quirck.box.meta import Deployment, ContainerMeta, NetworkMeta
from quirck.core.form import BaseTaskForm, RegexpForm

from networking.core import util
from networking.core.chapter import BaseChapter, ChapterTask, DockerMixin, FormMixin
from networking.core.config import SECRET_SEED


class DHCPVariant:
    deployment: Deployment
    form_classes: list[type[BaseTaskForm]]

    slaac_suffix: str
    domain: str

    def __init__(self, user_id: int):
        rnd = Random(f"{SECRET_SEED}-{user_id}")

        ip4_net = util.generate_subnet(rnd, IPNetwork("10.0.0.0/8"), 24)
        slaac_net = util.generate_subnet(rnd, IPNetwork("fdca::/16"), 64)
        dhcp6_net = util.generate_subnet(rnd, IPNetwork("fdcd::/16"), 64)

        dnsmasq_mac = util.generate_mac(rnd)
        ping_mac = util.generate_mac(rnd)
        http_mac = util.generate_mac(rnd)

        dns_ip = util.generate_address(rnd, dhcp6_net)
        http_ip = http_mac.ipv6(slaac_net.value or 0)
        client_ip4 = util.generate_address(rnd, next(ip4_net.subnet(prefixlen=25)))

        self.slaac_suffix = str(ping_mac.ipv6(0))
        self.domain = "".join(rnd.choice(string.ascii_lowercase + string.digits) for _ in range(24))

        self.deployment = Deployment(
            containers=[
                ContainerMeta.make_vpn(user_id, ["internal"]),
                ContainerMeta(
                    name="dnsmasq",
                    image="ct-itmo/labs-networking-dhcp-dnsmasq",
                    networks={"internal": str(dnsmasq_mac)},
                    environment={
                        "ADDRESS4": str(ip4_net.network + 254),
                        "ADDRESS6_1": str(dnsmasq_mac.ipv6(slaac_net.value or 0)),
                        "ADDRESS6_2": str(dhcp6_net.network + 0xffff),
                        "DHCP4": str(client_ip4),
                        "DHCP6": str(util.generate_address(rnd, dhcp6_net)),
                        "DNS6": str(dns_ip),
                        "SLAAC": str(slaac_net.network)
                    },
                    volumes=util.socket_volume()
                ),
                ContainerMeta(
                    name="nsd",
                    image="ct-itmo/labs-networking-dhcp-nsd",
                    networks={"internal": None},
                    environment={
                        "HOSTIP": str(dns_ip),
                        "DOMAIN": self.domain,
                        "AAAAIP": str(http_mac.ipv6(slaac_net.value or 0))
                    },
                    mem_limit=200 * 1024 * 1024,
                    ipv6_forwarding=False
                ),
                ContainerMeta(
                    name="ping",
                    image="ct-itmo/labs-networking-ping",
                    networks={"internal": str(ping_mac)},
                    environment={
                        "STUDENT_IP": "any",
                        "CHAPTER": "dhcp",
                        "TASK": "slaac"
                    },
                    volumes=util.socket_volume(),
                    ipv6_forwarding=False
                ),
                ContainerMeta(
                    name="http",
                    image="ct-itmo/labs-networking-dhcp-http",
                    networks={"internal": str(http_mac)},
                    environment={
                        "BIND": f"[{http_ip}]:9229"
                    },
                    volumes=util.socket_volume(),
                    ipv6_forwarding=False
                )
            ],
            networks=[
                NetworkMeta(name="internal")
            ]
        )

        self.form_classes = [
            RegexpForm.make_task("net", answer=re.compile(f"^{client_ip4}/24$", re.I)),
            RegexpForm.make_task("dns", answer=re.compile(f"^{http_ip}$", re.I))
        ]


class DHCPChapter(DockerMixin, FormMixin, BaseChapter[DHCPVariant]):
    slug = "dhcp"
    name = "DHCP-клиент"
    deadline = datetime(2023, 5, 24, 21, 0, 0)
    tasks = [
        ChapterTask("ip4", "Получите IPv4-адрес", Decimal(1)),
        ChapterTask("net", "Адрес и маска сети", Decimal(1)),
        ChapterTask("slaac", "Получите SLAAC-адрес", Decimal(1)),
        ChapterTask("ip6", "Получите адрес по DHCPv6", Decimal(1)),
        ChapterTask("dns", "Адрес сайта", Decimal(1)),
        ChapterTask("web", "Кнопка", Decimal(2))
    ]

    @util.scope_cached("variant")
    async def get_variant(self, request: Request) -> DHCPVariant:
        user_id: int = request.scope["user"].id
        return DHCPVariant(user_id)


__all__ = ["DHCPChapter"]
