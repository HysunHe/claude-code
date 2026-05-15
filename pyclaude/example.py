"""
此文件为 pyclaude 的最小可运行示例。
来源说明：
- 不是直接对应单一 TS 源文件
- 示例行为基于从以下源码中提炼出的核心机制构建：
  - src/query.ts
  - src/services/tools/toolOrchestration.ts
  - src/utils/messages.ts

当前文件职责：
- 演示 HarnessAgent 的 TAOR 主循环
- 演示并发安全工具的批量执行与 tool_result 回填
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyclaude import HarnessAgent, ScriptedModel, sync_tool


def grep_tool(tool_input, context):
    query = tool_input.get("query", "")
    return {"matches": [f"found:{query}:src/query.ts"]}


def read_tool(tool_input, context):
    path = tool_input.get("path", "")
    return {"path": path, "content": "query loop core"}


async def main() -> None:
    model = ScriptedModel(
        plan=[
            {
                "text": "先搜索 TAOR 主循环",
                "tool_uses": [
                    {"name": "grep", "input": {"query": "queryLoop"}},
                    {"name": "read", "input": {"path": "src/query.ts"}},
                ],
            },
            {
                "text": "已完成提取并准备生成 Python 版本。",
            },
        ]
    )
    agent = HarnessAgent(
        model=model,
        tools=[
            sync_tool("grep", grep_tool, concurrency_safe=True),
            sync_tool("read", read_tool, concurrency_safe=True),
        ],
    )
    state = await agent.run("提取 Harness TAOR 核心")
    for message in state.messages:
        print(message.type, message.content)
    print("transition=", state.last_transition)


if __name__ == "__main__":
    asyncio.run(main())
