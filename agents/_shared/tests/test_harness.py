from fastapi.testclient import TestClient
from ops_agent.harness import build_app


def test_health():
    # A trivial agent factory - health must not require a real LLM.
    app = build_app(lambda token, mode: (None, token, {}))
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
