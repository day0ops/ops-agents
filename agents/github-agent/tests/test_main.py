from unittest.mock import patch

from github_agent.main import build_agent


class FakeResp:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def test_build_agent_uses_raw_user_token_no_exchange(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("MCP_GITHUB_URL", "http://gw/mcp-github")
    with patch("github_agent.main.requests.post", return_value=FakeResp(200)):
        agent, bearer, extra = build_agent("user-keycloak-token", "")
    assert agent is not None
    assert bearer == "user-keycloak-token"
    assert extra == {}


def test_build_agent_returns_real_consent_url_without_invoking_the_llm(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("MCP_GITHUB_URL", "http://gw/mcp-github")
    real_url = "https://github.com/login/oauth/authorize?client_id=Ov23licI0fr0X9uYmiEx&scope=repo"
    with patch("github_agent.main.requests.post", return_value=FakeResp(400, {"url": real_url})):
        agent, bearer, extra = build_agent("user-keycloak-token", "")
    assert agent is None
    assert bearer == "user-keycloak-token"
    assert real_url in extra["answer"]


def test_build_agent_proceeds_normally_when_probe_fails_for_other_reasons(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("MCP_GITHUB_URL", "http://gw/mcp-github")
    with patch("github_agent.main.requests.post", return_value=FakeResp(404)):
        agent, _bearer, extra = build_agent("user-keycloak-token", "")
    assert agent is not None
    assert extra == {}
