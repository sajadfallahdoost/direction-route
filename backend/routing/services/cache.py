import time
from typing import Any, Dict, Tuple, Optional


class TTLCache:
	def __init__(self, ttl_seconds: int = 300, max_size: int = 1024):
		self._ttl = ttl_seconds
		self._max_size = max_size
		self._store: Dict[str, Tuple[float, Any]] = {}

	def _evict_if_needed(self):
		if len(self._store) <= self._max_size:
			return
		# Evict oldest
		oldest_key = min(self._store, key=lambda k: self._store[k][0])
		self._store.pop(oldest_key, None)

	def get(self, key: str) -> Optional[Any]:
		item = self._store.get(key)
		if not item:
			return None
		timestamp, value = item
		if time.time() - timestamp > self._ttl:
			self._store.pop(key, None)
			return None
		return value

	def set(self, key: str, value: Any):
		self._store[key] = (time.time(), value)
		self._evict_if_needed()


