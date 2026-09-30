.PHONY: install format lint typecheck test dependency-audit check run worker

install:
	python -m pip install -e '.[dev]'

format:
	ruff format src tests

lint:
	ruff check src tests

typecheck:
	mypy src

test:
	pytest

dependency-audit:
	pip-audit --ignore-vuln PYSEC-2026-311 --ignore-vuln PYSEC-2026-3813 --ignore-vuln PYSEC-2026-3814 --ignore-vuln PYSEC-2026-3815

check: lint typecheck test

run:
	uvicorn creator.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	creator-worker image-generation
