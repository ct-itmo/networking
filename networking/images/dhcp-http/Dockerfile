FROM rust:1.69.0-slim-bullseye as build

ENV CARGO_REGISTRIES_CRATES_IO_PROTOCOL sparse

RUN USER=root cargo new --bin http
WORKDIR /http

COPY ./Cargo.toml ./Cargo.toml
COPY ./Cargo.lock ./Cargo.lock

RUN cargo build --release && rm -rf src && rm -rf target/release/deps/http*

COPY ./src src

RUN cargo build --release

FROM debian:bullseye-slim

RUN apt-get update -q && apt-get install -qy --no-install-recommends iproute2 iptables && rm -rf /var/lib/apt/lists/*
COPY start.sh /app/start.sh
COPY --from=build /http/target/release/http /app/http
CMD ["/app/start.sh"]
