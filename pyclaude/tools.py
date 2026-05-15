"""
此文件由 Claude Code 源码中的工具编排层相关实现提炼并转写为 Python。
主要来源：
- src/services/tools/toolOrchestration.ts
- src/Tool.ts

当前文件职责：
- 定义 Tool、ToolUseContext、ToolUseRequest 抽象
- 提供工具查找与单次工具执行逻辑
- 提供与原始 TS 实现对应的工具批次划分与并发执行机制
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol

from .messages import UserMessage, create_tool_result_message


class ToolHandler(Protocol):
    async def __call__(self, tool_input: dict[str, Any], context: "ToolUseContext") -> Any: ...


@dataclass
class Tool:
    name: str
    handler: ToolHandler
    concurrency_safe: bool = False

    async def run(self, tool_input: dict[str, Any], context: "ToolUseContext") -> Any:
        return await self.handler(tool_input, context)


@dataclass
class ToolUseContext:
    state: dict[str, Any] = field(default_factory=dict)
    in_progress_tool_use_ids: set[str] = field(default_factory=set)


@dataclass
class ToolUseRequest:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolExecutionUpdate:
    message: UserMessage | None
    context: ToolUseContext


def find_tool_by_name(tools: list[Tool], name: str) -> Tool | None:
    for tool in tools:
        if tool.name == name:
            return tool
    return None


async def execute_tool_call(
    tool_use: ToolUseRequest,
    tools: list[Tool],
    context: ToolUseContext,
) -> ToolExecutionUpdate:
    tool = find_tool_by_name(tools, tool_use.name)
    if tool is None:
        return ToolExecutionUpdate(
            message=create_tool_result_message(
                tool_use.id,
                f"Unknown tool: {tool_use.name}",
                is_error=True,
            ),
            context=context,
        )

    context.in_progress_tool_use_ids.add(tool_use.id)
    try:
        result = await tool.run(tool_use.input, context)
        return ToolExecutionUpdate(
            message=create_tool_result_message(tool_use.id, result),
            context=context,
        )
    except Exception as exc:
        return ToolExecutionUpdate(
            message=create_tool_result_message(tool_use.id, str(exc), is_error=True),
            context=context,
        )
    finally:
        context.in_progress_tool_use_ids.discard(tool_use.id)


def partition_tool_calls(
    tool_calls: list[ToolUseRequest],
    tools: list[Tool],
) -> list[tuple[bool, list[ToolUseRequest]]]:
    batches: list[tuple[bool, list[ToolUseRequest]]] = []
    for call in tool_calls:
        tool = find_tool_by_name(tools, call.name)
        is_safe = bool(tool and tool.concurrency_safe)
        if batches and batches[-1][0] == is_safe and is_safe:
            batches[-1][1].append(call)
            continue
        batches.append((is_safe, [call]))
    return batches


async def run_tool_batch(
    tool_calls: list[ToolUseRequest],
    tools: list[Tool],
    context: ToolUseContext,
) -> list[ToolExecutionUpdate]:
    updates: list[ToolExecutionUpdate] = []
    for is_safe, batch in partition_tool_calls(tool_calls, tools):
        if is_safe:
            results = await asyncio.gather(
                *(execute_tool_call(call, tools, context) for call in batch)
            )
            updates.extend(results)
        else:
            for call in batch:
                updates.append(await execute_tool_call(call, tools, context))
    return updates


def sync_tool(
    name: str,
    fn: Callable[[dict[str, Any], ToolUseContext], Any],
    concurrency_safe: bool = False,
) -> Tool:
    async def handler(tool_input: dict[str, Any], context: ToolUseContext) -> Any:
        return fn(tool_input, context)

    return Tool(name=name, handler=handler, concurrency_safe=concurrency_safe)


def async_tool(
    name: str,
    fn: Callable[[dict[str, Any], ToolUseContext], Awaitable[Any]],
    concurrency_safe: bool = False,
) -> Tool:
    return Tool(name=name, handler=fn, concurrency_safe=concurrency_safe)
