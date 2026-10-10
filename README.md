# ops-agents

Operational agents and MCP servers for the agentgateway auth-pillar demo.

## Layout

```
agents/              ADK agents, one directory per agent
  repo-agent/
  release-manager-agent/
  deploy-agent/
  github-agent/
mcp-servers/          MCP servers
  repo-server/
```

Each service directory is self-contained: its own `requirements.txt` (runtime
deps) and `requirements-dev.txt` (test/lint deps), its own `Dockerfile`, and
its own tests. Shared dev tooling (ruff, pytest) is configured once at the
repo root in `pyproject.toml`.

## Build and test a single service

```bash
pip install -r <service>/requirements.txt -r <service>/requirements-dev.txt
ruff check .
pytest -q
```

## Build and push an image

Images build from this repo and push to
`australia-southeast1-docker.pkg.dev/field-engineering-apac/kasunt/<name>:<tag>`,
named after their service directory (`repo-server`, `repo-agent`,
`release-manager-agent`, `deploy-agent`, `github-agent`).

```bash
make build SVC=mcp-servers/repo-server IMAGE=repo-server TAG=0.1.0
make push  SVC=mcp-servers/repo-server IMAGE=repo-server TAG=0.1.0
```

`TAG` defaults to `0.1.0`.
