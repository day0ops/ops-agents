from accounts_agent.main import INSTRUCTION, build_agent


def test_build_agent_presents_the_raw_user_token(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/openai")
    monkeypatch.setenv("MCP_CORE_BANKING_URL", "http://gw/core-banking/mcp")
    agent, bearer, extra = build_agent("user-token", "")
    assert agent is not None
    assert bearer == "user-token"
    assert extra == {}


def test_instruction_steers_balance_questions_away_from_the_admin_only_tool():
    # A non-admin user asking a plain balance question was observed live
    # calling get_account_detail (admin-only, denied) instead of
    # list_accounts/get_transactions - the instruction must spell out which
    # tool answers which kind of question, not leave it to the model to infer.
    assert "list_accounts and get_transactions" in INSTRUCTION
    assert "never call get_account_detail" in INSTRUCTION
