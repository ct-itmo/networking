# Компьютерные сети

См. также: [инструкция для Quirck](https://github.com/ct-itmo/quirck/tree/master/README.md)

## Запуск

* Подготовьте Quirck
* `python -m quirck`
* `python -m networking.core.socket`

## Конфигурация

Добавьте в `.env`:

```
SECRET_SEED=...
SOCKET_PATH=/path/to/networking.sock
EXTERNAL_BASE_URL=http://localhost:12003

DNS_REGEXP_IP=^SECRET$
DNS_REGEXP_SERVERS=^SECRET$

SCOREBOARD_TOKEN=1234
```
