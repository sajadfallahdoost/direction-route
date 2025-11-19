/* global ol */

const map = new ol.Map({
	target: 'map',
	layers: [
		new ol.layer.Tile({
			source: new ol.source.OSM()
		})
	],
	view: new ol.View({
		center: ol.proj.fromLonLat([51.3890, 35.6892]), // Tehran
		zoom: 11
	})
});

const vectorSource = new ol.source.Vector();
const vectorLayer = new ol.layer.Vector({ source: vectorSource });
map.addLayer(vectorLayer);

const originInput = document.getElementById('origin');
const destinationInput = document.getElementById('destination');
const routeBtn = document.getElementById('routeBtn');
const summarySpan = document.getElementById('summary');

let originCoord = null;
let destinationCoord = null;

async function geocode(q) {
	const r = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`);
	const data = await r.json();
	if (data.error) {
		alert(`Geocoding failed: ${data.error}`);
		return [];
	}
	const results = data.results || [];
	return results.map(r => ({
		display_name: r.display_name,
		lat: parseFloat(r.lat),
		lon: parseFloat(r.lon),
	}));
}

function addMarker(lon, lat, color = '#ef4444') {
	const feat = new ol.Feature({
		geometry: new ol.geom.Point(ol.proj.fromLonLat([lon, lat]))
	});
	feat.setStyle(new ol.style.Style({
		image: new ol.style.Circle({
			radius: 6,
			fill: new ol.style.Fill({ color }),
			stroke: new ol.style.Stroke({ color: '#fff', width: 2 })
		})
	}));
	vectorSource.addFeature(feat);
	return feat;
}

function drawRoute(geojson) {
	const format = new ol.format.GeoJSON();
	const feature = format.readFeature(geojson, {
		featureProjection: map.getView().getProjection()
	});
	feature.setStyle(new ol.style.Style({
		stroke: new ol.style.Stroke({
			color: '#22c55e',
			width: 4
		})
	}));
	vectorSource.addFeature(feature);
	// fit
	const extent = feature.getGeometry().getExtent();
	map.getView().fit(extent, { padding: [50, 50, 50, 50] });
}

async function route() {
	vectorSource.clear();
	if (originCoord) addMarker(originCoord[1], originCoord[0], '#ef4444');
	if (destinationCoord) addMarker(destinationCoord[1], destinationCoord[0], '#3b82f6');

	const query = new URLSearchParams({
		origin: `${originCoord[0]},${originCoord[1]}`,
		destination: `${destinationCoord[0]},${destinationCoord[1]}`,
		profile: 'car',
		overview: 'full'
	}).toString();
	const r = await fetch(`/api/route?${query}`);
	const data = await r.json();
	if (data && data.raw && data.raw.routes && data.raw.routes[0]) {
		const route0 = data.raw.routes[0];
		drawRoute(route0.geometry);
		const km = (route0.distance / 1000).toFixed(1);
		const min = (route0.duration / 60).toFixed(0);
		summarySpan.textContent = `${km} km, ${min} min`;
	} else {
		summarySpan.textContent = 'No route found';
	}
}

async function handleGeocode(inputEl, assignFn) {
	const q = inputEl.value.trim();
	if (!q) return;
	const results = await geocode(q);
	if (results.length === 0) return;
	const top = results[0];
	assignFn([top.lat, top.lon]);
	map.getView().animate({ center: ol.proj.fromLonLat([top.lon, top.lat]), zoom: 13 });
}

originInput.addEventListener('change', () => handleGeocode(originInput, v => originCoord = v));
destinationInput.addEventListener('change', () => handleGeocode(destinationInput, v => destinationCoord = v));
routeBtn.addEventListener('click', async () => {
	if (!originCoord || !destinationCoord) {
		alert('Please set both origin and destination.');
		return;
	}
	await route();
});


