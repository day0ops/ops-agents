from fastapi.testclient import TestClient
from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types
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
    assert model._call_count <= 10
    assert "answer" in resp.json()
    assert resp.json()["answer"] != ""
