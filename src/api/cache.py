"""API 缓存层

两层缓存：
1. 数据缓存：MySQL 查询结果（stores, monthly_metrics 等），TTL 5 分钟
2. 结果缓存：API 计算结果（pipeline, allocation 等），TTL 3 分钟
"""

import time
from typing import Any


class TTLCache:
    """简单的 TTL 缓存"""

    def __init__(self, ttl_seconds: int = 300):
        self._store: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.time() - ts > self._ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any):
        self._store[key] = (time.time(), value)

    def invalidate(self, key: str | None = None):
        if key:
            self._store.pop(key, None)
        else:
            self._store.clear()

    def stats(self) -> dict:
        now = time.time()
        valid = sum(1 for ts, _ in self._store.values() if now - ts <= self._ttl)
        return {"total_keys": len(self._store), "valid_keys": valid, "ttl": self._ttl}


# 全局缓存实例
data_cache = TTLCache(ttl_seconds=300)    # 数据缓存 5 分钟
result_cache = TTLCache(ttl_seconds=180)  # 结果缓存 3 分钟
