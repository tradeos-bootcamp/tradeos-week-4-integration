.PHONY: install test run dev docker-up docker-down

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install pytest pytest-asyncio httpx

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	pytest tests/ -v

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build:
	docker-compose build