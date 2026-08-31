# BaseChatt Makefile
.PHONY: install dev venv db-up db-down up down lint typecheck test test-fast seed sync run cli clean web

PYTHON := python
PIP := $(PYTHON) -m pip

venv:
	$(PYTHON) -m venv .venv

install: venv
	.venv/bin/pip install -e ".[dev]"

db-up:
	docker compose up -d postgres redis

db-down:
	docker compose down postgres redis

up:
	docker compose up -d --build

down:
	docker compose down

lint:
	ruff check src tests apps/api

typecheck:
	mypy src

test:
	pytest

test-fast:
	pytest -x -q

seed:
	$(PYTHON) -m basechatt.cli seed

sync:
	$(PYTHON) -m basechatt.cli sync

run:
	uvicorn apps.api.main:app --reload

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache
