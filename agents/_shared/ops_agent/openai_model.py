"""ADK BaseLlm implementation calling an OpenAI-compatible endpoint directly
via the official openai SDK, deliberately avoiding LiteLLM. See the March
2026 PyPI supply-chain compromise (PYSEC-2026-2): malicious litellm
1.82.7/1.82.8 releases shipped a credential-stealing payload (SSH keys,
cloud/K8s credentials) that executed automatically via a .pth file on every
Python process start.

Only supports what this demo's agents need: a single non-streaming turn of
text and/or function-calling against one endpoint (agentgateway's /openai
route). No multimodal content, no streaming, no thinking/caching."""
import json
from collections.abc import AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from openai import AsyncOpenAI
from pydantic import PrivateAttr


def _content_text(content: types.Content) -> str:
    return "".join(p.text or "" for p in (content.parts or []) if p.text)


def _tool_param(name: str, declaration: types.FunctionDeclaration) -> dict:
    parameters = declaration.parameters_json_schema or {"type": "object", "properties": {}}
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": declaration.description or "",
            "parameters": parameters,
        },
    }


def _content_to_messages(content: types.Content) -> list[dict]:
    """Converts one ADK Content turn into one or more OpenAI chat messages."""
    parts = content.parts or []
    function_responses = [p.function_response for p in parts if p.function_response]
    if function_responses:
        return [
            {
                "role": "tool",
                "tool_call_id": fr.id or "",
                "content": fr.response if isinstance(fr.response, str) else json.dumps(fr.response),
            }
            for fr in function_responses
        ]

    if content.role == "user":
        return [{"role": "user", "content": _content_text(content)}]

    text = _content_text(content) or None
    tool_calls = [
        {
            "id": p.function_call.id or "",
            "type": "function",
            "function": {
                "name": p.function_call.name,
                "arguments": json.dumps(p.function_call.args or {}),
            },
        }
        for p in parts
        if p.function_call
    ]
    message = {"role": "assistant", "content": text}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return [message]


def _request_to_messages(llm_request: LlmRequest) -> list[dict]:
    messages = []
    system_instruction = llm_request.config.system_instruction if llm_request.config else None
    if system_instruction:
        text = (
            system_instruction
            if isinstance(system_instruction, str)
            else _content_text(system_instruction)
        )
        if text:
            messages.append({"role": "system", "content": text})
    for content in llm_request.contents:
        messages.extend(_content_to_messages(content))
    return messages


def _response_message_to_content(message) -> types.Content:
    parts = []
    if message.content:
        parts.append(types.Part(text=message.content))
    for tool_call in message.tool_calls or []:
        parts.append(
            types.Part(
                function_call=types.FunctionCall(
                    id=tool_call.id,
                    name=tool_call.function.name,
                    args=json.loads(tool_call.function.arguments or "{}"),
                )
            )
        )
    return types.Content(role="model", parts=parts)


class OpenAIModel(BaseLlm):
    """Minimal OpenAI-compatible model backed by the official `openai`
    package - no LiteLLM. `api_key` only needs to be non-empty (the SDK
    refuses to send a request without one); the real request reaches the
    target endpoint however `api_base` routes it."""

    _client: AsyncOpenAI = PrivateAttr(default=None)

    def __init__(self, model: str, api_base: str, api_key: str = "unused", **kwargs):
        super().__init__(model=model, **kwargs)
        self._client = AsyncOpenAI(base_url=api_base, api_key=api_key)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        if stream:
            raise NotImplementedError("OpenAIModel does not support streaming")

        messages = _request_to_messages(llm_request)

        tools = None
        if llm_request.tools_dict:
            tool_params = []
            for name, tool in llm_request.tools_dict.items():
                declaration = tool._get_declaration()
                if declaration:
                    tool_params.append(_tool_param(name, declaration))
            tools = tool_params or None

        completion = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
        )
        content = _response_message_to_content(completion.choices[0].message)
        yield LlmResponse(content=content)
