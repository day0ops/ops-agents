"""Statements Agent - Elicitation demo (Flow 3). No STS call from this agent
at all: the user's own Keycloak token is presented to the MCP route (Stripe
for Brokered mode, PayPal for Interactive - see INSTRUCTION_INTERACTIVE for
why), and agentgateway's entElicitation backend auth either injects a stored
real upstream token or returns a pending response with a consent URL - see
docs/superpowers/specs/2026-10-10-auth-pillar-agents-mcp-design.md Flow 3.

Confirmed live against the real deployment: the pending response is a plain
HTTP 400 with a JSON body `{"url": "..."}`, returned by agentgateway's
generic backend-auth layer for ANY request reaching this backend while the
STS has no banked Stripe token yet - not an MCP-level "pending" tool result.
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

INSTRUCTION_BROKERED = (
    "You are the Statements Agent for a retail bank. You answer questions "
    "about the customer's activity with their external payment processor "
    "(Stripe) - charges, payouts, and balances - by calling your tools. "
    "Restrict yourself to read-only queries; never create, modify, or refund "
    "anything. If a tool result indicates authorization is required (a pending "
    "status with a URL), tell the customer exactly that URL and ask them to "
    "open it to connect their payment account, then retry. Never fabricate a "
    "URL or any financial data."
)

# Stripe's OAuth app only supports dynamic client registration with PKCE
# (confirmed live: its .well-known/oauth-authorization-server advertises
# token_endpoint_auth_methods_supported: ["none"] - it never issues a client
# secret), which Interactive elicitation (a classic static OAuth app) can't
# use. Interactive is wired to PayPal's sandbox MCP instead - a second real
# payment processor, confirmed live to support classic confidential clients
# (token_endpoint_auth_methods_supported includes client_secret_post) -
# keeping the demo on-theme while Brokered's DCR+PKCE model stays the right
# fit for Stripe.
INSTRUCTION_INTERACTIVE = (
    "You are the Statements Agent for a retail bank, answering questions "
    "about the customer's PayPal transaction history - this demo uses PayPal "
    "sandbox for Interactive elicitation since Stripe's OAuth app only "
    "supports dynamic client registration with PKCE, not the classic static "
    "OAuth app Interactive elicitation needs. Restrict yourself to read-only "
    "queries; never create, modify, or refund anything. If a tool result "
    "indicates authorization is required (a pending status with a URL), tell "
    "the customer exactly that URL and ask them to open it to connect their "
    "payment account, then retry. Never fabricate a URL or any financial "
    "data."
)


# A bare probe request isn't enough: agentgateway's MCP layer rejects
# anything that isn't a well-formed JSON-RPC message with the right Accept
# header (406, then a deserialize-error 400) before the request ever reaches
# the backend-auth/elicitation check this probe is trying to trigger -
# live-verified against the real gateway. This is the smallest body/headers
# that gets past MCP's own pre-checks and down to that layer.
_MCP_PROBE_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}
_MCP_PROBE_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "elicitation-probe", "version": "0.0.1"},
    },
}


def _pending_elicitation_url(mcp_url: str, token: str) -> str | None:
    """Returns the real consent URL if agentgateway's entElicitation gate is
    blocking this backend for `token`, else None (not pending - proceed with
    the real MCP connection)."""
    headers = dict(_MCP_PROBE_HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.post(mcp_url, headers=headers, json=_MCP_PROBE_BODY, timeout=10)
    except requests.RequestException:
        return None
    if resp.status_code != 400:
        return None
    try:
        return resp.json().get("url")
    except ValueError:
        return None


def build_agent(token: str, mode: str):
    if mode == "interactive":
        mcp_url = os.environ["MCP_PAYPAL_URL"]
        instruction = INSTRUCTION_INTERACTIVE
    else:
        mcp_url = os.environ["MCP_STRIPE_URL"]
        instruction = INSTRUCTION_BROKERED
    connect_what = "payment account"

    pending_url = _pending_elicitation_url(mcp_url, token)
    if pending_url:
        answer = (
            f"To connect your {connect_what}, open this link: {pending_url}\n\n"
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
        name="statements_agent",
        instruction=instruction,
        tools=[toolset],
    )
    return agent, token, {}


app = build_app(build_agent)
