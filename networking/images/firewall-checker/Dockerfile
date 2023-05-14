FROM golang:1.18-bullseye as build

COPY . /build
WORKDIR /build

RUN go build -o firewall-checker .

FROM debian:bullseye-slim

RUN apt-get update -q && apt-get install -qy --no-install-recommends iproute2 nftables strace iputils-ping procps && rm -rf /var/lib/apt/lists/*
COPY start.sh /app/start.sh
COPY --from=build /build/firewall-checker /app/firewall-checker

CMD ["/app/start.sh"]
