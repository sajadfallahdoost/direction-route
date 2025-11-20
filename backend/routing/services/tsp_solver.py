import logging
from typing import Any, Dict, List
from itertools import permutations
from . import osrm_client

logger = logging.getLogger(__name__)


def solve_tsp_route(
	origin: Dict[str, Any],
	destinations: List[Dict[str, Any]],
	profile: str = "car",
	return_to_origin: bool = False
) -> Dict[str, Any]:
	"""
	Solve the Traveling Salesman Problem for an origin and 4 destinations.
	
	Uses brute force approach to find the optimal order to visit all destinations.
	
	Args:
		origin: Dict with 'lat', 'lon', 'label' keys
		destinations: List of 4 dicts with 'lat', 'lon', 'label' keys
		profile: Routing profile (car, bike, foot)
		return_to_origin: Whether to return to origin after visiting all destinations
		
	Returns:
		Dict containing:
			- optimal_route: total distance and duration info
			- ranked_destinations: destinations in optimal visit order with leg details
	"""
	if len(destinations) != 4:
		raise ValueError("Exactly 4 destinations are required for TSP solving")
	
	# Step 1: Collect all points (origin + 4 destinations)
	all_points = [origin] + destinations
	coordinates = [(p["lat"], p["lon"]) for p in all_points]
	
	# Step 2: Get distance/time matrix from OSRM Table API
	try:
		table_data = osrm_client.table(coordinates, profile=profile)
	except Exception as exc:
		logger.error(f"OSRM Table API failed: {exc}")
		raise Exception(f"Failed to get distance matrix: {exc}")
	
	durations = table_data.get("durations")
	distances = table_data.get("distances")
	
	if not durations or not distances:
		raise Exception("Invalid response from OSRM Table API")
	
	# Step 3: Generate all permutations of destination indices (1, 2, 3, 4)
	# Origin is at index 0
	dest_indices = list(range(1, 5))  # [1, 2, 3, 4]
	
	best_cost = float('inf')
	best_order = None
	best_total_distance = None
	best_total_duration = None
	
	# Step 4: Evaluate each permutation
	for perm in permutations(dest_indices):
		# Calculate route: origin -> dest[perm[0]] -> dest[perm[1]] -> dest[perm[2]] -> dest[perm[3]]
		route_indices = [0] + list(perm)
		if return_to_origin:
			route_indices.append(0)
		
		total_distance = 0
		total_duration = 0
		
		for i in range(len(route_indices) - 1):
			from_idx = route_indices[i]
			to_idx = route_indices[i + 1]
			total_distance += distances[from_idx][to_idx]
			total_duration += durations[from_idx][to_idx]
		
		# Use distance as cost metric (can be customized)
		cost = total_distance
		
		if cost < best_cost:
			best_cost = cost
			best_order = perm
			best_total_distance = total_distance
			best_total_duration = total_duration
	
	# Step 5: Get detailed route geometry for each leg of the optimal route
	ranked_destinations = []
	from_point = origin
	
	for rank, dest_idx in enumerate(best_order, 1):
		dest = destinations[dest_idx - 1]  # Convert from 1-based to 0-based
		
		# Get detailed route for this leg
		try:
			route_data = osrm_client.route(
				from_point["lat"], from_point["lon"],
				dest["lat"], dest["lon"],
				profile=profile,
				overview="full"
			)
			routes = route_data.get("routes", [])
			if routes:
				route0 = routes[0]
				leg_distance = route0.get("distance", 0)
				leg_duration = route0.get("duration", 0)
				leg_geometry = route0.get("geometry")
			else:
				# Fallback to table data
				from_idx = 0 if from_point == origin else best_order.index(dest_idx - 1) + 1
				leg_distance = distances[from_idx][dest_idx]
				leg_duration = durations[from_idx][dest_idx]
				leg_geometry = None
		except Exception as exc:
			logger.error(f"Failed to get leg route: {exc}")
			# Use table data as fallback
			from_idx = 0 if from_point == origin else list(best_order).index(dest_idx) + 1
			leg_distance = distances[from_idx][dest_idx]
			leg_duration = durations[from_idx][dest_idx]
			leg_geometry = None
		
		ranked_destinations.append({
			"rank": rank,
			"label": dest["label"],
			"lat": dest["lat"],
			"lon": dest["lon"],
			"leg": {
				"from": from_point["label"],
				"distance_m": leg_distance,
				"distance_km": round(leg_distance / 1000.0, 3),
				"duration_s": leg_duration,
				"duration_min": round(leg_duration / 60.0, 2),
				"geometry": leg_geometry
			}
		})
		
		from_point = dest
	
	# Step 6: Return structured result
	return {
		"optimal_route": {
			"total_distance_m": best_total_distance,
			"total_distance_km": round(best_total_distance / 1000.0, 3),
			"total_duration_s": best_total_duration,
			"total_duration_min": round(best_total_duration / 60.0, 2),
			"return_to_origin": return_to_origin
		},
		"ranked_destinations": ranked_destinations
	}

