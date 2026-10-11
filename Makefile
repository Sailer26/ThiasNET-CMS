.PHONY: dev test lint migrate seed theme-check admin-dev build

dev:            ## Avvia backend Flask in debug
	flask --app app run --debug --port 5000

admin-dev:      ## Avvia il pannello React (Vite)
	cd admin && npm run dev

test:
	pytest -q --cov=app --cov-report=term-missing

lint:
	ruff check . && ruff format --check . && mypy app && cd admin && npm run lint

migrate:
	flask --app app db upgrade

seed:
	flask --app app seed-demo

theme-check:    ## Valida theme.json di tutti i temi
	flask --app app theme-check

build:
	docker compose build
