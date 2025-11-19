import logging
import time
from typing import List, Dict, Any
import requests
from django.conf import settings
from .cache import TTLCache

logger = logging.getLogger(__name__)
_cache = TTLCache(ttl_seconds=getattr(settings, "CACHE_TTL_S", 300))


class GeocodingServiceError(Exception):
	"""Raised when the upstream geocoding provider fails."""


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
	email = getattr(settings, "NOMINATIM_EMAIL", "").strip()
	if email:
		params["email"] = email

	timeout = getattr(settings, "HTTP_TIMEOUT_S", 10)
	last_error = None
	for attempt in range(3):
		try:
			resp = requests.get(url, headers=headers, params=params, timeout=timeout)
		except requests.RequestException as exc:
			logger.warning("Geocoding request failed: %s", exc)
			last_error = str(exc)
			time.sleep(1.5 * (attempt + 1))
			continue

		if resp.status_code == 200:
			data = resp.json()
			_cache.set(cache_key, data)
			return data

		if resp.status_code in (429, 503):
			logger.info("Geocoding rate limited (%s), backing off...", resp.status_code)
			time.sleep(1.5 * (attempt + 1))
			continue

		message = resp.text[:200]
		logger.warning("Geocoding error %s: %s", resp.status_code, message)
		if resp.status_code == 403:
			raise GeocodingServiceError("Geocoding provider blocked our requests (HTTP 403). Update USER_AGENT or configure your own Nominatim instance.")
		raise GeocodingServiceError(f"Geocoding provider error (HTTP {resp.status_code}).")

	raise GeocodingServiceError(f"Geocoding provider unavailable after retries: {last_error or 'unknown error'}.")


