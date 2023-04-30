FROM rust:slim-buster as build

RUN USER=root cargo new --bin dhcp
WORKDIR /dhcp

COPY ./Cargo.toml ./Cargo.toml
COPY ./Cargo.lock ./Cargo.lock

RUN cargo build --release && rm -rf src && rm -rf target/release/deps/dhcp*

COPY ./src src

RUN cargo build --release

FROM debian:bullseye-slim

RUN apt-get update -q && apt-get install -qy --no-install-recommends iproute2 dnsmasq && rm -rf /var/lib/apt/lists/*
COPY dnsmasq.conf /etc/dnsmasq.conf
COPY start.sh /app/start.sh
COPY --from=build /dhcp/target/release/dhcp /app/dhcp-accept
CMD ["/app/start.sh"]