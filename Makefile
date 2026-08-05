.PHONY: up down logs test lint build shell-api shell-worker scale-workers demo

up:
	docker compose up --build -d

down:
	docker compose down -v

logs:
	docker compose logs -f

scale-workers:
	docker compose up --scale worker=3 -d

test:
	pytest tests/ --cov=shared --cov=services --cov-report=term-missing -v

lint:
	python -m flake8 shared/ services/ tests/ --max-line-length=100

shell-api:
	docker compose exec api bash

shell-worker:
	docker compose exec worker bash

demo:
	@echo "Submitting a test job..."
	curl -s -X POST http://localhost:8000/jobs \
	  -H "Content-Type: application/json" \
	  -d '{"job_type":"send_email","payload":{"to":"test@example.com","subject":"Hello"}}' | python3 -m json.tool
	@echo "\nListing all jobs:"
	curl -s http://localhost:8000/jobs | python3 -m json.tool
