import logging
from typing import Any, Dict
import requests
from django.conf import settings
from .cache import TTLCache

logger = logging.getLogger(__name__)
_cache = TTLCache(ttl_seconds=getattr(settings, "CACHE_TTL_S", 300))


def route(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float, profile: str = "car",
          overview: str = "full") -> Dict[str, Any]:
	base = getattr(settings, "OSRM_BASE_URL", "http://localhost:5000")
	coords = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
	cache_key = f"route:{profile}:{coords}:{overview}"
	cached = _cache.get(cache_key)
	if cached is not None:
		return cached

	url = f"{base}/route/v1/{profile}/{coords}"
	params = {
		"overview": overview,
		"geometries": "geojson",
		"steps": "true",
		"annotations": "duration,distance",
	}
	resp = requests.get(url, params=params, timeout=getattr(settings, "HTTP_TIMEOUT_S", 10))
	resp.raise_for_status()
	data = resp.json()
	_cache.set(cache_key, data)
	return data


