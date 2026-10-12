"""GitHub Agent - Elicitation demo (Flow 3). No STS call from this agent at
all: the user's own Keycloak token is presented to the GitHub MCP route, and
agentgateway's entElicitation backend auth either injects a stored real
GitHub token or returns a pending response with a consent URL - see
docs/superpowers/specs/2026-10-10-auth-pillar-agents-mcp-design.md Flow 3.

Confirmed live against the real deployment: the pending response is a plain
HTTP 400 with a JSON body `{"url": "..."}`, returned by agentgateway's
generic backend-auth layer for ANY request reaching this backend while the
STS has no banked GitHub token yet - not an MCP-level "pending" tool result.
Because it happens before the MCP session even initializes, ADK's McpToolset
treats it as a connection failure and silently drops the toolset (logged,
not raised), leaving the LLM with no tools and nothing to ground an answer
in - it then fabricates a plausible-looking but fake consent URL instead of
reporting the real one. _pending_elicitation_url probes the same backend
directly first so the real URL is read before ADK's wrapping ever discards
it, and build_agent returns it verbatim without invoking the LLM."""
import os

import requests
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from ops_agent.harness import bearer_header_provider, build_app
from ops_agent.openai_model import OpenAIModel

INSTRUCTION = (
    "You are the GitHub Agent. Use your tools to answer questions about the "
    "user's real GitHub repositories. If a tool result indicates that "
    "authorization is required (a pending status with a URL), tell the user "
    "exactly that URL and ask them to open it to connect their GitHub "
    "account, then retry."
)


def _pending_elicitation_url(mcp_url: str, token: str) -> str | None:
    """Returns the real consent URL if agentgateway's entElicitation gate is
    blocking this backend for `token`, else None (not pending - proceed with
    the real MCP connection). A bare probe request is enough to trigger the
    gate since it's generic backend auth, not MCP-specific."""
    try:
        resp = requests.post(
            mcp_url,
            headers={"Authorization": f"Bearer {token}"} if token else {},
            timeout=10,
        )
    except requests.RequestException:
        return None
    if resp.status_code != 400:
        return None
    try:
        return resp.json().get("url")
    except ValueError:
        return None


def build_agent(token: str, mode: str):
    mcp_url = os.environ["MCP_GITHUB_URL"]
    pending_url = _pending_elicitation_url(mcp_url, token)
    if pending_url:
        answer = (
            f"To connect your GitHub account, open this link: {pending_url}\n\n"
            "Once you've authorized access, ask me again."
        )
        return None, token, {"answer": answer}

    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=mcp_url),
        header_provider=bearer_header_provider,
    )
    agent = LlmAgent(
        model=OpenAIModel(
            model=os.environ.get("MODEL", "gpt-4o-mini"),
            api_base=os.environ["LLM_BASE_URL"],
            api_key=os.environ.get("LLM_API_KEY", "unused"),
        ),
        name="github_agent",
        instruction=INSTRUCTION,
        tools=[toolset],
    )
    return agent, token, {}


app = build_app(build_agent)
