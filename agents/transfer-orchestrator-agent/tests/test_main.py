from unittest.mock import patch

from transfer_orchestrator_agent.main import ask_settlement_agent, build_agent


def test_build_agent_exchanges_user_token_for_delegated_token(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("STS_URL", "http://sts:7777")
    monkeypatch.setenv("SETTLEMENT_AGENT_URL", "http://gw/settlement-agent/run")
    sa = tmp_path / "sa-token"; sa.write_text("orchestrator-sa")
    monkeypatch.setenv("SA_TOKEN_PATH", str(sa))
    with patch("transfer_orchestrator_agent.main.sts.exchange", return_value="T1") as m:
        _agent, bearer, extra = build_agent("user-token", "")
    m.assert_called_once_with("http://sts:7777", "user-token", "orchestrator-sa")
    assert bearer == "T1"
    assert extra == {}


def test_ask_settlement_agent_forwards_the_exchanged_token(monkeypatch):
    monkeypatch.setenv("SETTLEMENT_AGENT_URL", "http://gw/settlement-agent/run")
    captured = {}
    class FakeResp:
        def json(self): return {"answer": "settled", "chain": "user -> orchestrator -> settlement"}
        def raise_for_status(self): pass
    def fake_post(url, json=None, timeout=None):
        captured["url"] = url; captured["json"] = json; return FakeResp()
    with patch("transfer_orchestrator_agent.main.requests.post", fake_post):
        result = ask_settlement_agent("transfer 500 from savings to checking", "T1")
    assert captured["url"] == "http://gw/settlement-agent/run"
    assert captured["json"] == {"query": "transfer 500 from savings to checking", "token": "T1"}
    assert "chain" in result
