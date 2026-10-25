FROM geopython/pygeoapi:0.24.0@sha256:a62895f2585ef1fcd1fc97ec35bf13177becc1334a622172a2c5c4d2145b8f0a

LABEL org.opencontainers.image.title="Raster Processes API" \
      org.opencontainers.image.description="An OGC API – Processes service for raster operations, powered by pygeoapi and rasterio/GDAL." \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.vendor="Gouwe-Gozer" \
      org.opencontainers.image.base.name="docker.io/geopython/pygeoapi:0.24.0"

ENV CONTAINER_PORT=8080 \
    PROJ_NETWORK=OFF \
    PYTHONPATH=/pygeoapi \
    GEO_SAMPLE_DATA_DIR=/pygeoapi/geo_processes/data/samples \
    PYGEOAPI_OPENAPI=/tmp/pygeoapi.openapi.yml \
    PYGEOAPI_CONFIG=/pygeoapi/local.config.yml \
    PYTHONDONTWRITEBYTECODE=1 \
    WSGI_APP=geo_processes.app:APP

COPY config/pygeoapi.yml /pygeoapi/local.config.yml
COPY src/geo_processes /pygeoapi/geo_processes
COPY LICENSE THIRD_PARTY_NOTICES.md /licenses/raster-processes/

COPY docker/entrypoint.sh /geo-entrypoint.sh

# Install into the interpreter actually used by Gunicorn. Fail if no wheel exists.
RUN /venv/bin/python3 -m pip install --no-cache-dir --only-binary=:all: "numpy==1.26.4" "rasterio==1.4.3"

RUN /venv/bin/python3 -c \
    'import rasterio, pygeoapi; from geo_processes.processes.info import RasterInfoProcessor'

# Docker initializes a new named volume with this non-root ownership.
RUN mkdir -p /var/lib/geo/results \
    && chown 10001:10001 /var/lib/geo/results \
    && chmod 0700 /var/lib/geo/results

USER 10001:10001

EXPOSE 8080

ENTRYPOINT ["/bin/sh", "/geo-entrypoint.sh"]
