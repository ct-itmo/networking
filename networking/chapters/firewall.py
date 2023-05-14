import re
from datetime import datetime
from decimal import Decimal
from random import Random

from aiodocker.containers import DockerContainer
from aiodocker.exceptions import DockerError
from netaddr import EUI, IPAddress, IPNetwork
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from quirck.box.meta import Deployment, ContainerMeta, NetworkMeta
from quirck.core.form import BaseTaskForm, RegexpForm
from quirck.box.model import DockerMeta

from networking.core import util
from networking.core.chapter.base import BaseChapter, ChapterTask
from networking.core.chapter.check import Check, CheckableMixin
from networking.core.chapter.docker import DockerMixin
from networking.core.chapter.form import FormMixin
from networking.core.config import SECRET_SEED
from networking.core.model import Attempt


def addresses_list(*addresses: tuple[str, int]) -> str:
    return ",".join(str(ip) + ":" + str(port) for (ip, port) in addresses)


async def check_docker_result(container: DockerContainer) -> bool:
    try:
        result_file = await container.get_archive("/out/result")
        extracted = result_file.extractfile("result")
        if extracted is None:
            return False
        try:
            return extracted.read().decode().strip() == "OK"
        except UnicodeDecodeError:
            return False
        finally:
            extracted.close()
    except DockerError:
        return False


NOUNS = ["solutions", "task", "solver", "results", "scores", "author", "checker"]


async def commit_correct_attempt(session: AsyncSession, meta: DockerMeta, task: str) -> None:
    attempt = Attempt(
        user_id=meta.user_id,
        chapter=FirewallChapter.slug,
        task=task,
        data={},
        is_correct=True
    )
    session.add(attempt)
    await session.commit()


