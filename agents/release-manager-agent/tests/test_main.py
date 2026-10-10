from unittest.mock import patch

from release_manager_agent.main import ask_deploy_agent, build_agent


def test_build_agent_exchanges_user_token_for_delegated_token(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("STS_URL", "http://sts:7777")
    monkeypatch.setenv("DEPLOY_AGENT_URL", "http://gw/deploy-agent/run")
    sa_path = tmp_path / "sa-token"
    sa_path.write_text("release-manager-sa-token")
    monkeypatch.setenv("SA_TOKEN_PATH", str(sa_path))
    with patch("release_manager_agent.main.sts.exchange", return_value="T1") as m:
        _agent, bearer, extra = build_agent("user-token-123", "")
    m.assert_called_once_with("http://sts:7777", "user-token-123", "release-manager-sa-token")
    assert bearer == "T1"
    assert extra == {}

def test_ask_deploy_agent_forwards_the_exchanged_token(monkeypatch):
    monkeypatch.setenv("DEPLOY_AGENT_URL", "http://gw/deploy-agent/run")
    captured = {}
    class FakeResp:
        def json(self): return {"answer": "deployed", "chain": "user -> release-manager -> deploy-agent"}
        def raise_for_status(self): pass
    def fake_post(url, json=None, timeout=None):
        captured["url"] = url; captured["json"] = json
        return FakeResp()
    with patch("release_manager_agent.main.requests.post", fake_post):
        result = ask_deploy_agent("deploy payments-service to staging", "T1")
    assert captured["url"] == "http://gw/deploy-agent/run"
    assert captured["json"] == {"query": "deploy payments-service to staging", "token": "T1"}
    assert "chain" in result
