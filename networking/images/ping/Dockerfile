FROM rust:1.69.0-slim-bullseye as build

ENV CARGO_REGISTRIES_CRATES_IO_PROTOCOL sparse

RUN USER=root cargo new --bin ping
WORKDIR /ping

COPY ./Cargo.toml ./Cargo.toml
COPY ./Cargo.lock ./Cargo.lock

RUN cargo build --release && rm -rf src && rm -rf target/release/deps/ping*

COPY ./src src

RUN cargo build --release

FROM debian:bullseye-slim

RUN apt-get update -q && apt-get install -qy --no-install-recommends iproute2 nftables strace && rm -rf /var/lib/apt/lists/*
COPY start.sh /app/start.sh
COPY --from=build /ping/target/release/ping /app/ping
CMD ["/app/start.sh"]
