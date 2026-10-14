from accounts_agent.main import build_agent


def test_build_agent_presents_the_raw_user_token(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("MCP_CORE_BANKING_URL", "http://gw/core-banking/mcp")
    agent, bearer, extra = build_agent("user-token", "")
    assert agent is not None
    assert bearer == "user-token"
    assert extra == {}
