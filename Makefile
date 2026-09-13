.PHONY: setup dev build run eval clean

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

setup: $(VENV)/.stamp frontend/node_modules

$(VENV)/.stamp: backend/requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -r backend/requirements.txt
	touch $@

frontend/node_modules: frontend/package.json
	cd frontend && npm install --silent
	touch $@

# Backend with reload + Vite dev server on :5173 proxying /api to :8000
dev: setup
	$(VENV)/bin/uvicorn backend.main:app --reload --port 8000 & \
	cd frontend && npm run dev

# Compile the frontend into backend/static, then everything is one process
build: setup
	cd frontend && npm run build

run: build
	$(VENV)/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000

eval: setup
	$(PY) -m eval.run

clean:
	rm -rf $(VENV) frontend/node_modules backend/static
