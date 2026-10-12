# Su Windows senza make usare direttamente: python scripts/tasks.py <comando> (D-17)
PY ?= python
TASKS = $(PY) scripts/tasks.py

.PHONY: dev test lint migrate seed theme-check admin-dev build

dev:            ## Avvia backend Flask in debug
	$(TASKS) dev

admin-dev:      ## Avvia il pannello React (Vite), dalla Fase 5
	cd admin && npm run dev

test:
	$(TASKS) test

lint:           ## ruff + mypy (+ eslint se esiste admin/)
	$(TASKS) lint

migrate:
	$(TASKS) migrate

seed:           ## Dati demo (comando seed-demo da creare nelle fasi successive)
	$(PY) -m flask --app app seed-demo

theme-check:    ## Valida theme.json di tutti i temi
	$(TASKS) theme-check

build:
	docker compose build
