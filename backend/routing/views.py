from typing import Any, Dict, List
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from .services import geocoding, osrm_client
from .services.geocoding import GeocodingServiceError

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


@extend_schema(
	summary="Geocode an address or location name",
	description="Search for locations using Nominatim geocoding service. Returns a list of matching locations with coordinates and address details.",
	tags=["Geocoding"],
	parameters=[
		OpenApiParameter(
			name="q",
			type=OpenApiTypes.STR,
			location=OpenApiParameter.QUERY,
			required=True,
			description="Search query (e.g., 'Tehran, Sa'adat Abad' or 'Azadi Tower')",
			examples=[
				OpenApiExample(
					"Example 1",
					value="Tehran, Sa'adat Abad"
				),
				OpenApiExample(
					"Example 2",
					value="Azadi Tower"
				),
			],
		),
		OpenApiParameter(
			name="limit",
			type=OpenApiTypes.INT,
			location=OpenApiParameter.QUERY,
			required=False,
			description="Maximum number of results to return (default: 5)",
			default=5,
		),
	],
	responses={
		200: {
			"description": "List of geocoding results",
			"examples": {
				"application/json": {
					"results": [
						{
							"place_id": 123456,
							"lat": "35.6892",
							"lon": "51.3890",
							"display_name": "Tehran, Iran",
							"address": {
								"city": "Tehran",
								"country": "Iran"
							}
						}
					]
				}
			}
		},
		429: {
			"description": "Request throttled (too many requests)",
			"examples": {
				"application/json": {
					"results": [],
					"throttled": True
				}
			}
		}
	}
)
@api_view(['GET'])
def geocode_view(request):
	"""
	Geocode an address or location name.
	
	This endpoint searches for locations using the Nominatim geocoding service.
	It includes basic rate limiting (1 request per 0.5 seconds per IP address).
	"""
	q = request.GET.get("q", "").strip()
	limit = int(request.GET.get("limit", "5"))
	if not q:
		return Response({"results": []}, status=status.HTTP_200_OK)
	
	# naive throttle: 1 request / 0.5s per IP
	import time
	ip = request.META.get("REMOTE_ADDR", "unknown")
	now = time.time()
	last = _last_geocode_by_ip.get(ip, 0)
	if now - last < 0.5:
		return Response({"results": [], "throttled": True}, status=status.HTTP_429_TOO_MANY_REQUESTS)
	_last_geocode_by_ip[ip] = now
	
	try:
		candidates = geocoding.geocode(q, limit=limit)
	except GeocodingServiceError as exc:
		return Response(
			{"results": [], "error": str(exc)},
			status=status.HTTP_502_BAD_GATEWAY
		)
	return Response({"results": candidates}, status=status.HTTP_200_OK)


@extend_schema(
	summary="Calculate a route between two coordinates",
	description="Calculate a route between origin and destination coordinates using OSRM routing service. Returns route geometry, distance, duration, and bounding box.",
	tags=["Routing"],
	parameters=[
		OpenApiParameter(
			name="origin",
			type=OpenApiTypes.STR,
			location=OpenApiParameter.QUERY,
			required=True,
			description="Origin coordinates in format 'lat,lon' (e.g., '35.6892,51.3890')",
			examples=[
				OpenApiExample(
					"Example 1",
					value="35.6892,51.3890"
				),
			],
		),
		OpenApiParameter(
			name="destination",
			type=OpenApiTypes.STR,
			location=OpenApiParameter.QUERY,
			required=True,
			description="Destination coordinates in format 'lat,lon' (e.g., '35.6997,51.3381')",
			examples=[
				OpenApiExample(
					"Example 1",
					value="35.6997,51.3381"
				),
			],
		),
		OpenApiParameter(
			name="profile",
			type=OpenApiTypes.STR,
			location=OpenApiParameter.QUERY,
			required=False,
			description="Routing profile (default: 'car'). Options: 'car', 'bike', 'foot'",
			default="car",
		),
		OpenApiParameter(
			name="overview",
			type=OpenApiTypes.STR,
			location=OpenApiParameter.QUERY,
			required=False,
			description="Route overview level (default: 'full'). Options: 'simplified', 'full', 'false'",
			default="full",
		),
	],
	responses={
		200: {
			"description": "Route calculation result",
			"examples": {
				"application/json": {
					"raw": {
						"routes": [
							{
								"distance": 12345.6,
								"duration": 1800.5,
								"geometry": {"type": "LineString", "coordinates": [[51.3890, 35.6892], [51.3381, 35.6997]]},
								"bbox": [51.3381, 35.6892, 51.3890, 35.6997]
							}
						]
					},
					"summary": {
						"distance_m": 12345.6,
						"duration_s": 1800.5,
						"bbox": [51.3381, 35.6892, 51.3890, 35.6997]
					}
				}
			}
		},
		400: {
			"description": "Invalid request parameters",
			"examples": {
				"application/json": {
					"error": "expected 'lat,lon'"
				}
			}
		},
		502: {
			"description": "OSRM service error",
			"examples": {
				"application/json": {
					"error": "OSRM service unavailable"
				}
			}
		}
	}
)
@api_view(['GET'])
def route_view(request):
	"""
	Calculate a route between two coordinates.
	
	This endpoint uses OSRM to calculate the optimal route between origin and destination.
	Returns detailed route information including geometry, distance, duration, and bounding box.
	"""
	origin = request.GET.get("origin", "")
	destination = request.GET.get("destination", "")
	profile = request.GET.get("profile", "car")
	overview = request.GET.get("overview", "full")
	
	try:
		orig_lat, orig_lon = _parse_latlon(origin)
		dest_lat, dest_lon = _parse_latlon(destination)
	except Exception as e:
		return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

	try:
		data = osrm_client.route(orig_lat, orig_lon, dest_lat, dest_lon, profile=profile, overview=overview)
	except Exception as e:
		return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

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
	return Response(result, status=status.HTTP_200_OK)


