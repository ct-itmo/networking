FROM debian:bullseye-slim

RUN apt-get update -q && \
    apt-get install -qy --no-install-recommends iproute2 nsd && \
    rm -rf /var/lib/apt/lists/*
COPY nsd.conf /etc/nsd.conf
COPY zone /etc/zone
COPY start.sh /start.sh
CMD ["/start.sh"]