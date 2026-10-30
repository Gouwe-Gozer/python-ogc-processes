.DEFAULT_GOAL := help
.PHONY: help test test-python quality validate-openapi validate-geonovum validate-cite validate
UV ?= uv
GEONOVUM_INPUT ?=
export GEONOVUM_INPUT
CITE_ARGS ?=

help:
	@echo 'make test                Python tests, coverage, quality and OpenAPI'
	@echo 'make validate-geonovum   Isolated combined deployment; optional GEONOVUM_INPUT override'
	@echo 'make validate-cite       Isolated official suite (fails on test failures)'
	@echo 'make validate            Routine checks plus Geonovum; excludes CITE'

quality:
	$(UV) run ruff format --check src tests scripts
	$(UV) run ruff check src tests scripts
	$(UV) run bandit -r src scripts -c pyproject.toml

validate-openapi:
	mkdir -p runtime-data/validation
	$(UV) run pygeoapi config validate --config config/pygeoapi.yml
	GEO_MANAGER_CLASS=geo_processes.manager.OgcSynchronousManager $(UV) run python -m geo_processes.openapi --output runtime-data/validation/openapi.yml
	$(UV) run pygeoapi openapi validate runtime-data/validation/openapi.yml
	PYTHONPATH=tests/fixtures $(UV) run pygeoapi config validate --config config/pygeoapi.integration.yml
	PYTHONPATH=tests/fixtures $(UV) run pygeoapi openapi generate --format yaml --output-file runtime-data/validation/integration-openapi.yml config/pygeoapi.integration.yml
	$(UV) run pygeoapi openapi validate runtime-data/validation/integration-openapi.yml

test-python:
	mkdir -p runtime-data/validation runtime-data/tmp
	TMPDIR='$(CURDIR)/runtime-data/tmp' $(UV) run pytest --cov=geo_processes --cov-report=term-missing --cov-report=xml:runtime-data/validation/coverage.xml --cov-fail-under=70 --junitxml=runtime-data/validation/pytest.xml

test: quality validate-openapi test-python

validate-geonovum:
	@if [ -n "$$GEONOVUM_INPUT" ]; then \
		$(UV) run python scripts/check_geonovum_baseline.py --docker --input "$$GEONOVUM_INPUT" --raw-output runtime-data/validation/geonovum.json; \
	else \
		$(UV) run python scripts/validate_cite.py --geonovum; \
	fi

validate-cite:
	$(UV) run python scripts/validate_cite.py $(CITE_ARGS)

validate: test validate-geonovum
