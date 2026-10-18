# Su Windows senza make usare direttamente: python scripts/tasks.py <comando> (D-17)
PY ?= python
TASKS = $(PY) scripts/tasks.py

.PHONY: dev test lint migrate seed theme-check admin-install admin-dev admin-build admin-test admin-lint build

dev:            ## Avvia backend Flask in debug
	$(TASKS) dev

admin-install admin-dev admin-build admin-test admin-lint:  ## Pannello React (D-96)
	$(TASKS) $@

test:
	$(TASKS) test

lint:           ## ruff + mypy (il pannello ha admin-lint)
	$(TASKS) lint

migrate:
	$(TASKS) migrate

seed:           ## Dati demo (comando seed-demo da creare nelle fasi successive)
	$(PY) -m flask --app app seed-demo

theme-check:    ## Valida theme.json di tutti i temi
	$(TASKS) theme-check

build:
	docker compose build
