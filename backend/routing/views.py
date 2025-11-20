from typing import Any, Dict, List, Union
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from .services import geocoding, osrm_client, tsp_solver
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


def _normalize_point(value: Union[str, Dict[str, Any]], fallback_label: str) -> Dict[str, Any]:
	"""
	Accept a 'lat,lon' string or a {lat, lon, label?} dict and return a normalized point dict.
	"""
	if isinstance(value, str):
		lat, lon = _parse_latlon(value)
		label = fallback_label
	elif isinstance(value, dict):
		if "lat" not in value or "lon" not in value:
			raise ValueError("point dict must include 'lat' and 'lon'")
		try:
			lat = float(value["lat"])
			lon = float(value["lon"])
		except (TypeError, ValueError) as exc:
			raise ValueError("invalid coordinate values") from exc
		label = value.get("label") or value.get("name") or fallback_label
		if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
			raise ValueError("invalid coordinate range")
	else:
		raise ValueError("point must be a 'lat,lon' string or an object with 'lat' and 'lon'")
	return {
		"label": label,
		"lat": lat,
		"lon": lon,
	}


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


@extend_schema(
	summary="Calculate optimal route order for multiple destinations (TSP)",
	description="Accepts an origin and exactly four destinations, uses TSP algorithm to find the optimal visiting order that minimizes total travel distance. Returns destinations in optimal visit order with leg-by-leg route details.",
	tags=["Routing"],
	request={
		"application/json": {
			"type": "object",
			"properties": {
				"origin": {"type": "object"},
				"destinations": {"type": "array", "items": {"type": "object"}},
				"profile": {"type": "string", "default": "car"},
				"return_to_origin": {"type": "boolean", "default": False}
			},
			"required": ["origin", "destinations"]
		}
	},
	responses={
		200: {
			"description": "Optimal route with destinations in visit order",
			"examples": {
				"application/json": {
					"origin": {"label": "Depot", "lat": 35.7, "lon": 51.4},
					"profile": "car",
					"optimal_route": {
						"total_distance_m": 15420.5,
						"total_distance_km": 15.421,
						"total_duration_s": 2340.5,
						"total_duration_min": 39.01,
						"return_to_origin": False
					},
					"ranked_destinations": [
						{
							"rank": 1,
							"label": "Stop A",
							"lat": 35.72,
							"lon": 51.42,
							"leg": {
								"from": "Depot",
								"distance_m": 3200.0,
								"distance_km": 3.2,
								"duration_s": 480.0,
								"duration_min": 8.0,
								"geometry": {"type": "LineString", "coordinates": [[51.4, 35.7], [51.42, 35.72]]}
							}
						},
						{
							"rank": 2,
							"label": "Stop C",
							"lat": 35.68,
							"lon": 51.38,
							"leg": {
								"from": "Stop A",
								"distance_m": 4100.0,
								"distance_km": 4.1,
								"duration_s": 620.0,
								"duration_min": 10.33,
								"geometry": {"type": "LineString", "coordinates": [[51.42, 35.72], [51.38, 35.68]]}
							}
						}
					],
					"count": 4
				}
			}
		},
		400: {
			"description": "Invalid payload",
			"examples": {
				"application/json": {"error": "origin is required"}
			}
		},
		502: {
			"description": "Routing service error",
			"examples": {
				"application/json": {"error": "Failed to calculate optimal route: OSRM unavailable"}
			}
		}
	}
)
@csrf_exempt
@api_view(['POST'])
def rank_destinations_view(request):
	"""
	Calculate optimal route order using TSP algorithm with OSRM.
	
	This endpoint uses the Traveling Salesman Problem (TSP) algorithm to find
	the optimal order to visit 4 destinations from an origin, minimizing total
	travel distance. It returns destinations in the optimal visit order with
	detailed route information for each leg.
	"""
	payload = request.data or {}
	origin_payload = payload.get("origin")
	destinations_payload = payload.get("destinations") or []
	profile = payload.get("profile", "car")
	return_to_origin = payload.get("return_to_origin", False)

	if not origin_payload:
		return Response({"error": "origin is required"}, status=status.HTTP_400_BAD_REQUEST)
	if not isinstance(destinations_payload, list) or len(destinations_payload) == 0:
		return Response({"error": "destinations must be a non-empty list"}, status=status.HTTP_400_BAD_REQUEST)
	if len(destinations_payload) != 4:
		return Response({"error": "Exactly four destinations are required"}, status=status.HTTP_400_BAD_REQUEST)

	try:
		origin = _normalize_point(origin_payload, "Origin")
	except ValueError as exc:
		return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

	parsed_destinations: List[Dict[str, Any]] = []
	for idx, dest in enumerate(destinations_payload, 1):
		try:
			parsed_destinations.append(_normalize_point(dest, f"Destination {idx}"))
		except ValueError as exc:
			return Response({"error": f"destination {idx}: {exc}"}, status=status.HTTP_400_BAD_REQUEST)

	# Use TSP solver to find optimal route
	try:
		result = tsp_solver.solve_tsp_route(
			origin=origin,
			destinations=parsed_destinations,
			profile=profile,
			return_to_origin=return_to_origin
		)
	except Exception as exc:
		return Response(
			{"error": f"Failed to calculate optimal route: {exc}"},
			status=status.HTTP_502_BAD_GATEWAY
		)

	return Response({
		"origin": origin,
		"profile": profile,
		"optimal_route": result["optimal_route"],
		"ranked_destinations": result["ranked_destinations"],
		"count": len(result["ranked_destinations"]),
	}, status=status.HTTP_200_OK)


