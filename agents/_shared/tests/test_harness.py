from fastapi.testclient import TestClient
from ops_agent.harness import build_app


def test_health():
    # A trivial agent factory - health must not require a real LLM.
    app = build_app(lambda token, mode: (None, token, {}))
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}


def test_run_returns_extra_verbatim_when_agent_is_none():
    # agent=None means the factory already has the complete answer (e.g. a
    # real consent URL) and /run must return it without touching the LLM.
    app = build_app(lambda token, mode: (None, token, {"answer": "real url here"}))
    client = TestClient(app)
    resp = client.post("/run", json={"query": "connect my account", "token": "t"})
    assert resp.json() == {"answer": "real url here"}
