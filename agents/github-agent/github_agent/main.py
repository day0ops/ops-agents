"""GitHub Agent - Elicitation demo (Flow 3). No STS call from this agent at
all: the user's own Keycloak token is presented to the GitHub MCP route, and
agentgateway's entElicitation backend auth either injects a stored real
GitHub token or returns a pending response with a consent URL - see
docs/superpowers/specs/2026-10-10-auth-pillar-agents-mcp-design.md Flow 3.

TODO(Phase B live verification): confirm the exact wire shape of the
"pending" response an MCP tool call receives on the first attempt (status
code / body field for the elicitation URL) against the real deployment, and
adjust the instruction/tool wrapper below to surface it faithfully - this
can only be confirmed once Task B5's entElicitation policy is live."""
import os

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from ops_agent.harness import bearer_header_provider, build_app

INSTRUCTION = (
    "You are the GitHub Agent. Use your tools to answer questions about the "
    "user's real GitHub repositories. If a tool result indicates that "
    "authorization is required (a pending status with a URL), tell the user "
    "exactly that URL and ask them to open it to connect their GitHub "
    "account, then retry."
)


def build_agent(token: str, mode: str):
    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=os.environ["MCP_GITHUB_URL"]),
        header_provider=bearer_header_provider,
    )
    agent = LlmAgent(
        model=LiteLlm(model="openai/gpt-4o-mini", api_base=os.environ["LLM_BASE_URL"]),
        name="github_agent",
        instruction=INSTRUCTION,
        tools=[toolset],
    )
    return agent, token, {}


app = build_app(build_agent)
