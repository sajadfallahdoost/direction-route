from rest_framework.test import APIClient
from routing.services import osrm_client


def test_rank_destinations_sorted(monkeypatch):
	client = APIClient()

	def fake_route(origin_lat, origin_lon, dest_lat, dest_lon, profile="car", overview="false"):
		# produce deterministic distance based on latitude ordering
		distance = (dest_lat - origin_lat) * 100000 + 1000
		if distance < 0:
			distance *= -1
		return {
			"routes": [{
				"distance": distance,
				"duration": distance / 10.0,
				"geometry": {"type": "LineString", "coordinates": []}
			}]
		}

	monkeypatch.setattr(osrm_client, "route", fake_route)

	payload = {
		"origin": {"label": "HQ", "lat": 35.70, "lon": 51.40},
		"destinations": [
			{"label": "Stop A", "lat": 35.71, "lon": 51.39},
			{"label": "Stop B", "lat": 35.72, "lon": 51.38},
			{"label": "Stop C", "lat": 35.75, "lon": 51.37},
			{"label": "Stop D", "lat": 35.80, "lon": 51.36},
		],
	}

	resp = client.post("/api/rank-destinations", data=payload, format="json")
	assert resp.status_code == 200
	data = resp.json()
	ranks = [item["label"] for item in data["ranked_destinations"]]
	assert ranks == ["Stop A", "Stop B", "Stop C", "Stop D"]
