FROM rust:1.94.0-slim-trixie AS build

RUN USER=root cargo new --bin dns
WORKDIR /dns

COPY ./Cargo.toml ./Cargo.toml
COPY ./Cargo.lock ./Cargo.lock

RUN cargo build --release && rm -rf src && rm -rf target/release/deps/dns*

COPY ./src src

RUN cargo build --release

FROM debian:trixie-slim

RUN apt-get update -q && apt-get install -qy --no-install-recommends iproute2 && rm -rf /var/lib/apt/lists/*
COPY start.sh /app/start.sh
COPY --from=build /dns/target/release/dns /app/dns-bot
CMD ["/app/start.sh"]
