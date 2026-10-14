from unittest.mock import patch

from statements_agent.main import build_agent


class FakeResp:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def test_build_agent_uses_raw_user_token_no_exchange(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("MCP_STRIPE_URL", "http://gw/mcp-stripe")
    with patch("statements_agent.main.requests.post", return_value=FakeResp(200)):
        agent, bearer, extra = build_agent("user-keycloak-token", "")
    assert agent is not None
    assert bearer == "user-keycloak-token"
    assert extra == {}


def test_build_agent_returns_real_consent_url_without_invoking_the_llm(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("MCP_STRIPE_URL", "http://gw/mcp-stripe")
    real_url = "https://connect.stripe.com/oauth/authorize?client_id=ca_Ov23licI0fr0X9uYmiEx&scope=read_only"
    with patch("statements_agent.main.requests.post", return_value=FakeResp(400, {"url": real_url})):
        agent, bearer, extra = build_agent("user-keycloak-token", "")
    assert agent is None
    assert bearer == "user-keycloak-token"
    assert real_url in extra["answer"]


def test_build_agent_proceeds_normally_when_probe_fails_for_other_reasons(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("MCP_STRIPE_URL", "http://gw/mcp-stripe")
    with patch("statements_agent.main.requests.post", return_value=FakeResp(404)):
        agent, _bearer, extra = build_agent("user-keycloak-token", "")
    assert agent is not None
    assert extra == {}


def test_probe_sends_a_well_formed_mcp_request(monkeypatch):
    # Regression guard: a bare POST gets rejected by agentgateway's MCP layer
    # (406, then a JSON-RPC deserialize-error 400) before ever reaching the
    # backend-auth/elicitation check - live-verified against the real
    # gateway. The probe must look like a real MCP client to get past it.
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("MCP_STRIPE_URL", "http://gw/mcp-stripe")
    with patch("statements_agent.main.requests.post", return_value=FakeResp(200)) as m:
        build_agent("user-keycloak-token", "")
    _args, kwargs = m.call_args
    assert kwargs["headers"]["Accept"] == "application/json, text/event-stream"
    assert kwargs["json"]["method"] == "initialize"


def test_build_agent_uses_github_url_in_interactive_mode(monkeypatch):
    # Stripe's OAuth app can't do Interactive (DCR+PKCE only, no client
    # secret) - interactive mode is wired to GitHub instead.
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("MCP_GITHUB_URL", "http://gw/mcp-github")
    with patch("statements_agent.main.requests.post", return_value=FakeResp(200)) as m:
        agent, bearer, extra = build_agent("user-keycloak-token", "interactive")
    assert agent is not None
    assert bearer == "user-keycloak-token"
    assert extra == {}
    probed_url = m.call_args[0][0]
    assert probed_url == "http://gw/mcp-github"


def test_build_agent_returns_real_consent_url_in_interactive_mode(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("MCP_GITHUB_URL", "http://gw/mcp-github")
    real_url = "https://github.com/login/oauth/authorize?client_id=abc123&scope=read%3Auser+repo"
    with patch("statements_agent.main.requests.post", return_value=FakeResp(400, {"url": real_url})):
        agent, bearer, extra = build_agent("user-keycloak-token", "interactive")
    assert agent is None
    assert bearer == "user-keycloak-token"
    assert real_url in extra["answer"]
    assert "account" in extra["answer"]


def test_build_agent_defaults_to_stripe_for_any_non_interactive_mode(monkeypatch):
    # "brokered", "", and anything else all mean: use the real Stripe URL.
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("MCP_STRIPE_URL", "http://gw/mcp-stripe-brokered")
    with patch("statements_agent.main.requests.post", return_value=FakeResp(200)):
        agent, _bearer, extra = build_agent("user-keycloak-token", "brokered")
    assert agent is not None
    assert extra == {}
