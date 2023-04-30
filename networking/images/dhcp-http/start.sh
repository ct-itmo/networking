#!/bin/bash

set -e

export RUST_LOG=info
export RUST_BACKTRACE=full

echo "Will bind to $BIND"
sleep 4

ip6tables -A INPUT -p icmpv6 --icmpv6-type echo-request -d ff02::1 -j DROP

exec /app/http
