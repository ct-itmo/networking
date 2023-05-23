import re
from datetime import datetime
from decimal import Decimal
from random import Random
from typing import Literal

from aiodocker.containers import DockerContainer
from aiodocker.exceptions import DockerError
from netaddr import IPAddress, IPNetwork
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from quirck.box.meta import Deployment, ContainerMeta, NetworkMeta
from quirck.box.model import DockerMeta

from networking.core import util
from networking.core.chapter.base import BaseChapter, ChapterTask
from networking.core.chapter.check import Check, CheckableMixin
from networking.core.chapter.docker import DockerMixin
from networking.core.config import SECRET_SEED, EXTERNAL_BASE_URL
from networking.core.model import Attempt


def addresses_list(*addresses: tuple[IPAddress, int]) -> str:
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
    form_classes = []

    ip4_a_network: IPNetwork
    ip4_b_network: IPNetwork
    ip4_a_firewall: IPAddress
    ip4_a_client: IPAddress
    ip4_a_checker: IPAddress
    ip4_a_free: IPAddress
    ip4_b_firewall: IPAddress
    ip4_b_client: IPAddress
    ip4_b_client2: IPAddress
    ip4_b_checker: IPAddress
    ip4_a_free: IPAddress
    allow_udp_port2: int
    icmp_ttl: int
    tcp_bad_word: str

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
        self.ip4_a_client, self.ip4_a_client2, self.ip4_a_free, ip4_a_checker = \
            util.generate_distinct(4, util.generate_address, rnd, self.ip4_a_network, no_gateway=True)

        self.ip4_b_firewall = IPAddress(self.ip4_b_network.first | 1, self.ip4_a_network.version)
        self.ip4_b_client, self.ip4_b_free, ip4_b_checker, self.ip4_b_client2 = \
            util.generate_distinct(4, util.generate_address, rnd, self.ip4_b_network, no_gateway=True)

        udp_ports_number = util.generate_distinct(10, rnd.randint, 2001, 3000)
        self.allow_udp_port2 = udp_ports_number[0]
        deny_udp_addresses = addresses_list(*map(lambda p: (self.ip4_b_client2, p), udp_ports_number[1:]))
        udp_ports_client_listen = addresses_list(*map(lambda p: (self.ip4_b_client2, p), udp_ports_number))

        self.icmp_ttl = rnd.randint(20, 50)

        mac_a_client, mac_b_client, mac_a_checker, mac_b_checker, mac_b_client2 = \
            util.generate_distinct(5, util.generate_mac, rnd)

        self.tcp_bad_word = f"{rnd.choice(NOUNS)}-{rnd.randint(1, 100)}"

        self.http_access_host = EXTERNAL_BASE_URL

        def make_checker_meta(name: str, network_type: Literal["A", "B"], check_mode: str = "basic",
                              environment: dict[str, str] = {}, task: str | None = None,
                              add_gateway: bool = True, add_socket_volume: bool = False) -> ContainerMeta:
            env = {
                "BOX_IP": str(ip4_a_checker if network_type == "A" else ip4_b_checker),
                "BOX_NETWORK_NAME": "internal" + network_type,
                "CHECK_MODE": check_mode
            }
            if task is not None:
                env["TASK"] = task
                env["CHAPTER"] = "firewall"
            if add_gateway:
                env["BOX_GATEWAY"] = str(self.ip4_a_firewall if network_type == "A" else self.ip4_b_firewall)

            return ContainerMeta(
                name="check-" + name,
                image="ct-itmo/labs-networking-firewall-checker",
                networks={"internal" + network_type: str(mac_a_checker if network_type == "A" else mac_b_checker)},
                ipv6_forwarding=False,
                environment={**env, **environment},
                volumes=util.socket_volume() if add_socket_volume else {}
            )

        self.deployment = Deployment(
            containers=[
                ContainerMeta.make_vpn(user_id, ["internalA", "internalB"]),
                ContainerMeta(
                    name="client-a",
                    image="ct-itmo/labs-networking-firewall-client",
                    networks={"internalA": str(mac_a_client)},
                    environment={
                        "BOX_IP": str(self.ip4_a_client),
                        "BOX_IP2": str(self.ip4_a_client2),
                        "BOX_GATEWAY": str(self.ip4_a_firewall),
                        "UDP_SERVERS": addresses_list((self.ip4_a_client, 3001)),
                        "TCP_SERVERS": addresses_list((self.ip4_a_client, 3002), (self.ip4_a_client2, 3333)),
                    },
                    volumes=util.socket_volume()
                ),
                ContainerMeta(
                    name="client-b",
                    image="ct-itmo/labs-networking-firewall-client",
                    networks={"internalB": str(mac_b_client)},
                    environment={
                        "BOX_IP": str(self.ip4_b_client),
                        "BOX_GATEWAY": str(self.ip4_b_firewall),
                        "UDP_SERVERS": addresses_list((self.ip4_b_client, 3001)),
                        "TCP_SERVERS": addresses_list((self.ip4_b_client, 3002)),
                        "HTTP_SERVERS": addresses_list((self.ip4_b_client, 3003)),
                    },
                    volumes=util.socket_volume()
                ),
            ],
            networks=[
                NetworkMeta(name="internalA"),
                NetworkMeta(name="internalB"),
            ]
        )

        self.checks = {
            "setup": Check([
                make_checker_meta(
                    name="ping",
                    network_type="B",
                    task="setup",
                    environment={
                        "BOX_IP2": str(ip4_a_checker),
                        "PING_VALID_IPS": str(self.ip4_b_firewall) + "," + str(self.ip4_b_client),
                        "PING_INVALID_IPS": str(self.ip4_a_firewall) + "," + str(self.ip4_a_client),
                    },
                    add_gateway=False,
                    add_socket_volume=True,
                )
            ], {0: "/out/check.log"}),
            "forward_a_to_b": Check([
                make_checker_meta(
                    name="forward-a-to-b",
                    network_type="A",
                    task="forward_a_to_b",
                    environment={
                        "PING_VALID_IPS": str(self.ip4_b_firewall) + "," + str(self.ip4_b_client),
                        "UDP_VALID_ADDRESSES": addresses_list((self.ip4_b_client, 3001)),
                        "TCP_VALID_ADDRESSES": addresses_list((self.ip4_b_client, 3002)),
                    },
                    add_socket_volume=True,
                )
            ], {0: "/out/check.log"}),
            "forward_b_to_a": Check([
                make_checker_meta(
                    name="forward-b-to-a",
                    network_type="B",
                    task="forward_b_to_a",
                    environment={
                        "PING_VALID_IPS": str(self.ip4_a_firewall) + "," + str(self.ip4_a_client),
                        "UDP_VALID_ADDRESSES": addresses_list((self.ip4_a_client, 3001)),
                    },
                    add_socket_volume=True,
                )
            ], {0: "/out/check.log"}),
            "tcp_unidirectional": Check([
                make_checker_meta(
                    name="tcp-unidirectional-a",
                    network_type="A",
                    environment={
                        "PING_VALID_IPS": str(self.ip4_a_client) + "," + str(self.ip4_b_client),
                        "UDP_VALID_ADDRESSES": addresses_list((self.ip4_a_client, 3001), (self.ip4_b_client, 3001)),
                        "TCP_VALID_ADDRESSES": addresses_list((self.ip4_a_client, 3002), (self.ip4_b_client, 3002)),
                    },
                    add_socket_volume=True,
                ),
                make_checker_meta(
                    name="tcp-unidirectional-b",
                    network_type="B",
                    environment={
                        "PING_VALID_IPS": str(self.ip4_a_client) + "," + str(self.ip4_b_client),
                        "UDP_VALID_ADDRESSES": addresses_list((self.ip4_a_client, 3001), (self.ip4_b_client, 3001)),
                        "TCP_VALID_ADDRESSES": addresses_list((self.ip4_b_client, 3002)),
                        "TCP_INVALID_ADDRESSES": addresses_list((self.ip4_a_client, 3002), (self.ip4_a_client2, 3333)),
                    },
                    add_socket_volume=True,
                )
            ], {0: "/out/check.log", 1: "/out/check.log"}, self.check_tcp_unidirectional),
            "udp_ports": Check([
                make_checker_meta(
                    name="udp-ports-a",
                    network_type="A",
                    environment={
                        "PING_VALID_IPS": str(self.ip4_b_client2),
                        "UDP_VALID_ADDRESSES":
                            addresses_list((self.ip4_b_client, 3001), (self.ip4_b_client2, 3001),
                                           (self.ip4_b_client2, self.allow_udp_port2)),
                        "UDP_INVALID_ADDRESSES": deny_udp_addresses,
                        "STARTUP_TIMEOUT": "2",
                    },
                ),
                make_checker_meta(
                    name="udp-ports-b",
                    network_type="B",
                    environment={
                        "UDP_VALID_ADDRESSES": addresses_list((self.ip4_a_client, 3001), (self.ip4_b_client, 3001)),
                    },
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
                        "UDP_SERVERS": addresses_list((self.ip4_b_client2, 3001)) + "," + udp_ports_client_listen,
                        "HIDE_REQUEST_SOURCE": "true",
                    },
                    volumes=util.socket_volume()
                )
            ], {0: "/out/check.log", 1: "/out/check.log", 2: "/out/check.log"}, self.check_udp_ports,
                logs_joiner=lambda container_logs: f"=== from network B:\n{container_logs[1]}\n"
                                                   f"=== from network A:\n{container_logs[0]}\n"
                                                   f"=== logs from servers in network B:\n{container_logs[2]}"),
            "tcp_body_filter": Check([
                make_checker_meta(
                    name="tcp-body-filter-a",
                    network_type="A",
                    check_mode="tcp_body_filter",
                    task="tcp_body_filter",
                    environment={
                        "TCP_VALID_ADDRESSES": addresses_list((self.ip4_b_client, 3002)),
                        "BAD_WORD": self.tcp_bad_word,
                    },
                    add_socket_volume=True,
                )
            ], {0: "/out/check.log"}),
            "forward_nat": Check([
                make_checker_meta(
                    name="forward-a-to-b",
                    network_type="A",
                    check_mode="forwarding_nat",
                    environment={
                        "NAT_IP": str(self.ip4_b_firewall),
                        "UDP_VALID_ADDRESSES": addresses_list((self.ip4_b_client, 3001)),
                        "TCP_VALID_ADDRESSES": addresses_list((self.ip4_b_client, 3002)),
                    },
                ),
                make_checker_meta(
                    name="forward-b-to-a",
                    network_type="B",
                    check_mode="forwarding_nat",
                    environment={
                        "NAT_IP": str(self.ip4_a_firewall),
                        "UDP_VALID_ADDRESSES": addresses_list((self.ip4_a_client, 3001)),
                    },
                )
            ], {0: "/out/check.log", 1: "/out/check.log"}, self.check_forward_nat),
            "icmp_config": Check([
                make_checker_meta(
                    name="icmp-config-b",
                    network_type="B",
                    check_mode="icmp_config",
                    task="icmp_config",
                    environment={
                        "PING_VALID_IPS": str(self.ip4_a_client),
                        "PING_EXPECTED_TTL": str(self.icmp_ttl),
                    },
                    add_socket_volume=True,
                )
            ], {0: "/out/check.log"}),
            "http_access": Check([
                make_checker_meta(
                    name="icmp-http-access",
                    network_type="A",
                    check_mode="http_access",
                    task="http_access",
                    environment={
                        "HTTP_VALID_URLS": str(EXTERNAL_BASE_URL)+ f",http://{self.ip4_b_client}:3003",
                        "HTTP_INVALID_URLS": "https://ya.ru,http://vk.com,http://google.com,https://8.8.8.8",
                        "SECRET_SEED": str(SECRET_SEED),
                    },
                    add_socket_volume=True,
                )
            ], {0: "/out/check.log"}),
        }


class FirewallChapter(CheckableMixin, DockerMixin, BaseChapter[FirewallVariant]):
    slug = "firewall"
    name = "Файрвол"
    author = "Константин Бац"
    deadline = datetime(2023, 6, 20, 21, 0, 0)
    tasks = [
        ChapterTask("setup", "Устройство в двух сетях", Decimal(1)),
        ChapterTask("forward_a_to_b", "Форвардинг из A в B", Decimal(1)),
        ChapterTask("forward_b_to_a", "Форвардинг из B в A", Decimal(1)),
        ChapterTask("tcp_unidirectional", "TCP только из A в B", Decimal(2)),
        ChapterTask("udp_ports", "Ограничение UDP", Decimal(1)),
        ChapterTask("tcp_body_filter", "Фильтр содержимого", Decimal(1)),
        ChapterTask("forward_nat", "NAT", Decimal(1)),
        ChapterTask("icmp_config", "Настройка ICMP", Decimal(2)),
        ChapterTask("http_access", "HTTP-доступ", Decimal(2))
    ]

    @util.scope_cached("variant")
    async def get_variant(self, request: Request) -> FirewallVariant:
        user_id: int = request.scope["user"].id
        return FirewallVariant(user_id)


__all__ = ["FirewallChapter"]
