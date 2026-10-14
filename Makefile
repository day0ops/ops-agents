# Usage: make build SVC=mcp-servers/core-banking IMAGE=core-banking TAG=v0.1.0
# TAG should match the latest git release tag (see .github/workflows/release.yml) -
# CI always pushes v-prefixed tags, so a manual build should match them.
REGISTRY ?= australia-southeast1-docker.pkg.dev/field-engineering-apac/kasunt
TAG ?= v0.1.0

.PHONY: test lint build push
test:
	pytest -q
lint:
	ruff check .
build:
	docker build -t $(REGISTRY)/$(IMAGE):$(TAG) -f $(SVC)/Dockerfile .
push:
	docker push $(REGISTRY)/$(IMAGE):$(TAG)