class FirewallVariant:
    deployment: Deployment
    form_classes: list[type[BaseTaskForm]]

    ll_mac: EUI
    ip4_client: IPAddress
    ip4_server: IPAddress
    ip6_client: IPAddress
    ip6_server: IPAddress

    async def check_tcp_unidirectional(self, session: AsyncSession, meta: DockerMeta,
                                       containers: list[DockerContainer]) -> None:
        a_checker, b_checker = containers
        if not (await check_docker_result(a_checker) and await check_docker_result(b_checker)):
            return
        await commit_correct_attempt(session, meta, "tcp_unidirectional")

    async def check_forward_nat(self, session: AsyncSession, meta: DockerMeta,
                                       containers: list[DockerContainer]) -> None:
        a_checker, b_checker = containers
        if not (await check_docker_result(a_checker) and await check_docker_result(b_checker)):
            return
        await commit_correct_attempt(session, meta, "forward_nat")

    async def check_udp_ports(self, session: AsyncSession, meta: DockerMeta,
                              containers: list[DockerContainer]) -> None:
        a_checker, b_checker, a_client2 = containers

        if not (await check_docker_result(a_checker) and await check_docker_result(b_checker)):
            return

        try:
            result_file = await a_client2.get_archive("/out/check.log")
            extracted = result_file.extractfile("check.log")
            if extracted is None:
                return
            try:
                for log in extracted.read().decode().split("\n"):
                    if m := re.fullmatch(r"\[UDP\s[\d\.]+:(\d+)\].*", log):
                        port = int(m.groups(0)[0])
                        if port != 3001 and port != self.allow_udp_port2:
                            return
            except UnicodeDecodeError:
                return
            finally:
                extracted.close()
        except DockerError:
            return

        attempt = Attempt(
            user_id=meta.user_id,
            chapter=FirewallChapter.slug,
            task="udp_ports",
            data={},
            is_correct=True
        )

        session.add(attempt)
        await session.commit()

    def __init__(self, user_id: int):
        rnd = Random(f"{SECRET_SEED}-{user_id}")

        self.ip4_a_network = util.generate_subnet(rnd, IPNetwork("10.0.0.0/9"), 24)
        self.ip4_b_network = util.generate_subnet(rnd, IPNetwork("10.128.0.0/9"), 24)

        self.ip4_a_firewall = IPAddress(self.ip4_a_network.first | 1, self.ip4_a_network.version)
        self.ip4_a_client, self.ip4_a_free, ip4_a_checker = \
            util.generate_distinct(3, util.generate_address, rnd, self.ip4_a_network, no_gateway=True)

        self.ip4_b_firewall = IPAddress(self.ip4_b_network.first | 1, self.ip4_a_network.version)
        self.ip4_b_client, self.ip4_b_free, ip4_b_checker, self.ip4_b_client2 = \
            util.generate_distinct(4, util.generate_address, rnd, self.ip4_b_network, no_gateway=True)

        udp_ports_number = util.generate_distinct(10, rnd.randint, 2001, 3000)
        self.allow_udp_port2 = udp_ports_number[0]
        deny_udp_addresses = addresses_list(*map(lambda p: (self.ip4_b_client2, p), udp_ports_number[1:]))
        udp_ports_client_listen = addresses_list(*map(lambda p: (self.ip4_b_client2, p), udp_ports_number))
        # udp_port_check_addresses = util.generate_distinct(10, rnd)

        # self.ip4_client, self.ip4_server = util.generate_distinct(2, util.generate_address, rnd, ip4_network)

        # ip6_network = util.generate_subnet(rnd, IPNetwork("fd33::/16"), 64)
        # self.ip6_client, self.ip6_server = util.generate_distinct(2, util.generate_address, rnd, ip6_network)

        mtu = rnd.randint(1000, 1100)

        mac_a_client, mac_b_client, mac_a_checker, mac_b_checker, mac_b_client2 = \
            util.generate_distinct(5, util.generate_mac, rnd)
        self.ll_mac = util.generate_mac(rnd)
        mac4 = util.generate_mac(rnd)
        mac6 = util.generate_mac(rnd)

        self.tcp_bad_word = f"{rnd.choice(NOUNS)}-{rnd.randint(1, 100)}"

        self.deployment = Deployment(
            containers=[
                ContainerMeta.make_vpn(user_id, ["internalA", "internalB"]),
                ContainerMeta(
                    name="client-a",
                    image="ct-itmo/labs-networking-firewall-client",
                    networks={"internalA": str(mac_a_client)},
                    environment={
                        "BOX_IP": self.ip4_a_client,
                        "BOX_GATEWAY": self.ip4_a_firewall,

                    },
                    volumes=util.socket_volume()
                ),
                ContainerMeta(
                    name="client-b",
                    image="ct-itmo/labs-networking-firewall-client",
                    networks={"internalB": str(mac_b_client)},
                    environment={
                        "BOX_IP": self.ip4_b_client,
                        "BOX_GATEWAY": self.ip4_b_firewall,
                    },
                    volumes=util.socket_volume()
                ),
                ContainerMeta(
                    name="test-a",
                    image="ct-itmo/labs-networking-firewall-checker-sleep",
                    networks={"internalA": str(mac4)},
                    environment={
                        "BOX_IP": str(self.ip4_a_free),
                        "BOX_GATEWAY": str(self.ip4_a_firewall),
                        "BOX_NETWORK_NAME": "internalA",
                        "PING_VALID_IPS": str(self.ip4_b_firewall) + "," + str(self.ip4_b_client),
                        "CLIENT_CONNECTION_IP": str(self.ip4_b_client),
                        "STUDENT_IP": "any",
                        "CHAPTER": "firewall",
                        "TASK": "forward_a_to_b",
                        "CHECK_MODE": "forwarding",
                    },
                    volumes=util.socket_volume()
                ),
            ],
            networks=[
                NetworkMeta(name="internalA"),
                NetworkMeta(name="internalB"),
            ]
        )

        self.form_classes = [
            RegexpForm.make_task("mac4", answer=re.compile(f"^{str(mac4).replace('-', '[-:]?')}$", re.I)),
            RegexpForm.make_task("mac6", answer=re.compile(f"^{str(mac6).replace('-', '[-:]?')}$", re.I)),
            RegexpForm.make_task("mtu", answer=re.compile(f"^{mtu}$", re.I))
        ]

        self.checks = {
            "setup": Check([
                ContainerMeta(
                    name="check-ping",
                    image="ct-itmo/labs-networking-firewall-checker",
                    networks={"internalB": str(mac_b_checker)},
                    ipv6_forwarding=False,
                    environment={
                        "BOX_IP": str(ip4_a_checker),
                        "BOX_IP2": str(ip4_b_checker),
                        "BOX_NETWORK_NAME": "internalB",
                        "PING_VALID_IPS": str(self.ip4_b_firewall) + "," + str(self.ip4_b_client),
                        "PING_INVALID_IPS": str(self.ip4_a_firewall) + "," + str(self.ip4_a_client),
                        "CHAPTER": "firewall",
                        "TASK": "setup",
                        "CHECK_MODE": "setup",
                    },
                    volumes=util.socket_volume()
                )
            ], {0: "/out/check.log"}),
            "forward_a_to_b": Check([
                ContainerMeta(
                    name="check-forward-a-to-b",
                    image="ct-itmo/labs-networking-firewall-checker",
                    networks={"internalA": str(mac_a_checker)},
                    ipv6_forwarding=False,
                    environment={
                        "BOX_IP": str(ip4_a_checker),
                        "BOX_GATEWAY": str(self.ip4_a_firewall),
                        "BOX_NETWORK_NAME": "internalA",
                        "PING_VALID_IPS": str(self.ip4_b_firewall) + "," + str(self.ip4_b_client),
                        "UDP_VALID_ADDRESSES": addresses_list((self.ip4_b_client, 3001)),
                        "TCP_VALID_ADDRESSES": addresses_list((self.ip4_b_client, 3002)),
                        "CHAPTER": "firewall",
                        "TASK": "forward_a_to_b",
                        "CHECK_MODE": "forwarding",
                    },
                    volumes=util.socket_volume()
                )
            ], {0: "/out/check.log"}),
            "forward_b_to_a": Check([
                ContainerMeta(
                    name="check-forward-b-to-a",
                    image="ct-itmo/labs-networking-firewall-checker",
                    networks={"internalB": str(mac_b_checker)},
                    ipv6_forwarding=False,
                    environment={
                        "BOX_IP": str(ip4_b_checker),
                        "BOX_GATEWAY": str(self.ip4_b_firewall),
                        "BOX_NETWORK_NAME": "internalB",
                        "PING_VALID_IPS": str(self.ip4_a_firewall) + "," + str(self.ip4_a_client),
                        "UDP_VALID_ADDRESSES": addresses_list((self.ip4_a_client, 3001)),
                        "CHAPTER": "firewall",
                        "TASK": "forward_b_to_a",
                        "CHECK_MODE": "forwarding",
                    },
                    volumes=util.socket_volume()
                )
            ], {0: "/out/check.log"}),
            "tcp_unidirectional": Check([
                ContainerMeta(
                    name="check-tcp-unidirectional-a",
                    image="ct-itmo/labs-networking-firewall-checker",
                    networks={"internalA": str(mac_a_checker)},
                    ipv6_forwarding=False,
                    environment={
                        "BOX_IP": str(ip4_a_checker),
                        "BOX_GATEWAY": str(self.ip4_a_firewall),
                        "BOX_NETWORK_NAME": "internalA",
                        "PING_VALID_IPS": str(self.ip4_a_client) + "," + str(self.ip4_b_client),
                        "UDP_VALID_ADDRESSES": addresses_list((self.ip4_a_client, 3001), (self.ip4_b_client, 3001)),
                        "TCP_VALID_ADDRESSES": addresses_list((self.ip4_a_client, 3002), (self.ip4_b_client, 3002)),
                        "CHECK_MODE": "tcp_unidirectional",
                    },
                    volumes=util.socket_volume()
                ),
                ContainerMeta(
                    name="check-tcp-unidirectional-b",
                    image="ct-itmo/labs-networking-firewall-checker",
                    networks={"internalB": str(mac_b_checker)},
                    ipv6_forwarding=False,
                    environment={
                        "BOX_IP": str(ip4_b_checker),
                        "BOX_GATEWAY": str(self.ip4_b_firewall),
                        "BOX_NETWORK_NAME": "internalB",
                        "PING_VALID_IPS": str(self.ip4_a_client) + "," + str(self.ip4_b_client),
                        "UDP_VALID_ADDRESSES": addresses_list((self.ip4_a_client, 3001), (self.ip4_b_client, 3001)),
                        "TCP_VALID_ADDRESSES": addresses_list((self.ip4_b_client, 3002)),
                        "TCP_INVALID_ADDRESSES": addresses_list((self.ip4_a_client, 3002)),
                        "CHECK_MODE": "tcp_unidirectional",
                    },
                    volumes=util.socket_volume()
                ),
            ], {0: "/out/check.log", 1: "/out/check.log"}, self.check_tcp_unidirectional),
            "udp_ports": Check([
                ContainerMeta(
                    name="check-udp-ports-a",
                    image="ct-itmo/labs-networking-firewall-checker",
                    networks={"internalA": str(mac_a_checker)},
                    ipv6_forwarding=False,
                    environment={
                        "BOX_IP": str(ip4_a_checker),
                        "BOX_GATEWAY": str(self.ip4_a_firewall),
                        "BOX_NETWORK_NAME": "internalA",
                        "PING_VALID_IPS": str(self.ip4_b_client2),
                        "UDP_VALID_ADDRESSES":
                            addresses_list((self.ip4_b_client, 3001), (self.ip4_b_client2, 3001),
                                           (self.ip4_b_client2, self.allow_udp_port2)),
                        "UDP_INVALID_ADDRESSES": deny_udp_addresses,
                        "CHECK_MODE": "tcp_unidirectional",
                        "STARTUP_TIMEOUT": "2",
                    },
                    volumes=util.socket_volume()
                ),
                ContainerMeta(
                    name="check-udp-ports-b",
                    image="ct-itmo/labs-networking-firewall-checker",
                    networks={"internalB": str(mac_b_checker)},
                    ipv6_forwarding=False,
                    environment={
                        "BOX_IP": str(ip4_b_checker),
                        "BOX_GATEWAY": str(self.ip4_b_firewall),
                        "BOX_NETWORK_NAME": "internalB",
                        "UDP_VALID_ADDRESSES": addresses_list((self.ip4_a_client, 3001), (self.ip4_b_client, 3001)),
                        "CHECK_MODE": "tcp_unidirectional",
                    },
                    volumes=util.socket_volume()
                ),
                ContainerMeta(
                    name="check-udp-ports-b-client",
                    image="ct-itmo/labs-networking-firewall-client",
                    networks={"internalB": str(mac_b_client2)},
                    ipv6_forwarding=False,
                    environment={
                        "BOX_IP": str(self.ip4_b_client2),
                        "BOX_GATEWAY": str(self.ip4_b_firewall),
                        "TIMEOUT": "10s",
                        "OTHER_UDP_SERVER": udp_ports_client_listen,
                        "HIDE_REQUEST_SOURCE": "true",
                    },
                    volumes=util.socket_volume()
                ),
            ], {0: "/out/check.log", 1: "/out/check.log", 2: "/out/check.log"}, self.check_udp_ports),
            "tcp_body_filter": Check([
                ContainerMeta(
                    name="check-udp-ports-a",
                    image="ct-itmo/labs-networking-firewall-checker",
                    networks={"internalA": str(mac_a_checker)},
                    ipv6_forwarding=False,
                    environment={
                        "BOX_IP": str(ip4_a_checker),
                        "BOX_GATEWAY": str(self.ip4_a_firewall),
                        "BOX_NETWORK_NAME": "internalA",
                        "TCP_VALID_ADDRESSES": addresses_list((self.ip4_b_client, 3002)),
                        "CHECK_MODE": "tcp_body_filter",
                        "CHAPTER": "firewall",
                        "TASK": "tcp_body_filter",
                        "BAD_WORD": self.tcp_bad_word,
                    },
                    volumes=util.socket_volume()
                ),
            ], {0: "/out/check.log"}),
            "forward_nat": Check([
                ContainerMeta(
                    name="check-forward-a-to-b",
                    image="ct-itmo/labs-networking-firewall-checker",
                    networks={"internalA": str(mac_a_checker)},
                    ipv6_forwarding=False,
                    environment={
                        "BOX_IP": str(ip4_a_checker),
                        "BOX_GATEWAY": str(self.ip4_a_firewall),
                        "BOX_NETWORK_NAME": "internalA",
                        "NAT_IP": str(self.ip4_b_firewall),
                        "UDP_VALID_ADDRESSES": addresses_list((self.ip4_b_client, 3001)),
                        "TCP_VALID_ADDRESSES": addresses_list((self.ip4_b_client, 3002)),
                        "CHECK_MODE": "forwarding_nat",
                    },
                ),
                ContainerMeta(
                    name="check-forward-b-to-a",
                    image="ct-itmo/labs-networking-firewall-checker",
                    networks={"internalB": str(mac_b_checker)},
                    ipv6_forwarding=False,
                    environment={
                        "BOX_IP": str(ip4_b_checker),
                        "BOX_GATEWAY": str(self.ip4_b_firewall),
                        "BOX_NETWORK_NAME": "internalB",
                        "NAT_IP": str(self.ip4_a_firewall),
                        "UDP_VALID_ADDRESSES": addresses_list((self.ip4_a_client, 3001)),
                        "CHECK_MODE": "forwarding_nat",
                    },
                ),
            ], {0: "/out/check.log", 1: "/out/check.log"}, self.check_forward_nat),
        }


