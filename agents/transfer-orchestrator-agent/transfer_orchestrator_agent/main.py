"""Transfer Orchestrator Agent - front-line of the two-hop Delegation chain
(Flow 2). Exchanges the user's token at the STS, then delegates to Settlement
Agent, passing the exchanged (not raw) token - Settlement Agent re-exchanges
it in turn, producing a nested act chain (chain-of-custody)."""
import os

import requests
from google.adk.agents import LlmAgent
from ops_agent import sts
from ops_agent.harness import build_app
from ops_agent.openai_model import OpenAIModel

INSTRUCTION = (
    "You are the Transfer Orchestrator for a retail bank. When the customer "
    "asks to move money, use the ask_settlement_agent tool to delegate the "
    "actual ledger operation to the Settlement Agent, and relay its answer "
    "including the delegation chain it reports. You never touch the ledger "
    "directly."
)


def ask_settlement_agent(query: str, token: str) -> dict:
    """Delegate a transfer-related request to the Settlement Agent, passing
    along the caller's exchanged authorization token."""
    resp = requests.post(
        os.environ["SETTLEMENT_AGENT_URL"], json={"query": query, "token": token}, timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def build_agent(token: str, mode: str):
    sa_token = sts.read_sa_token(os.environ.get("SA_TOKEN_PATH", sts.DEFAULT_SA_TOKEN_PATH))
    delegated_token = sts.exchange(os.environ["STS_URL"], token, sa_token)

    def ask_settlement_agent_tool(query: str) -> dict:
        """Ask the Settlement Agent to check or perform a transfer-related action."""
        return ask_settlement_agent(query, delegated_token)

    agent = LlmAgent(
        model=OpenAIModel(
            model=os.environ.get("MODEL", "gpt-4o-mini"),
            api_base=os.environ["LLM_BASE_URL"],
            api_key=os.environ.get("LLM_API_KEY", "unused"),
        ),
        name="transfer_orchestrator_agent",
        instruction=INSTRUCTION,
        tools=[ask_settlement_agent_tool],
    )
    return agent, delegated_token, {}


app = build_app(build_agent)
