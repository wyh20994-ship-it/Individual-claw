from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


MessageRole = Literal["system", "user", "assistant", "tool"]


class ChatMessage(BaseModel):
    role: MessageRole
    content: str = ""
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class LLMRequest(BaseModel):
    messages: list[ChatMessage]
    provider: str | None = None
    model: str | None = None
    tools: list[dict[str, Any]] | None = None
    max_tokens: int | None = None
    temperature: float | None = None


class LLMMessage(BaseModel):
    role: str = "assistant"
    content: str | None = ""
    tool_calls: list[dict[str, Any]] | None = None


class LLMResponse(BaseModel):
    message: LLMMessage
    usage: dict[str, Any] | None = None


class ToolCall(BaseModel):
    id: str = ""
    function: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    result: str


class PlanResult(BaseModel):
    goal: str = ""
    plan: list[str] = Field(default_factory=list)
    need_tools: bool = True
    thought: str = ""


class RpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int = "0"
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class RpcError(BaseModel):
    code: int
    message: str


class RpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int
    result: Any | None = None
    error: RpcError | None = None


class ConversationEntry(BaseModel):
    user_id: str
    role: Literal["user", "assistant"]
    content: str
    timestamp: str
    channel: str | None = None
    message_id: str | None = None


class MemoryIndexEntry(BaseModel):
    filename: str
    description: str


class MemoryExtractionResult(BaseModel):
    entries: list[MemoryIndexEntry] = Field(default_factory=list)
    notes: dict[str, str] = Field(default_factory=dict)


class SandboxCommand(BaseModel):
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SandboxResult(BaseModel):
    ok: bool
    output: str = ""
    error: str | None = None
