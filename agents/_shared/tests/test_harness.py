import asyncio

from fastapi.testclient import TestClient
from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import types
from ops_agent import harness
from ops_agent.harness import build_app
from pydantic import PrivateAttr


def test_health():
    # A trivial agent factory - health must not require a real LLM.
    app = build_app(lambda token, mode: (None, token, {}))
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}


def test_run_returns_extra_verbatim_when_agent_is_none():
    # agent=None means the factory already has the complete answer (e.g. a
    # real consent URL) and /run must return it without touching the LLM.
    app = build_app(lambda token, mode: (None, token, {"answer": "real url here"}))
    client = TestClient(app)
    resp = client.post("/run", json={"query": "connect my account", "token": "t"})
    assert resp.json() == {"answer": "real url here"}


def noop() -> dict:
    """A tool that always succeeds and gives the model no reason to stop
    calling it again - used to simulate a model stuck in a repeat-call loop."""
    return {"ok": True}


class _AlwaysCallsToolModel(BaseLlm):
    """A fake model that never produces a final text answer - every turn is
    another tool call, forever, unless something external stops the loop."""

    _call_count: int = PrivateAttr(default=0)

    async def generate_content_async(self, llm_request, stream: bool = False):
        self._call_count += 1
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        function_call=types.FunctionCall(
                            id=f"call-{self._call_count}", name="noop", args={}
                        )
                    )
                ],
            )
        )


def test_run_stops_after_max_llm_calls_instead_of_looping_forever():
    # Regression test: a real agent got stuck making 257 identical tool calls
    # over ~4.5 minutes before the caller's HTTP client gave up, with nothing
    # on the server side ever stopping it. This proves the harness's
    # max_llm_calls cap actually bounds the loop, end to end through a real
    # ADK Runner, not just that the constant is set somewhere.
    model = _AlwaysCallsToolModel(model="fake-looping-model")
    agent = LlmAgent(
        model=model,
        name="loop_agent",
        instruction="call the noop tool",
        tools=[noop],
    )
    app = build_app(lambda token, mode: (agent, token, {}))
    client = TestClient(app)

    resp = client.post("/run", json={"query": "trigger the loop", "token": "t"})

    assert resp.status_code == 200
    assert model._call_count <= harness.MAX_LLM_CALLS_PER_RUN + 1
    assert "answer" in resp.json()
    assert resp.json()["answer"] != ""


class _SlowModel(BaseLlm):
    """A fake model that hangs well past the run timeout before it would ever
    answer - simulates a stuck or very slow turn."""

    async def generate_content_async(self, llm_request, stream: bool = False):
        await asyncio.sleep(5)
        yield LlmResponse(
            content=types.Content(
                role="model", parts=[types.Part(text="too late to matter")]
            )
        )


class _AnswersOnceModel(BaseLlm):
    """A fake model that returns a final text answer immediately, no tools."""

    async def generate_content_async(self, llm_request, stream: bool = False):
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text="done")])
        )


def test_run_returns_cleanly_on_timeout_instead_of_hanging(monkeypatch):
    # Regression test: a stuck run must return a clean message within the
    # wall-clock budget, not hang until the caller's connection is dropped
    # (which is what showed up in the browser as "Failed to fetch").
    monkeypatch.setattr(harness, "RUN_TIMEOUT_SECONDS", 0.2)
    agent = LlmAgent(
        model=_SlowModel(model="fake-slow-model"),
        name="slow_agent",
        instruction="answer the question",
    )
    app = build_app(lambda token, mode: (agent, token, {}))
    client = TestClient(app)

    resp = client.post("/run", json={"query": "hi", "token": "t"})

    assert resp.status_code == 200
    # The clean timeout message, not the model's never-reached answer.
    assert resp.json()["answer"] != ""
    assert "too late to matter" not in resp.json()["answer"]


def test_run_always_closes_the_runner_to_tear_down_mcp_sessions(monkeypatch):
    # The MCP SSE stream is only torn down when runner.close() runs; without it
    # the session lingers server-side for minutes as a zombie. Prove the handler
    # always closes the runner on a normal completion.
    closed = {"count": 0}
    original_close = InMemoryRunner.close

    async def counting_close(self):
        closed["count"] += 1
        return await original_close(self)

    monkeypatch.setattr(InMemoryRunner, "close", counting_close)

    agent = LlmAgent(
        model=_AnswersOnceModel(model="fake-fast-model"),
        name="fast_agent",
        instruction="answer the question",
    )
    app = build_app(lambda token, mode: (agent, token, {}))
    client = TestClient(app)

    resp = client.post("/run", json={"query": "hi", "token": "t"})

    assert resp.status_code == 200
    assert closed["count"] == 1
