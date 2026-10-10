import base64
import json
from unittest.mock import patch

from deploy_agent.main import build_agent


def _jwt(payload: dict) -> str:
    def seg(d): return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{seg({'alg':'none'})}.{seg(payload)}.sig"

def test_build_agent_reexchanges_and_surfaces_the_chain(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("MCP_URL", "http://gw/repo-chain/mcp")
    monkeypatch.setenv("STS_URL", "http://sts:7777")
    sa_path = tmp_path / "sa-token"
    sa_path.write_text("deploy-agent-sa-token")
    monkeypatch.setenv("SA_TOKEN_PATH", str(sa_path))

    t1 = "release-manager-token"
    t2 = _jwt({"sub": "user-123", "act": {"sub": "deploy-agent", "act": {"sub": "release-manager"}}})

    with patch("deploy_agent.main.sts.exchange", return_value=t2) as m:
        _agent, bearer, extra = build_agent(t1, "")

    m.assert_called_once_with("http://sts:7777", t1, "deploy-agent-sa-token")
    assert bearer == t2
    assert extra["chain"]["sub"] == "user-123"
    assert extra["chain"]["act"] == "deploy-agent"
    assert extra["chain"]["act_act"] == "release-manager"
