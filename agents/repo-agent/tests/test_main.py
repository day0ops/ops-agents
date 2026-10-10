from unittest.mock import patch

from repo_agent.main import _mcp_url_for_mode, build_agent


def test_mcp_url_selects_route_by_mode(monkeypatch):
    monkeypatch.setenv("MCP_STANDARD_URL", "http://gw/repo-standard/mcp")
    monkeypatch.setenv("MCP_DELEGATION_URL", "http://gw/repo-delegation/mcp")
    assert _mcp_url_for_mode("standard") == "http://gw/repo-standard/mcp"
    assert _mcp_url_for_mode("sts-delegation") == "http://gw/repo-delegation/mcp"

def test_standard_mode_bearer_is_the_raw_user_token(monkeypatch):
    monkeypatch.setenv("MCP_STANDARD_URL", "http://gw/repo-standard/mcp")
    monkeypatch.setenv("MCP_DELEGATION_URL", "http://gw/repo-delegation/mcp")
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    _agent, bearer, extra = build_agent("user-token-123", "standard")
    assert bearer == "user-token-123"
    assert extra == {}

def test_sts_delegation_mode_exchanges_before_building_agent(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_STANDARD_URL", "http://gw/repo-standard/mcp")
    monkeypatch.setenv("MCP_DELEGATION_URL", "http://gw/repo-delegation/mcp")
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("STS_URL", "http://sts:7777")
    sa_path = tmp_path / "sa-token"
    sa_path.write_text("agent-sa-token")
    monkeypatch.setenv("SA_TOKEN_PATH", str(sa_path))
    with patch("repo_agent.main.sts.exchange", return_value="delegated-token") as m:
        _agent, bearer, _extra = build_agent("user-token-123", "sts-delegation")
    m.assert_called_once_with("http://sts:7777", "user-token-123", "agent-sa-token")
    assert bearer == "delegated-token"
