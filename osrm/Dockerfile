FROM osrm/osrm-backend:latest as base

# This Dockerfile is optional for multi-stage preprocessing.
# We keep preprocessing outside via Makefile to allow updating maps without rebuilds.

CMD ["bash", "-lc", "osrm-routed --algorithm mld /data/iran.osrm"]


