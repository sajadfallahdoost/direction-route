from typing import Any, Dict, List
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_GET
from django.conf import settings
from .services import geocoding, osrm_client

_last_geocode_by_ip = {}


def _parse_latlon(param: str) -> List[float]:
	parts = [p.strip() for p in param.split(",")]
	if len(parts) != 2:
		raise ValueError("expected 'lat,lon'")
	lat = float(parts[0])
	lon = float(parts[1])
	if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
		raise ValueError("invalid coordinate range")
	return [lat, lon]


@require_GET
def geocode_view(request: HttpRequest):
	q = request.GET.get("q", "").strip()
	limit = int(request.GET.get("limit", "5"))
	if not q:
		return JsonResponse({"results": []})
	# naive throttle: 1 request / 0.5s per IP
	import time
	ip = request.META.get("REMOTE_ADDR", "unknown")
	now = time.time()
	last = _last_geocode_by_ip.get(ip, 0)
	if now - last < 0.5:
		return JsonResponse({"results": [], "throttled": True}, status=429)
	_last_geocode_by_ip[ip] = now
	candidates = geocoding.geocode(q, limit=limit)
	return JsonResponse({"results": candidates})


@require_GET
def route_view(request: HttpRequest):
	origin = request.GET.get("origin", "")
	destination = request.GET.get("destination", "")
	profile = request.GET.get("profile", "car")
	overview = request.GET.get("overview", "full")
	try:
		orig_lat, orig_lon = _parse_latlon(origin)
		dest_lat, dest_lon = _parse_latlon(destination)
	except Exception as e:
		return JsonResponse({"error": str(e)}, status=400)

	try:
		data = osrm_client.route(orig_lat, orig_lon, dest_lat, dest_lon, profile=profile, overview=overview)
	except Exception as e:
		return JsonResponse({"error": str(e)}, status=502)

	# Summarize top route
	route = None
	if data.get("routes"):
		route = data["routes"][0]

	result: Dict[str, Any] = {
		"raw": data,
		"summary": None,
	}
	if route:
		result["summary"] = {
			"distance_m": route.get("distance"),
			"duration_s": route.get("duration"),
			"bbox": route.get("bbox"),
		}
	return JsonResponse(result)


