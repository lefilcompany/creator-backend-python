.PHONY: install format format-check lint typecheck test dependency-audit secrets security check run worker

install:
	python -m pip install -e '.[dev]'

format:
	ruff format src tests

format-check:
	ruff format --check src tests

lint:
	ruff check src tests

typecheck:
	mypy src

test:
	pytest

dependency-audit:
	pip-audit

secrets:
	gitleaks detect --source . --no-banner --redact --config .gitleaks.toml

security: dependency-audit secrets

check: lint format-check typecheck test

run:
	uvicorn creator.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	creator-worker image-generation
