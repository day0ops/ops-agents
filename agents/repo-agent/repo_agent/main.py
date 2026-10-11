"""Repo Agent - single-hop agent demonstrating Standard (Impersonation,
proxy-native) vs STS Delegation exchange against the internal repo MCP
server. Mode switches which gateway route / exchange path is used - see
Flow 1 in docs/superpowers/specs/2026-10-10-auth-pillar-agents-mcp-design.md."""
import os

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from ops_agent import sts
from ops_agent.harness import bearer_header_provider, build_app
from ops_agent.openai_model import OpenAIModel

INSTRUCTION = (
    "You are the Repo Agent. You can list repositories and check pull "
    "request status using your tools. Answer concisely based on tool results."
)


def _mcp_url_for_mode(mode: str) -> str:
    if mode == "sts-delegation":
        return os.environ["MCP_DELEGATION_URL"]
    return os.environ["MCP_STANDARD_URL"]


def build_agent(token: str, mode: str):
    """Returns (LlmAgent, bearer_for_mcp, extra) per the harness contract."""
    if mode == "sts-delegation":
        sa_token = sts.read_sa_token(os.environ.get("SA_TOKEN_PATH", sts.DEFAULT_SA_TOKEN_PATH))
        bearer = sts.exchange(os.environ["STS_URL"], token, sa_token)
    else:
        bearer = token

    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=_mcp_url_for_mode(mode)),
        header_provider=bearer_header_provider,
    )
    agent = LlmAgent(
        model=OpenAIModel(
            model=os.environ.get("MODEL", "gpt-4o-mini"),
            api_base=os.environ["LLM_BASE_URL"],
            api_key=os.environ.get("LLM_API_KEY", "unused"),
        ),
        name="repo_agent",
        instruction=INSTRUCTION,
        tools=[toolset],
    )
    return agent, bearer, {}


app = build_app(build_agent)
