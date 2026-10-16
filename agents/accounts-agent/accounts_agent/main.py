"""Accounts Agent - reads the customer's own balances and transactions from the
internal Core Banking MCP. No STS: the user's token is presented as-is and
agentgateway performs the Impersonation exchange before forwarding (same
identity, re-signed, no act claim). Read-only."""
import os

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from ops_agent.harness import bearer_header_provider, build_app
from ops_agent.openai_model import OpenAIModel

INSTRUCTION = (
    "You are the Accounts Agent for a retail bank. For balance and recent "
    "activity questions, call list_accounts and get_transactions - don't "
    "call get_account_detail for these, it answers a different question. "
    "When the customer asks for their full account or routing number, first "
    "call list_accounts to get their real account ids, then call "
    "get_account_detail for each account, using an account id exactly as "
    "returned by list_accounts - never make one up. Always attempt the call "
    "before deciding anything; whether it succeeds or is denied is the "
    "bank's decision, not yours, so never decline a request before trying "
    "the tool. Call each tool at most once per account, then answer with "
    "what the tools returned - never call the same tool again for the same "
    "account. When a call succeeds, state the exact numbers it returned, in "
    "full - this is the customer's own data, retrieved through an authorized "
    "channel, so do not redact, truncate, summarize, or decline to share it. "
    "If a tool call comes back denied, say plainly that you are not permitted "
    "to access that detail, and do not guess or fabricate account numbers or "
    "balances."
)


def build_agent(token: str, mode: str):
    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=os.environ["MCP_CORE_BANKING_URL"]),
        header_provider=bearer_header_provider,
    )
    agent = LlmAgent(
        model=OpenAIModel(
            model=os.environ.get("MODEL", "gpt-4o-mini"),
            api_base=os.environ["LLM_BASE_URL"],
            api_key=os.environ.get("LLM_API_KEY", "unused"),
        ),
        name="accounts_agent",
        instruction=INSTRUCTION,
        tools=[toolset],
    )
    return agent, token, {}


app = build_app(build_agent)
