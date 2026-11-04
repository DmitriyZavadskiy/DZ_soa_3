import logging

from google.protobuf import json_format
from redis.asyncio.sentinel import Sentinel

log = logging.getLogger("cache")


def flight_key(flight_id) -> str:
    return f"flight:{flight_id}"


def search_key(origin: str, destination: str, date: str | None) -> str:
    return f"search:{origin}:{destination}:{date or 'any'}"


class Cache:
    def __init__(self, sentinel_host: str, sentinel_port: int, master_name: str, ttl_seconds: int):
        sentinel = Sentinel([(sentinel_host, sentinel_port)], socket_timeout=1)
        self.redis = sentinel.master_for(master_name, socket_timeout=1, decode_responses=True)
        self.ttl = ttl_seconds

    async def get(self, key: str, message):
        raw = await self.redis.get(key)
        if raw is None:
            log.info("cache miss %s", key)
            return None
        log.info("cache hit %s", key)
        return json_format.Parse(raw, message)

    async def set(self, key: str, message) -> None:
        await self.redis.set(key, json_format.MessageToJson(message), ex=self.ttl)

    async def delete(self, *keys: str) -> None:
        await self.redis.delete(*keys)
        log.info("cache invalidated %s", " ".join(keys))
