FROM nginx

RUN apt-get update -q && apt-get install -qy --no-install-recommends iproute2 && rm -rf /var/lib/apt/lists/*

COPY nginx.conf /etc/nginx/nginx.conf
COPY start.sh /start.sh

CMD ["/start.sh"]
