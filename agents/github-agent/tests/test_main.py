from github_agent.main import build_agent


def test_build_agent_uses_raw_user_token_no_exchange(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("MCP_GITHUB_URL", "http://gw/mcp-github")
    _agent, bearer, extra = build_agent("user-keycloak-token", "")
    assert bearer == "user-keycloak-token"
    assert extra == {}
