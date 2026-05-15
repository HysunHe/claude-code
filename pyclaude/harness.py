"""
此文件由 Claude Code 源码中的 Harness/Query 主循环相关实现提炼并转写为 Python。
主要来源：
- src/query.ts
- src/services/tools/toolOrchestration.ts
- src/utils/messages.ts

当前文件职责：
- 定义最小可用的 HarnessState 与 HarnessAgent
- 实现 Think-Act-Observe-Repeat 主循环
- 从 assistant 消息中抽取 tool_use，并在观察 tool_result 后继续下一轮
- 提供 ScriptedModel 作为演示与测试用的模型适配器
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import uuid4

from .messages import AssistantMessage, Message, create_user_text_message, tool_use_block
from .tools import Tool, ToolUseContext, ToolUseRequest, run_tool_batch


class ModelAdapter(Protocol):
    async def complete(
        self,
        messages: list[Message],
        tools: list[Tool],
        context: ToolUseContext,
    ) -> AssistantMessage: ...


@dataclass
class HarnessState:
    messages: list[Message]
    turn_count: int = 0
    last_transition: str | None = None


@dataclass
class HarnessAgent:
    model: ModelAdapter
    tools: list[Tool]
    context: ToolUseContext = field(default_factory=ToolUseContext)
    max_turns: int = 12

    async def run(self, user_input: str, history: list[Message] | None = None) -> HarnessState:
        messages = list(history or [])
        messages.append(create_user_text_message(user_input))
        state = HarnessState(messages=messages, turn_count=0)

        while True:
            if state.turn_count >= self.max_turns:
                state.last_transition = "max_turns_reached"
                return state

            state.turn_count += 1
            assistant_message = await self.model.complete(state.messages, self.tools, self.context)
            state.messages.append(assistant_message)

            tool_calls = self._extract_tool_calls(assistant_message)
            if not tool_calls:
                state.last_transition = "completed"
                return state

            updates = await run_tool_batch(tool_calls, self.tools, self.context)
            for update in updates:
                if update.message is not None:
                    state.messages.append(update.message)
            state.last_transition = "tool_followup"

    def _extract_tool_calls(self, assistant_message: AssistantMessage) -> list[ToolUseRequest]:
        tool_calls: list[ToolUseRequest] = []
        for block in assistant_message.content:
            if block.get("type") != "tool_use":
                continue
            tool_calls.append(
                ToolUseRequest(
                    id=str(block["id"]),
                    name=str(block["name"]),
                    input=dict(block.get("input") or {}),
                )
            )
        return tool_calls


@dataclass
class ScriptedModel:
    plan: list[dict[str, Any]]
    model_name: str = "scripted-model"
    _cursor: int = 0

    async def complete(
        self,
        messages: list[Message],
        tools: list[Tool],
        context: ToolUseContext,
    ) -> AssistantMessage:
        if self._cursor >= len(self.plan):
            return AssistantMessage(content=[{"type": "text", "text": "Done."}], model=self.model_name)

        step = self.plan[self._cursor]
        self._cursor += 1

        content: list[dict[str, Any]] = []
        if text := step.get("text"):
            content.append({"type": "text", "text": text})
        for raw_tool in step.get("tool_uses", []):
            content.append(
                tool_use_block(
                    tool_id=str(raw_tool.get("id") or uuid4()),
                    name=str(raw_tool["name"]),
                    input=dict(raw_tool.get("input") or {}),
                )
            )
        return AssistantMessage(
            content=content or [{"type": "text", "text": "Done."}],
            model=self.model_name,
            stop_reason="tool_use" if any(block["type"] == "tool_use" for block in content) else "end_turn",
        )
