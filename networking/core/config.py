from starlette.datastructures import Secret

from quirck.core.config import config


SECRET_SEED = config("SECRET_SEED", cast=Secret)
SOCKET_PATH = config("SOCKET_PATH", cast=str)
