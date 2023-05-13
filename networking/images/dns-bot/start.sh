#!/bin/bash

set -e

export INTERFACE=eth0
export RUST_LOG=info
export RUST_BACKTRACE=full

ip addr add $BOX_IP/24 dev eth0

mkdir /out
/app/dns-bot 2>/out/dns.log
