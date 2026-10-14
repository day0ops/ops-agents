"""Settlement Agent - specialist, hop 2 of the two-hop Delegation chain
(Flow 2). Re-exchanges the token it receives (already an STS-issued delegated
token from the Transfer Orchestrator) at the STS, producing a token with a
nested act chain - confirmed live that Solo's STS accepts its own tokens as
exchange subjects (see the design spec's spike finding). Surfaces the decoded
chain in its response for the chain-of-custody demo."""
import os

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from ops_agent import sts
from ops_agent.harness import bearer_header_provider, build_app
from ops_agent.openai_model import OpenAIModel

INSTRUCTION = (
    "You are the Settlement Agent for a retail bank. You perform the actual "
    "ledger transfer by calling the core banking transfer tool, then report "
    "the result and the full delegation chain (who authorized this, through "
    "which agents). Only report what the tool returns."
)


def build_agent(token: str, mode: str):
    """token here is the Transfer Orchestrator's already-exchanged
    (STS-issued) token, not a raw Keycloak token - this is the re-exchange
    hop."""
    sa_token = sts.read_sa_token(os.environ.get("SA_TOKEN_PATH", sts.DEFAULT_SA_TOKEN_PATH))
    t2 = sts.exchange(os.environ["STS_URL"], token, sa_token)
    claims = sts.decode_claims(t2)
    act = claims.get("act", {})
    chain = {
        "sub": claims.get("sub"),
        "act": act.get("sub"),
        "act_act": act.get("act", {}).get("sub"),
    }

    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=os.environ["MCP_CORE_BANKING_DELEGATION_URL"]
        ),
        header_provider=bearer_header_provider,
    )
    agent = LlmAgent(
        model=OpenAIModel(
            model=os.environ.get("MODEL", "gpt-4o-mini"),
            api_base=os.environ["LLM_BASE_URL"],
            api_key=os.environ.get("LLM_API_KEY", "unused"),
        ),
        name="settlement_agent",
        instruction=INSTRUCTION,
        tools=[toolset],
    )
    return agent, t2, {"chain": chain}


app = build_app(build_agent)
