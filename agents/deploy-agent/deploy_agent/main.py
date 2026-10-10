"""Deploy Agent - specialist, hop 2 of the two-hop Delegation chain (Flow 2).
Re-exchanges the token it receives (already an STS-issued delegated token
from Release Manager) at the STS, producing a token with a nested act chain
- confirmed live that Solo's STS accepts its own tokens as exchange
subjects (see the design spec's spike finding). Surfaces the decoded chain
in its response for the chain-of-custody demo."""
import os

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from ops_agent import sts
from ops_agent.harness import bearer_header_provider, build_app

INSTRUCTION = (
    "You are the Deploy Agent. Use your tools to check pull request status or "
    "trigger deploys. Answer concisely based on tool results."
)


def build_agent(token: str, mode: str):
    """token here is Release Manager's already-exchanged (STS-issued) token,
    not a raw Keycloak token - this is the re-exchange hop."""
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
        connection_params=StreamableHTTPConnectionParams(url=os.environ["MCP_URL"]),
        header_provider=bearer_header_provider,
    )
    agent = LlmAgent(
        model=LiteLlm(model="openai/gpt-4o-mini", api_base=os.environ["LLM_BASE_URL"]),
        name="deploy_agent",
        instruction=INSTRUCTION,
        tools=[toolset],
    )
    return agent, t2, {"chain": chain}


app = build_app(build_agent)
