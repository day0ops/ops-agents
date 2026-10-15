"""FastAPI harness serving an ADK agent as POST /run + GET /health, threading
a per-request bearer token into session state so an McpToolset header_provider
can attach it to each MCP call. ADK 2.11.0 API verified live against the
installed package (InMemoryRunner, run_async, types.Content, create_session
all match the documented shape used below).

agent_factory(token, mode) returns a 3-tuple:
  - the LlmAgent to run, or None if the factory already has the complete
    answer and the LLM must not be invoked at all (e.g. a real consent URL
    read back from a failed tool connection - letting the model see and
    re-express it risks paraphrasing or inventing one instead). When None,
    /run returns `extra` directly, unchanged.
  - bearer: the token to place in session state for header_provider to use.
    This is NOT always `token` verbatim - an agent performing its own STS
    exchange (e.g. Delegation mode, or the two-hop chain's re-exchange)
    computes the exchanged token BEFORE building the agent/session, and
    returns that exchanged value here, so the MCP call carries it.
  - extra: a dict merged into the JSON response (e.g. a decoded delegation
    chain for the chain-of-custody demo) - {} if unused. When agent is None,
    this is the full response body and must include "answer".
"""
import asyncio
import logging
import uuid
from collections.abc import Callable

from fastapi import FastAPI
from google.adk.agents import RunConfig
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel

logger = logging.getLogger("ops_agent.harness")

# ADK's own default (RunConfig.max_llm_calls, unset) is 500 - high enough that
# a model stuck repeating the same tool call runs for minutes. Every agent
# built on this harness reaches its answer in a handful of turns (list_accounts
# + a couple of get_transactions, or a single transfer/get_account_detail), so
# a tight cap bounds a runaway loop without affecting any real exchange.
MAX_LLM_CALLS_PER_RUN = 6

# Hard wall-clock budget for a single /run. The wizard's own HTTP client gives
# up at 45s (agentgateway-demo-wizard's ops_agent_handler.go), and once the
# browser-to-wizard connection is dropped the user just sees "Failed to fetch".
# Returning a clean message well before that is far better than hanging, so the
# whole run is bounded below the caller's timeout.
RUN_TIMEOUT_SECONDS = 30

# Separate, short budget for tearing the runner (and its MCP sessions) down.
# runner.close() walks the agent's McpToolsets and closes each one - without it
# the MCP Streamable-HTTP SSE stream lingers server-side for minutes as a zombie
# (observed live: a GET stream held open for 300s after the run). Teardown must
# never be allowed to hang the response either, so it gets its own ceiling.
CLOSE_TIMEOUT_SECONDS = 5


class RunRequest(BaseModel):
    query: str
    token: str = ""
    mode: str = ""


async def bearer_header_provider(ctx) -> dict:
    """Reusable McpToolset header_provider: attaches the bearer token placed
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
        if agent is None:
            return extra
        runner = InMemoryRunner(agent=agent, app_name="ops-agent")
        user_id = "demo"
        session_id = str(uuid.uuid4())
        await runner.session_service.create_session(
            app_name="ops-agent", user_id=user_id, session_id=session_id,
            state={"bearer_token": bearer, "mode": req.mode},
        )
        message = types.Content(role="user", parts=[types.Part(text=req.query)])

        async def consume() -> str:
            text = ""
            async for event in runner.run_async(
                user_id=user_id, session_id=session_id, new_message=message,
                run_config=RunConfig(max_llm_calls=MAX_LLM_CALLS_PER_RUN),
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    text = "".join(
                        p.text for p in event.content.parts if getattr(p, "text", None)
                    )
            return text

        final = ""
        try:
            final = await asyncio.wait_for(consume(), timeout=RUN_TIMEOUT_SECONDS)
        except LlmCallsLimitExceededError:
            final = (
                "I wasn't able to finish answering that within the usual number of "
                "steps. Please try rephrasing the question."
            )
        except asyncio.TimeoutError:
            final = (
                "That request took longer than expected, so I stopped it. "
                "Please try again."
            )
        finally:
            # Always tear the runner (and its MCP sessions) down, even on
            # timeout or error - otherwise the MCP SSE stream lingers as a
            # zombie. close() must not be allowed to hang the response either,
            # so bound it and swallow any teardown error.
            try:
                await asyncio.wait_for(runner.close(), timeout=CLOSE_TIMEOUT_SECONDS)
            except Exception as err:  # noqa: BLE001 - teardown must never break the response
                logger.warning("runner.close() did not complete cleanly: %s", err)

        return {"answer": final, **extra}

    return app
