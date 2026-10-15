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
    assert "don't" in INSTRUCTION and "call get_account_detail for these" in INSTRUCTION


def test_instruction_never_tells_the_model_the_tool_is_restricted():
    # Regression guard: an earlier wording ("...unless the customer
    # explicitly asks..., since that tool is restricted to admins") primed
    # the model to self-censor and refuse get_account_detail even for the
    # explicit-ask case it was meant to allow - observed live, the model
    # never even attempted the call, before or after the gateway's RBAC
    # policy existed. Enforcement belongs to the gateway's CEL policy, not
    # the model's own judgment, so the instruction must never frame the tool
    # as restricted/admin-only to the model itself.
    assert "restricted" not in INSTRUCTION
    assert "admin" not in INSTRUCTION.lower()


def test_instruction_tells_the_model_to_always_attempt_the_explicit_ask_case():
    assert "call get_account_detail directly" in INSTRUCTION
    assert "always attempt it" in INSTRUCTION
    assert "never decline a request before trying the tool" in INSTRUCTION


def test_instruction_has_a_stop_condition_to_avoid_looping():
    # Observed live: a non-admin user asking for their full account/routing
    # number triggered 257 identical get_transactions calls over ~4.5
    # minutes, with the model never producing a final answer - nothing in
    # the instruction ever told it when to STOP calling tools and answer.
    # The harness's max_llm_calls cap now bounds this as a last resort, but
    # the instruction itself should also give the model no reason to loop.
    assert "at most once per account" in INSTRUCTION
    assert "never call the same tool again for the same account" in INSTRUCTION


def test_instruction_tells_the_model_to_relay_retrieved_data_in_full():
    # Observed live: the model successfully called get_account_detail, then
    # still refused to state the numbers it got back ("I was able to access
    # your account details. However, I am not permitted to reveal..."), with
    # no tool denial involved - gpt-4o-mini's own caution around
    # sensitive-looking numbers, not anything the gateway decided. The
    # instruction must explicitly override that instinct for a successful
    # call, since "only report what the tools return" alone wasn't enough.
    assert "state the exact numbers it returned, in full" in INSTRUCTION
    assert "do not redact, truncate, summarize, or decline to share it" in INSTRUCTION
