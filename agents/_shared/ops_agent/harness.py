"""FastAPI harness serving an ADK agent as POST /run + GET /health, threading
a per-request bearer token into session state so an MCPToolset header_provider
can attach it to each MCP call. ADK 2.11.0 API verified live against the
installed package (InMemoryRunner, run_async, types.Content, create_session
all match the documented shape used below).

agent_factory(token, mode) returns a 3-tuple:
  - the LlmAgent to run
  - bearer: the token to place in session state for header_provider to use.
    This is NOT always `token` verbatim - an agent performing its own STS
    exchange (e.g. Delegation mode, or the two-hop chain's re-exchange)
    computes the exchanged token BEFORE building the agent/session, and
    returns that exchanged value here, so the MCP call carries it.
  - extra: a dict merged into the JSON response (e.g. a decoded delegation
    chain for the chain-of-custody demo) - {} if unused.
"""
import uuid
from collections.abc import Callable

from fastapi import FastAPI
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel


class RunRequest(BaseModel):
    query: str
    token: str = ""
    mode: str = ""


async def bearer_header_provider(ctx) -> dict:
    """Reusable MCPToolset header_provider: attaches the bearer token placed
    in session state by build_app (see agent_factory contract above) as the
    Authorization header on every MCP tool call for this session."""
    token = ctx.state.get("bearer_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def build_app(agent_factory: Callable) -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/run")
    async def run(req: RunRequest):
        agent, bearer, extra = agent_factory(req.token, req.mode)
        runner = InMemoryRunner(agent=agent, app_name="ops-agent")
        user_id = "demo"
        session_id = str(uuid.uuid4())
        await runner.session_service.create_session(
            app_name="ops-agent", user_id=user_id, session_id=session_id,
            state={"bearer_token": bearer, "mode": req.mode},
        )
        message = types.Content(role="user", parts=[types.Part(text=req.query)])
        final = ""
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=message,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final = "".join(p.text for p in event.content.parts if getattr(p, "text", None))
        return {"answer": final, **extra}

    return app
