DATA_DIR := $(CURDIR)/data
PBF_URL  := https://download.geofabrik.de/asia/iran-latest.osm.pbf
PBF_FILE := $(DATA_DIR)/iran.osm.pbf
OSRM    := $(DATA_DIR)/iran.osrm
PROFILE := /opt/car.lua

.PHONY: all download extract partition customize routed clean

all: download extract partition customize

$(DATA_DIR):
	mkdir -p $(DATA_DIR)

download: | $(DATA_DIR)
	@if [ ! -f "$(PBF_FILE)" ]; then \
		echo "Downloading Iran PBF..."; \
		curl -L "$(PBF_URL)" -o "$(PBF_FILE)"; \
	else \
		echo "PBF already exists: $(PBF_FILE)"; \
	fi

extract: download
	docker run --rm -t -v $(DATA_DIR):/data osrm/osrm-backend:latest osrm-extract -p $(PROFILE) /data/iran.osm.pbf

partition: extract
	docker run --rm -t -v $(DATA_DIR):/data osrm/osrm-backend:latest osrm-partition /data/iran.osrm

customize: partition
	docker run --rm -t -v $(DATA_DIR):/data osrm/osrm-backend:latest osrm-customize /data/iran.osrm

routed:
	docker run --rm -it -p 5000:5000 -v $(DATA_DIR):/data osrm/osrm-backend:latest osrm-routed --algorithm mld /data/iran.osrm

clean:
	rm -f $(DATA_DIR)/*.osrm* $(DATA_DIR)/*.pbf


