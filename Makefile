PY = .venv/Scripts/python.exe

.PHONY: setup ingest ingest-offline test lint type check

setup:
	py -3.12 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt -r requirements-dev.txt

ingest:
	$(PY) -m app.ingest

ingest-offline:
	$(PY) -m app.ingest --skip-contextualize

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check app tests scripts

type:
	$(PY) -m mypy app

check: lint type test
