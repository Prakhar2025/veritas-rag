PY = .venv/Scripts/python.exe

.PHONY: setup ingest ingest-offline api console eval eval-real test lint type check

setup:
	py -3.12 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt -r requirements-dev.txt

ingest:
	$(PY) -m app.ingest

ingest-offline:
	$(PY) -m app.ingest --skip-contextualize

api:
	$(PY) -m uvicorn app.api.app:create_app --factory --host 127.0.0.1 --port 8000

console:
	cd console && npm run dev

eval:
	$(PY) evals/run_evals.py --smoke

eval-real:
	$(PY) evals/run_evals.py --full

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check app tests scripts

type:
	$(PY) -m mypy app

check: lint type test
