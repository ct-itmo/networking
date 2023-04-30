#!/bin/bash

set -e

shutdown() {
  echo "Shutting down"
  exit 0
}

trap 'shutdown' SIGTERM

mkdir /out

# Run twice to setup both IPv4 and IPv6, no idea better
# If ran using `-w 6` or `-6`, it hangs
# If ran once, only IPv6 is set up on the first run
dhcpcd -1 -B -t 5 eth0 &>> /out/dhcpcd.log
sleep 1
dhcpcd -1 -4 -B -t 5 eth0 &>> /out/dhcpcd.log
sleep 3

ip addr show dev eth0 | grep inet | awk '{print $2}' > /out/addresses
echo "Done"
