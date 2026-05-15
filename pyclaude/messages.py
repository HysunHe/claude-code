"""
此文件由 Claude Code 源码中的消息层相关实现提炼并转写为 Python。
主要来源：
- src/utils/messages.ts

当前文件职责：
- 定义简化后的消息数据结构
- 提供 text/tool_use/tool_result 内容块构造函数
- 提供 user/assistant/tool_result 消息构造函数
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

ContentBlock = dict[str, Any]
Role = Literal["user", "assistant", "system"]
MessageType = Literal["user", "assistant", "system", "stream_event", "stream_request_start"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Message:
    type: MessageType
    role: Role
    content: list[ContentBlock]
    uuid: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=utc_now_iso)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class AssistantMessage(Message):
    model: str = "mock-model"
    stop_reason: str | None = None

    def __init__(
        self,
        content: list[ContentBlock],
        model: str = "mock-model",
        stop_reason: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            type="assistant",
            role="assistant",
            content=content,
            meta=meta or {},
        )
        self.model = model
        self.stop_reason = stop_reason


@dataclass
class UserMessage(Message):
    def __init__(
        self,
        content: list[ContentBlock],
        meta: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(type="user", role="user", content=content, meta=meta or {})


@dataclass
class SystemMessage(Message):
    def __init__(
        self,
        content: list[ContentBlock],
        meta: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            type="system",
            role="system",
            content=content,
            meta=meta or {},
        )


def text_block(text: str) -> ContentBlock:
    return {"type": "text", "text": text}


def tool_use_block(tool_id: str, name: str, input: dict[str, Any]) -> ContentBlock:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": input}


def tool_result_block(tool_use_id: str, content: Any, is_error: bool = False) -> ContentBlock:
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": content,
        "is_error": is_error,
    }


def create_user_text_message(text: str, meta: dict[str, Any] | None = None) -> UserMessage:
    return UserMessage(content=[text_block(text)], meta=meta)


def create_assistant_text_message(
    text: str,
    model: str = "mock-model",
    stop_reason: str | None = None,
    meta: dict[str, Any] | None = None,
) -> AssistantMessage:
    return AssistantMessage(
        content=[text_block(text)],
        model=model,
        stop_reason=stop_reason,
        meta=meta,
    )


def create_tool_result_message(
    tool_use_id: str,
    content: Any,
    is_error: bool = False,
    meta: dict[str, Any] | None = None,
) -> UserMessage:
    return UserMessage(
        content=[tool_result_block(tool_use_id=tool_use_id, content=content, is_error=is_error)],
        meta=meta,
    )
