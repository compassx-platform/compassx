import time


class ResultCache:
    def __init__(self, ttl_seconds: int = 3600):
        self._ttl = ttl_seconds
        self._items: dict[str, tuple[float, dict]] = {}

    def _key(self, sql_hash: str, warehouse_id: str) -> str:
        return f"{warehouse_id}:{sql_hash}"

    async def get(self, sql_hash: str, warehouse_id: str) -> dict | None:
        key = self._key(sql_hash, warehouse_id)
        item = self._items.get(key)
        if not item:
            return None
        expires_at, payload = item
        if expires_at < time.time():
            self._items.pop(key, None)
            return None
        # Empty catalog results become stale as soon as a table receives its
        # first data file. Never let an old empty response hide new data.
        if payload.get("rows_returned", 0) == 0:
            self._items.pop(key, None)
            return None
        return payload

    async def set(self, sql_hash: str, warehouse_id: str, payload: dict) -> None:
        self._items[self._key(sql_hash, warehouse_id)] = (time.time() + self._ttl, payload)

    async def invalidate(self, warehouse_id: str) -> None:
        prefix = f"{warehouse_id}:"
        for key in list(self._items):
            if key.startswith(prefix):
                self._items.pop(key, None)


result_cache = ResultCache()
