.PHONY: install format lint typecheck test check run worker

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

check: lint typecheck test

run:
	uvicorn creator.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	creator-worker image-generation
