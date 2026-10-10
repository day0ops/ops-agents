# Usage: make build SVC=mcp-servers/repo-server IMAGE=repo-server TAG=0.1.0
REGISTRY ?= australia-southeast1-docker.pkg.dev/field-engineering-apac/kasunt
TAG ?= 0.1.0

.PHONY: test lint build push
test:
	pytest -q
lint:
	ruff check .
build:
	docker build -t $(REGISTRY)/$(IMAGE):$(TAG) $(SVC)
push:
	docker push $(REGISTRY)/$(IMAGE):$(TAG)
