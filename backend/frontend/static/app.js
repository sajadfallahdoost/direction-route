/* global ol */

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
	console.log('DOM loaded, initializing app...');
	
	// Initialize map centered on Tehran
	const map = new ol.Map({
		target: 'map',
		layers: [
			new ol.layer.Tile({
				source: new ol.source.OSM()
			})
		],
		view: new ol.View({
			center: ol.proj.fromLonLat([51.3890, 35.6892]),
			zoom: 11
		})
	});

	// Vector layers for markers and routes
	const vectorSource = new ol.source.Vector();
	const vectorLayer = new ol.layer.Vector({ 
		source: vectorSource,
		zIndex: 10
	});

	const routeSource = new ol.source.Vector();
	const routeLayer = new ol.layer.Vector({ 
		source: routeSource,
		zIndex: 5
	});

	map.addLayer(routeLayer);
	map.addLayer(vectorLayer);

	// UI Elements - با بررسی null safety
	const originInput = document.getElementById('origin');
	const destinationInputs = Array.from(document.querySelectorAll('[data-destination-input]'));
	const rankBtn = document.getElementById('rankBtn');
	const rankingList = document.getElementById('rankingList');
	const rankingPanel = document.getElementById('rankingPanel');
	const statusMessage = document.getElementById('statusMessage');
	const loadingOverlay = document.getElementById('loadingOverlay');
	
	// بررسی وجود المنت‌های ضروری
	if (!originInput || !rankBtn || !rankingList || !rankingPanel || !statusMessage || !loadingOverlay) {
		console.error('برخی المنت‌های ضروری یافت نشدند!');
		console.log({
			originInput: !!originInput,
			rankBtn: !!rankBtn,
			rankingList: !!rankingList,
			rankingPanel: !!rankingPanel,
			statusMessage: !!statusMessage,
			loadingOverlay: !!loadingOverlay
		});
		return;
	}
	
	console.log('همه المنت‌ها با موفقیت یافت شدند ✓');

	// State
	let originCoord = null;
	const destinationCoords = new Array(destinationInputs.length).fill(null);

	// Color palette for routes (rank 1 to 4)
	const routeColors = [
		'#22c55e', // Green - Rank 1 (closest)
		'#eab308', // Yellow - Rank 2
		'#a855f7', // Purple - Rank 3
		'#f97316'  // Orange - Rank 4
	];

	// Persian number conversion
	function toPersianNumber(num) {
		const persianDigits = '۰۱۲۳۴۵۶۷۸۹';
		return String(num).replace(/\d/g, digit => persianDigits[digit]);
	}

	// Geocoding function
	async function geocode(q) {
		const r = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`);
		const data = await r.json();
		if (data.error) {
			throw new Error(`خطا در جستجو: ${data.error}`);
		}
		const results = data.results || [];
		return results.map(r => ({
			display_name: r.display_name,
			lat: parseFloat(r.lat),
			lon: parseFloat(r.lon),
		}));
	}

	// Add marker to map
	function addMarker(lon, lat, color = '#ef4444', label = '') {
		const feat = new ol.Feature({
			geometry: new ol.geom.Point(ol.proj.fromLonLat([lon, lat])),
			name: label
		});
		
		const style = new ol.style.Style({
			image: new ol.style.Circle({
				radius: 8,
				fill: new ol.style.Fill({ color }),
				stroke: new ol.style.Stroke({ color: '#fff', width: 3 })
			})
		});
		
		if (label) {
			style.setText(new ol.style.Text({
				text: label,
				offsetY: -20,
				font: 'bold 14px Arial',
				fill: new ol.style.Fill({ color: '#fff' }),
				stroke: new ol.style.Stroke({ color: '#000', width: 3 }),
				backgroundFill: new ol.style.Fill({ color: color + 'dd' }),
				backgroundStroke: new ol.style.Stroke({ color: '#fff', width: 2 }),
				padding: [4, 6, 2, 6]
			}));
		}
		
		feat.setStyle(style);
		vectorSource.addFeature(feat);
		return feat;
	}

	// Draw route on map
	function drawRoute(geometry, color, width = 4, rank = null) {
		if (!geometry) {
			console.warn('No geometry provided for route');
			return null;
		}
		
		let coords = [];
		
		// Handle different geometry formats
		if (geometry.coordinates && Array.isArray(geometry.coordinates)) {
			// GeoJSON format: coordinates is array of [lon, lat] pairs
			coords = geometry.coordinates.map(coord => {
				if (Array.isArray(coord) && coord.length >= 2) {
					return ol.proj.fromLonLat([coord[0], coord[1]]);
				}
				return null;
			}).filter(c => c !== null);
		} else if (Array.isArray(geometry)) {
			// Direct array format
			coords = geometry.map(coord => {
				if (Array.isArray(coord) && coord.length >= 2) {
					return ol.proj.fromLonLat([coord[0], coord[1]]);
				}
				return null;
			}).filter(c => c !== null);
		}
		
		if (coords.length < 2) {
			console.warn('Invalid route geometry - not enough coordinates:', geometry);
			return null;
		}
		
		console.log(`Drawing route with ${coords.length} coordinates, rank: ${rank}`);
		
		const routeLine = new ol.Feature({
			geometry: new ol.geom.LineString(coords)
		});
		
		// Thicker line for rank 1
		const lineWidth = rank === 1 ? width + 2 : width;
		
		routeLine.setStyle([
			// Outer white border
			new ol.style.Style({
				stroke: new ol.style.Stroke({
					color: '#fff',
					width: lineWidth + 4,
					lineCap: 'round',
					lineJoin: 'round'
				})
			}),
			// Main colored line
			new ol.style.Style({
				stroke: new ol.style.Stroke({
					color: color,
					width: lineWidth,
					lineCap: 'round',
					lineJoin: 'round'
				})
			})
		]);
		
		routeSource.addFeature(routeLine);
		return routeLine;
	}

	// Handle geocoding for an input
	async function handleGeocode(inputEl, assignFn) {
		const q = inputEl.value.trim();
		if (!q) return null;
		
		try {
			const results = await geocode(q);
			if (results.length === 0) {
				showStatus('هیچ نتیجه‌ای یافت نشد', 'error');
				return null;
			}
			const top = results[0];
			assignFn([top.lat, top.lon]);
			map.getView().animate({ 
				center: ol.proj.fromLonLat([top.lon, top.lat]), 
				zoom: 13,
				duration: 500
			});
			return [top.lat, top.lon];
		} catch (err) {
			showStatus(err.message, 'error');
			throw err;
		}
	}

	// Build payload for ranking API
	function buildPayload() {
		return {
			origin: {
				label: originInput.value.trim() || 'مبدأ',
				lat: originCoord[0],
				lon: originCoord[1],
			},
			destinations: destinationCoords.map((coord, idx) => ({
				label: destinationInputs[idx].value.trim() || `مقصد ${toPersianNumber(idx + 1)}`,
				lat: coord[0],
				lon: coord[1],
			}))
		};
	}

	// Request ranking from API
	async function requestRanking() {
		const payload = buildPayload();
		console.log('Sending payload:', payload);
		
		const resp = await fetch('/api/rank-destinations', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload)
		});
		
		if (!resp.ok) {
			const errorData = await resp.json().catch(() => ({}));
			const msg = errorData.error || `درخواست با خطا مواجه شد (کد ${resp.status})`;
			throw new Error(msg);
		}
		return resp.json();
	}

	// Show status message
	function showStatus(message, type = 'info') {
		if (!statusMessage) {
			console.warn('statusMessage element not found');
			return;
		}
		
		statusMessage.textContent = message;
		statusMessage.className = `status-message status-${type}`;
		statusMessage.style.display = 'block';
		
		if (type === 'success' || type === 'error') {
			setTimeout(() => {
				statusMessage.style.display = 'none';
			}, 5000);
		}
	}

	// Show/hide loading overlay
	function setLoading(loading) {
		if (!loadingOverlay) {
			console.warn('loadingOverlay element not found');
			return;
		}
		loadingOverlay.style.display = loading ? 'flex' : 'none';
		if (rankBtn) {
			rankBtn.disabled = loading;
		}
	}

	// Persian order labels
	const persianOrderLabels = ['اول', 'دوم', 'سوم', 'چهارم'];
	
	// Render ranking results with optimal TSP route
	function renderRanking(data) {
		console.log('Rendering optimal route data:', data);
		
		vectorSource.clear();
		routeSource.clear();
		
		const added = [];
		
		// Add origin marker
		if (data.origin) {
			added.push(addMarker(data.origin.lon, data.origin.lat, '#ef4444', 'مبدأ'));
		}
		
		const listItems = [];
		const rankedDests = data.ranked_destinations || [];
		const optimalRoute = data.optimal_route || {};
		
		// Add total route summary at top
		if (optimalRoute.total_distance_km !== undefined) {
			const totalKm = toPersianNumber(optimalRoute.total_distance_km.toFixed(2));
			const totalMin = toPersianNumber(optimalRoute.total_duration_min.toFixed(1));
			listItems.push(`
				<li class="ranking-item total-summary">
					<div class="rank-badge" style="background-color: #3b82f6">
						📊
					</div>
					<div class="rank-details">
						<div class="rank-label" style="font-weight: 700">مسیر بهینه (کل)</div>
						<div class="rank-stats">
							<span class="stat">
								<span class="stat-icon">📏</span>
								${totalKm} کیلومتر
							</span>
							<span class="stat">
								<span class="stat-icon">⏱️</span>
								${totalMin} دقیقه
							</span>
						</div>
					</div>
				</li>
			`);
		}
		
		// Draw routes and markers for each leg in optimal order
		rankedDests.forEach((dest, idx) => {
			const color = routeColors[idx % routeColors.length];
			const rank = dest.rank;
			const leg = dest.leg || {};
			
			console.log(`Processing leg ${rank}:`, leg.from, '→', dest.label, 'has geometry:', !!leg.geometry);
			
			// Draw route for this leg
			if (leg.geometry) {
				const route = drawRoute(leg.geometry, color, 4, rank);
				if (route) {
					console.log(`✓ Route leg drawn: ${leg.from} → ${dest.label}`);
				}
			} else {
				console.warn(`✗ No geometry for leg: ${leg.from} → ${dest.label}`);
			}
			
			// Add destination marker
			const rankLabel = toPersianNumber(rank);
			added.push(addMarker(dest.lon, dest.lat, color, rankLabel));
			
			// Format distance and duration for this leg
			const km = leg.distance_km?.toFixed ? leg.distance_km.toFixed(2) : (leg.distance_m / 1000).toFixed(2);
			const minutes = leg.duration_min?.toFixed ? leg.duration_min.toFixed(1) : (leg.duration_s / 60).toFixed(1);
			
			// Create list item showing the leg
			const orderLabel = persianOrderLabels[idx] || rankLabel;
			const priorityLabel = rank === 1 ? '(ایستگاه اول)' : '';
			listItems.push(`
				<li class="ranking-item rank-${rank}">
					<div class="rank-badge" style="background-color: ${color}">
						${rankLabel}
					</div>
					<div class="rank-details">
						<div class="rank-label">
							<strong>${orderLabel}:</strong> ${dest.label} 
							<span class="priority-label">${priorityLabel}</span>
						</div>
						<div class="rank-sublabel">از ${leg.from}</div>
						<div class="rank-stats">
							<span class="stat">
								<span class="stat-icon">📏</span>
								${toPersianNumber(km)} کیلومتر
							</span>
							<span class="stat">
								<span class="stat-icon">⏱️</span>
								${toPersianNumber(minutes)} دقیقه
							</span>
						</div>
					</div>
				</li>
			`);
		});
		
		if (rankingList) {
			rankingList.innerHTML = listItems.join('');
		}
		
		if (rankingPanel) {
			rankingPanel.style.display = 'block';
		}
		
		// Fit map to show all markers
		if (added.length > 0) {
			const extent = added.reduce((acc, feature) => {
				const geomExtent = feature.getGeometry().getExtent();
				if (!acc) {
					return ol.extent.clone(geomExtent);
				}
				return ol.extent.extend(acc, geomExtent);
			}, null);
			if (extent) {
				map.getView().fit(extent, { 
					padding: [100, 100, 100, 100], 
					duration: 800,
					maxZoom: 14
				});
			}
		}
	}

	// Event listeners
	originInput.addEventListener('change', () => {
		handleGeocode(originInput, v => originCoord = v).catch(() => {});
	});

	destinationInputs.forEach((input, idx) => {
		input.addEventListener('change', () => {
			handleGeocode(input, coords => {
				destinationCoords[idx] = coords;
			}).catch(() => {});
		});
	});

	rankBtn.addEventListener('click', async () => {
		console.log('🚗 Button clicked!');
		console.log('Current state:', {
			originCoord,
			destinationCoords,
			originValue: originInput.value,
			destValues: destinationInputs.map(i => i.value)
		});
		
		// Auto-geocode inputs that haven't been processed yet
		if (!originCoord && originInput.value.trim()) {
			console.log('⏳ Auto-geocoding origin...');
			try {
				const result = await handleGeocode(originInput, v => originCoord = v);
				console.log('Origin geocoding result:', result);
				if (!result) {
					showStatus('خطا در پیدا کردن مبدأ. لطفاً دوباره تلاش کنید.', 'error');
					return;
				}
			} catch (err) {
				console.error('Geocode origin error:', err);
				showStatus('خطا در پیدا کردن مبدأ: ' + err.message, 'error');
				return;
			}
		}
		
		for (let i = 0; i < destinationInputs.length; i += 1) {
			if (!destinationCoords[i] && destinationInputs[i].value.trim()) {
				console.log(`⏳ Auto-geocoding destination ${i + 1}...`);
				try {
					const result = await handleGeocode(destinationInputs[i], coords => {
						destinationCoords[i] = coords;
					});
					console.log(`Destination ${i + 1} geocoding result:`, result);
					if (!result) {
						showStatus(`خطا در پیدا کردن مقصد ${i + 1}. لطفاً دوباره تلاش کنید.`, 'error');
						return;
					}
				} catch (err) {
					console.error(`Geocode destination ${i + 1} error:`, err);
					showStatus(`خطا در پیدا کردن مقصد ${i + 1}: ` + err.message, 'error');
					return;
				}
			}
		}
		
		console.log('✅ After auto-geocoding:', {
			originCoord,
			destinationCoords
		});
		
		// Validate inputs
		if (!originCoord) {
			console.log('❌ Validation failed: No origin');
			showStatus('لطفاً مبدأ را وارد کنید', 'error');
			originInput.focus();
			return;
		}
		
		const emptyDestinations = destinationCoords.filter(coord => !coord);
		if (emptyDestinations.length > 0) {
			console.log('❌ Validation failed: Missing destinations', emptyDestinations.length);
			showStatus('لطفاً همه ۴ مقصد را وارد کنید', 'error');
			const firstEmpty = destinationCoords.findIndex(coord => !coord);
			destinationInputs[firstEmpty].focus();
			return;
		}
		
		console.log('✅ Validation passed!');
		
		// Request ranking
		setLoading(true);
		showStatus('در حال محاسبه مسیرها...', 'info');
		
		try {
			console.log('📡 Requesting ranking from API...');
			const data = await requestRanking();
			console.log('✅ Ranking response received:', data);
			renderRanking(data);
			showStatus('محاسبه مسیرها با موفقیت انجام شد ✓', 'success');
		} catch (err) {
			console.error('❌ Ranking error:', err);
			showStatus(`خطا: ${err.message}`, 'error');
			if (rankingPanel) {
				rankingPanel.style.display = 'none';
			}
		} finally {
			setLoading(false);
		}
	});

	// Add popup on marker click
	const popup = new ol.Overlay({
		element: document.createElement('div'),
		positioning: 'bottom-center',
		stopEvent: false,
		offset: [0, -10]
	});
	popup.getElement().className = 'map-popup';
	map.addOverlay(popup);

	map.on('click', function(evt) {
		const feature = map.forEachFeatureAtPixel(evt.pixel, function(feature) {
			return feature;
		});
		
		if (feature && feature.get('name')) {
			const coords = feature.getGeometry().getCoordinates();
			popup.setPosition(coords);
			popup.getElement().innerHTML = `<div class="popup-content">${feature.get('name')}</div>`;
			popup.getElement().style.display = 'block';
		} else {
			popup.getElement().style.display = 'none';
		}
	});
	
	console.log('✅ App initialized successfully!');
});
