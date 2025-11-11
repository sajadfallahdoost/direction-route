import logging
from typing import List, Dict, Any
import requests
from django.conf import settings
from .cache import TTLCache

logger = logging.getLogger(__name__)
_cache = TTLCache(ttl_seconds=getattr(settings, "CACHE_TTL_S", 300))


def geocode(query: str, limit: int = 5) -> List[Dict[str, Any]]:
	if not query or not query.strip():
		return []
	cache_key = f"geocode:{query}:{limit}"
	cached = _cache.get(cache_key)
	if cached is not None:
		return cached

	base = getattr(settings, "NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org")
	url = f"{base}/search"
	headers = {
		"User-Agent": getattr(settings, "USER_AGENT", "route-app/1.0"),
	}
	params = {
		"q": query,
		"format": "jsonv2",
		"addressdetails": 1,
		"limit": limit,
	}

	for attempt in range(3):
		resp = requests.get(url, headers=headers, params=params, timeout=getattr(settings, "HTTP_TIMEOUT_S", 10))
		if resp.status_code == 200:
			data = resp.json()
			_cache.set(cache_key, data)
			return data
		if resp.status_code in (429, 503):
			# Backoff
			import time
			time.sleep(1.5 * (attempt + 1))
			continue
		logger.warning("Geocoding error %s: %s", resp.status_code, resp.text[:200])
		break
	return []


