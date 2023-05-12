#!/bin/bash

set -e

if [[ -v IP4 ]]; then
    ip addr add $IP4/24 dev eth0
fi

if [[ -v IP6 ]]; then
    ip addr add $IP6/64 dev eth0
fi

sed -i 's/$DOMAIN/'"$DOMAIN"'/g' /etc/nginx/nginx.conf

sleep 1

exec nginx -g 'daemon off;'
