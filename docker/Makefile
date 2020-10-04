
COMPOSE_ACTIONS = build up down
.PHONY: $(COMPOSE_ACTIONS)

COMPOSE := sudo docker-compose

.DEFAULT_GOAL := up

$(COMPOSE_ACTIONS):
	$(COMPOSE) $@

up: build