class FirewallChapter(CheckableMixin, DockerMixin, FormMixin, BaseChapter[FirewallVariant]):
    slug = "firewall"
    name = "Firewall"
    deadline = datetime(2023, 6, 5, 21, 0, 0)
    tasks = [
        ChapterTask("setup", "Устройство в двух сетях", Decimal(1)),
        ChapterTask("forward_a_to_b", "Forwarding из A в B", Decimal(1)),
        ChapterTask("forward_b_to_a", "Forwarding из B в A", Decimal(1)),
        ChapterTask("tcp_unidirectional", "TCP только из A в B", Decimal(1)),
        ChapterTask("udp_ports", "Ограничение UDP", Decimal(1)),
        ChapterTask("tcp_body_filter", "Фильтр содержимого", Decimal(1)),
        ChapterTask("forward_nat", "Forwarding с NAT", Decimal(1)),
        ChapterTask("mac4", "MAC-адрес", Decimal(2)),
        ChapterTask("ping_ll", "Link-local", Decimal(2)),
        ChapterTask("ping6", "IPv6-пинг", Decimal(1)),
        ChapterTask("mac6", "MAC-адрес (v6)", Decimal(1)),
        ChapterTask("mtu", "MTU", Decimal(3))
    ]

    @util.scope_cached("variant")
    async def get_variant(self, request: Request) -> FirewallVariant:
        user_id: int = request.scope["user"].id
        return FirewallVariant(user_id)


__all__ = ["FirewallChapter"]
