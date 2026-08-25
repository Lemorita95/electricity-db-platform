# platform/electricity-data-manager/Makefile

infra-up:
	$(MAKE) -C ../infrastructure up

infra-down:
	$(MAKE) -C ../infrastructure down

build:
	docker build -t electricity-data-manager:latest .

up: build
	docker-compose up

up-all: infra-up up

down:
	docker-compose down

down-all: down infra-down

logs:
	docker-compose logs -f app

migrate:
	docker-compose run --rm migrate