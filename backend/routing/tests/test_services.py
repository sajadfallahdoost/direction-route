import types
from routing.services import geocoding, osrm_client


class DummyResponse:
	def __init__(self, status_code=200, json_data=None, text=''):
		self.status_code = status_code
		self._json = json_data or {}
	self.text = text

	def json(self):
		return self._json

	def raise_for_status(self):
		if not (200 <= self.status_code < 300):
			raise Exception(f"HTTP {self.status_code}")


def test_geocode_success(monkeypatch):
	def fake_get(url, headers=None, params=None, timeout=None):
		return DummyResponse(200, [{"display_name": "Tehran", "lat": "35.6892", "lon": "51.3890"}])

	monkeypatch.setattr(geocoding.requests, "get", fake_get)
	results = geocoding.geocode("Tehran", limit=1)
	assert results and results[0]["display_name"] == "Tehran"


def test_route_success(monkeypatch):
	def fake_get(url, params=None, timeout=None):
		return DummyResponse(200, {
			"routes": [{
				"distance": 1000.0,
				"duration": 120.0,
				"geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}
			}]
		})

	monkeypatch.setattr(osrm_client.requests, "get", fake_get)
	data = osrm_client.route(35.0, 51.0, 35.1, 51.1)
	assert "routes" in data and data["routes"]


