"""Fast Thinking Agent — PydanticAI 实现。

7 个 UI Tool 驱动前端展示；LLM 的 assistant text 不会被消费，
所有用户可见内容通过 tool 推送（在 prompt 中强制约束）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeAlias

from pydantic_ai import Agent, RunContext

from backend.llm_provider import create_agent_model, load_prompt

AiOptionItem: TypeAlias = str | dict[str, str]


@dataclass
class FastThinkDeps:
    """快思考 Agent 的运行时依赖。"""

    session_id: str
    memory_text: str  # MEMORY.md 当前内容（动态注入 instructions）
    slow_guidance: str = ""  # 上一轮慢思考产出的指导，Fast 可参考可忽略
    collected_tool_calls: list[dict[str, Any]] = field(default_factory=list)


SYSTEM_PROMPT = "\n\n".join(
    [
        load_prompt("backend/prompts/SOUL.md"),
        load_prompt("backend/prompts/IDENTITY.md"),
        load_prompt("backend/prompts/AGENTS.md"),
        load_prompt("backend/prompts/fast-instructions.md"),
        load_prompt("backend/prompts/fast-tools.md"),
    ]
)


fast_agent: Agent[FastThinkDeps, str] = Agent(
    create_agent_model(),
    deps_type=FastThinkDeps,
    system_prompt=SYSTEM_PROMPT,
    retries=0,
)


@fast_agent.instructions
async def inject_memory(ctx: RunContext[FastThinkDeps]) -> str:
    """per-request 注入当前 MEMORY.md 内容。"""
    if not ctx.deps.memory_text.strip():
        return ""
    return f"## 当前长期记忆（MEMORY.md）\n\n{ctx.deps.memory_text}"


@fast_agent.instructions
async def inject_slow_guidance(ctx: RunContext[FastThinkDeps]) -> str:
    """注入上一轮慢思考对话后产出的指导，作为快思考本轮决策的参考。

    快思考可以采用、部分采用、或完全忽略这份指导——它只是上一轮沉淀的思考，
    本轮的主导权仍在快思考自己判断。
    """
    if not ctx.deps.slow_guidance.strip():
        return ""
    return (
        "## 上一轮慢思考指导（参考，非必须遵守）\n\n"
        "以下是慢思考对上一轮对话沉淀出的指导。你本轮可参考，也可根据\n"
        "用户最新消息自行决定是否采用。如果当前语境已经漂移，请忽略。\n\n"
        f"{ctx.deps.slow_guidance}"
    )


def _record(ctx: RunContext[FastThinkDeps], name: str, args: dict[str, Any]) -> None:
    ctx.deps.collected_tool_calls.append({"name": name, "args": args})


@fast_agent.tool
async def ai_message(
    ctx: RunContext[FastThinkDeps],
    messages: list[str],
    needs_deep_analysis: bool,
) -> str:
    """向用户发送文本消息。needs_deep_analysis=True 触发慢思考深度分析。

    急性焦虑、日记记录、关系困扰、本周回顾等场景必须置 True，
    触发规则见 fast-tools.md。
    """
    _record(
        ctx,
        "ai_message",
        {"messages": messages, "needs_deep_analysis": needs_deep_analysis},
    )
    return "消息已发送"


@fast_agent.tool
async def ai_options(
    ctx: RunContext[FastThinkDeps],
    options: list[AiOptionItem],
    text: str = "",
) -> str:
    """展示 2-4 个引导选项。兼容字符串数组或 {id, text} 对象数组。"""
    _record(ctx, "ai_options", {"options": options, "text": text})
    return "选项已展示"


@fast_agent.tool
async def ai_mood_select(
    ctx: RunContext[FastThinkDeps],
    greeting: str,
) -> str:
    """引导用户选择心情（弹滑块）。用户明确提到心情词时优先调用，
    一旦调用本轮结束，不再补发其他 tool。"""
    _record(ctx, "ai_mood_select", {"greeting": greeting})
    return "心情选择已展示"


@fast_agent.tool
async def ai_praise_popup(
    ctx: RunContext[FastThinkDeps],
    text: str,
) -> str:
    """2-8 字短语夸夸弹幕，用户表达正向行动/特质时调用，可与 ai_message 并行。"""
    _record(ctx, "ai_praise_popup", {"text": text})
    return "夸夸已展示"


@fast_agent.tool
async def ai_complete_conversation(
    ctx: RunContext[FastThinkDeps],
    summary: str,
) -> str:
    """对话收尾小结。仅当用户明确表达收尾意图时调用。"""
    _record(ctx, "ai_complete_conversation", {"summary": summary})
    return "对话小结已展示"


@fast_agent.tool
async def ai_body_sensation(
    ctx: RunContext[FastThinkDeps],
    description: str,
) -> str:
    """身体感知引导（仅限平静状态）。急性焦虑禁用。"""
    _record(ctx, "ai_body_sensation", {"description": description})
    return "身体感知引导已发送"


@fast_agent.tool
async def ai_safety_brake(
    ctx: RunContext[FastThinkDeps],
    risk_level: str,
    response: str,
) -> str:
    """检测到自伤/自杀风险立即触发。risk_level: low/medium/high。"""
    _record(ctx, "ai_safety_brake", {"risk_level": risk_level, "response": response})
    return "安全响应已触发"
