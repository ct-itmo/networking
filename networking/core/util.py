import functools
from random import Random
from typing import Awaitable, Callable, ParamSpec, TypeVar

from netaddr import EUI, IPAddress, IPNetwork
from netaddr.ip import BaseIP
from starlette.requests import Request

from networking.core.config import SOCKET_PATH

Args = ParamSpec("Args")
T = TypeVar("T")


def get_address_size(ip: BaseIP) -> int:
    match ip.version:
        case 4: return 32
        case 6: return 128
        case _: raise ValueError(f"Unknown IP version: {ip.version}")


def generate_mac(rnd: Random) -> EUI:
    # addresses having first octet x2, x6, xC or xE are locally administered, it's safe to use such one
    return EUI((0x02 << 40) | rnd.getrandbits(40), version=48)


def generate_subnet(rnd: Random, network: IPNetwork, new_prefix_len: int) -> IPNetwork:
    bit_count = new_prefix_len - network.prefixlen
    assert(bit_count >= 0)

    if bit_count == 0:
        return network

    new_addr = network.first | (rnd.getrandbits(bit_count) << (get_address_size(network) - new_prefix_len))

    return IPNetwork((new_addr, new_prefix_len), version=network.version)


def generate_address(rnd: Random, network: IPNetwork) -> IPAddress:
    bit_count = get_address_size(network) - network.prefixlen
    if bit_count == 0:
        return network.ip

    entropy = rnd.getrandbits(bit_count)
    if bit_count > 1:
        while entropy == 0 or entropy == (1 << bit_count) - 1:
            entropy = rnd.getrandbits(bit_count)

    return IPAddress(network.first | entropy, version=network.version)


def generate_distinct(n: int, func: Callable[Args, T], *args: Args.args, **kwargs: Args.kwargs) -> tuple[T, ...]:
    while True:
        results = tuple(func(*args, **kwargs) for _ in range(n))
        if len(set(results)) == n:
            return results


def socket_volume() -> dict[str, str]:
    return {SOCKET_PATH: "/var/run/quirck.sock"}


def scope_cached(key: str):
    def inner(func: Callable[Args, Awaitable[T]]) -> Callable[Args, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Args.args, **kwargs: Args.kwargs) -> T:
            request: Request | None = None

            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            else:
                for arg in kwargs.values():
                    if isinstance(arg, Request):
                        request = arg
                        break
                else:
                    raise TypeError("scope_cached() can be applied only to functions containing Request")
            
            if key not in request.scope:
                request.scope[key] = await func(*args, **kwargs)

            return request.scope[key]

        return wrapper
    return inner


__all__ = [
    "generate_mac", "generate_subnet", "generate_address", "generate_distinct",
    "socket_volume", "scope_cached"
]
