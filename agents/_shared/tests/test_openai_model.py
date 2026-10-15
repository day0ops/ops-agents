import asyncio
import json

from google.adk.models.llm_request import LlmRequest
from google.adk.tools.base_tool import BaseTool
from google.genai import types
from ops_agent.openai_model import OpenAIModel, _repair_tool_call_ids


def _run(coro):
    return asyncio.run(coro)


async def _collect(agen):
    return [item async for item in agen]


class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = _FakeFunction(name, arguments)


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, message):
        self.message = message


class _FakeCompletion:
    def __init__(self, message):
        self.choices = [_FakeChoice(message)]


class _FakeCompletions:
    def __init__(self, message, captured):
        self._message = message
        self._captured = captured

    async def create(self, **kwargs):
        self._captured.update(kwargs)
        return _FakeCompletion(self._message)


class _FakeChat:
    def __init__(self, message, captured):
        self.completions = _FakeCompletions(message, captured)


class _FakeClient:
    def __init__(self, message, captured):
        self.chat = _FakeChat(message, captured)


def _model_with_fake_client(message, captured):
    model = OpenAIModel(model="gpt-4o-mini", api_base="http://gw/openai", api_key="unused")
    model._client = _FakeClient(message, captured)
    return model


def test_sends_system_instruction_and_user_message():
    captured = {}
    model = _model_with_fake_client(_FakeMessage(content="hi"), captured)
    request = LlmRequest(
        model="gpt-4o-mini",
        contents=[types.Content(role="user", parts=[types.Part(text="list repos")])],
    )
    request.config.system_instruction = "You are a repo agent."

    responses = _run(_collect(model.generate_content_async(request)))

    assert captured["model"] == "gpt-4o-mini"
    assert captured["messages"][0] == {"role": "system", "content": "You are a repo agent."}
    assert captured["messages"][1] == {"role": "user", "content": "list repos"}
    assert len(responses) == 1
    assert responses[0].content.parts[0].text == "hi"


def test_sends_tool_declarations_from_tools_dict():
    captured = {}
    model = _model_with_fake_client(_FakeMessage(content="ok"), captured)

    class FakeTool(BaseTool):
        def __init__(self):
            super().__init__(name="list_repos", description="List repos")

        def _get_declaration(self):
            return types.FunctionDeclaration(
                name="list_repos",
                description="List repos",
                parameters_json_schema={"type": "object", "properties": {}},
            )

    request = LlmRequest(
        model="gpt-4o-mini",
        contents=[types.Content(role="user", parts=[types.Part(text="hi")])],
        tools_dict={"list_repos": FakeTool()},
    )

    _run(_collect(model.generate_content_async(request)))

    assert captured["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "list_repos",
                "description": "List repos",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]


def test_omits_tools_param_when_no_tools_declared():
    captured = {}
    model = _model_with_fake_client(_FakeMessage(content="ok"), captured)
    request = LlmRequest(
        model="gpt-4o-mini",
        contents=[types.Content(role="user", parts=[types.Part(text="hi")])],
    )

    _run(_collect(model.generate_content_async(request)))

    assert captured["tools"] is None


def test_parses_tool_call_response_into_function_call_parts():
    captured = {}
    message = _FakeMessage(
        content=None,
        tool_calls=[_FakeToolCall(id="call_1", name="list_repos", arguments="{}")],
    )
    model = _model_with_fake_client(message, captured)
    request = LlmRequest(
        model="gpt-4o-mini",
        contents=[types.Content(role="user", parts=[types.Part(text="list repos")])],
    )

    responses = _run(_collect(model.generate_content_async(request)))

    assert len(responses) == 1
    part = responses[0].content.parts[0]
    assert part.function_call.id == "call_1"
    assert part.function_call.name == "list_repos"
    assert part.function_call.args == {}


def test_sends_model_turn_with_tool_call_as_assistant_message():
    captured = {}
    model = _model_with_fake_client(_FakeMessage(content="done"), captured)
    request = LlmRequest(
        model="gpt-4o-mini",
        contents=[
            types.Content(role="user", parts=[types.Part(text="list repos")]),
            types.Content(
                role="model",
                parts=[
                    types.Part(
                        function_call=types.FunctionCall(id="call_1", name="list_repos", args={})
                    )
                ],
            ),
        ],
    )

    _run(_collect(model.generate_content_async(request)))

    assistant_message = captured["messages"][1]
    assert assistant_message["role"] == "assistant"
    assert assistant_message["tool_calls"] == [
        {"id": "call_1", "type": "function", "function": {"name": "list_repos", "arguments": "{}"}}
    ]


def test_sends_function_response_as_tool_message():
    captured = {}
    model = _model_with_fake_client(_FakeMessage(content="done"), captured)
    request = LlmRequest(
        model="gpt-4o-mini",
        contents=[
            types.Content(role="user", parts=[types.Part(text="list repos")]),
            types.Content(
                role="model",
                parts=[
                    types.Part(
                        function_call=types.FunctionCall(id="call_1", name="list_repos", args={})
                    )
                ],
            ),
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            id="call_1", name="list_repos", response={"repos": ["a"]}
                        )
                    )
                ],
            ),
        ],
    )

    _run(_collect(model.generate_content_async(request)))

    tool_message = captured["messages"][-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call_1"
    assert json.loads(tool_message["content"]) == {"repos": ["a"]}


def test_repair_pairs_missing_tool_call_ids_by_position():
    # Regression: a missing id on a tool call and its result means the OpenAI
    # API can't pair them, so the model never sees the result and re-calls the
    # same tool forever (observed live as the Accounts Agent looping until the
    # step cap fired). Missing ids must be filled with a matching pair.
    messages = [
        {"role": "user", "content": "q"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "", "type": "function",
                 "function": {"name": "get_account_detail", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "tool_call_id": "", "content": "result"},
    ]
    _repair_tool_call_ids(messages)
    call_id = messages[1]["tool_calls"][0]["id"]
    assert call_id != ""
    assert messages[2]["tool_call_id"] == call_id


def test_repair_leaves_real_ids_untouched():
    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {"id": "call_abc", "type": "function",
                 "function": {"name": "t", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "tool_call_id": "call_abc", "content": "r"},
    ]
    _repair_tool_call_ids(messages)
    assert messages[0]["tool_calls"][0]["id"] == "call_abc"
    assert messages[1]["tool_call_id"] == "call_abc"


def test_repair_pairs_multiple_turns_distinctly_and_in_order():
    messages = [
        {"role": "assistant", "tool_calls": [
            {"id": "", "type": "function", "function": {"name": "t", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "", "content": "r0"},
        {"role": "assistant", "tool_calls": [
            {"id": "", "type": "function", "function": {"name": "t", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "", "content": "r1"},
    ]
    _repair_tool_call_ids(messages)
    assert messages[0]["tool_calls"][0]["id"] == messages[1]["tool_call_id"]
    assert messages[2]["tool_calls"][0]["id"] == messages[3]["tool_call_id"]
    assert messages[0]["tool_calls"][0]["id"] != messages[2]["tool_calls"][0]["id"]
