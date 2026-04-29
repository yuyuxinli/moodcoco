"""Slow Thinking Agent — PydanticAI 实现。

Agent loop：读 Skill → 写记忆 → 必要时多轮迭代，直到产出**给快思考的指导**。
不限时，由 agent 自己决定何时结束。

**关键语义**：Slow 的 output 不是给用户看的气泡，而是写入 `backend/state/SLOW_GUIDANCE.md`
作为**下一轮 Fast 的 instructions 参考**。Fast 自己决定是否采用。
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext

from backend.llm_provider import PROJECT_ROOT, create_agent_model, load_prompt

logger = logging.getLogger("backend.slow")


def _resolve_skills_dir() -> Path:
    """SKILLS_DIR 解析：环境变量 MOODCOCO_SKILLS_DIR 优先，相对路径基于 PROJECT_ROOT。

    用于让 SJTU 同学指向他们自己的 bundle 跑 web 调试，例如：
        MOODCOCO_SKILLS_DIR=SJTU_skills/moodcoco-psych-companion-openclaw-v1/skills
    """
    override = os.environ.get("MOODCOCO_SKILLS_DIR")
    if not override:
        return PROJECT_ROOT / "backend" / "skills"
    path = Path(override).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


SKILLS_DIR = _resolve_skills_dir()
MEMORY_FILE = PROJECT_ROOT / "backend" / "state" / "MEMORY.md"


@dataclass
class SlowThinkDeps:
    """慢思考 Agent 的运行时依赖。"""

    session_id: str
    user_message: str
    fast_reply_text: str = ""  # 同轮 fast-think 回复，用于避免复读
    tool_call_history: list[str] = field(default_factory=list)
    fast_deps: Any | None = None
    reasoning_trail: list[str] = field(default_factory=list)
    search_cache: dict[str, str] = field(default_factory=dict)
    pending_actions: list[dict] = field(default_factory=list)
    carryover_inject: list[str] = field(default_factory=list)
    carryover_skills: list[str] = field(default_factory=list)
    carryover_retrieval: str = ""
    mutation_count_this_iter: int = 0


VOICE_MUTATION_TOOL_GUIDE = """
## Voice 模式工具选用指南

When in voice mode (fast_deps available):
- Use slow_attach_skill_to_fast(name) when the conversation needs a SJTU skill
  (listen / validation / face-decision / relationship-guide / etc).
- Use slow_set_fast_retrieval(text) when you've gathered context that should
  replace the retrieval block (compact, <=200 chars).
- Use slow_inject_to_fast(text) for short notes that augment but don't replace.
- Across iters in one turn, prefer using >=2 distinct tools to enrich Fast.
- For non-trivial emotional or relationship turns, the strongest default is:
  attach the most relevant skill, set a compact retrieval block, then inject one
  short next-step note. Do not route every turn through only slow_inject_to_fast.
"""


SLOW_SYSTEM_PROMPT = "\n\n".join(
    [
        load_prompt("backend/prompts/SOUL.md"),
        load_prompt("backend/prompts/IDENTITY.md"),
        load_prompt("backend/prompts/AGENTS.md"),
        load_prompt("backend/prompts/slow-instructions.md"),
        VOICE_MUTATION_TOOL_GUIDE,
    ]
)


slow_agent: Agent[SlowThinkDeps, str] = Agent(
    create_agent_model(),
    deps_type=SlowThinkDeps,
    output_type=str,
    system_prompt=SLOW_SYSTEM_PROMPT,
    retries=1,
)


@slow_agent.instructions
async def inject_context(ctx: RunContext[SlowThinkDeps]) -> str:
    memory_text = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""
    parts = [
        f"## 本轮用户消息\n\n{ctx.deps.user_message}",
        f"## 快思考已回复（不要复读）\n\n{ctx.deps.fast_reply_text or '（无）'}",
    ]
    if memory_text.strip():
        parts.append(f"## 当前长期记忆 MEMORY.md\n\n{memory_text}")
    return "\n\n".join(parts)


def _turn_id() -> str:
    try:
        from backend.voice.plugins._context import voice_turn_ctx

        return voice_turn_ctx.get() or "unknown"
    except (ImportError, LookupError, RuntimeError):
        return "unknown"


def _log_slow_tool_call(
    ctx: RunContext[SlowThinkDeps],
    *,
    tool: str,
    started_at: float,
    text_len: int = 0,
) -> None:
    logger.info(
        "slow_tool_call",
        extra={
            "session_id": ctx.deps.session_id,
            "turn_id": _turn_id(),
            "phase": "slow",
            "tool": tool,
            "text_len": text_len,
            "latency_ms": round((time.monotonic() - started_at) * 1000),
            "mutations_made": ctx.deps.mutation_count_this_iter,
        },
    )


def _append_lru(items: list[str], value: str, *, limit: int) -> None:
    normalized = value.strip()
    if not normalized:
        return
    if normalized in items:
        items.remove(normalized)
    items.append(normalized)
    del items[:-limit]


@slow_agent.tool
async def list_skills(ctx: RunContext[SlowThinkDeps]) -> list[str]:
    """列出所有可用 Skill 名称。"""
    started_at = time.monotonic()
    ctx.deps.tool_call_history.append("list_skills")
    if not SKILLS_DIR.exists():
        _log_slow_tool_call(ctx, tool="list_skills", started_at=started_at)
        return []
    skills = sorted(
        p.name for p in SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").exists()
    )
    _log_slow_tool_call(ctx, tool="list_skills", started_at=started_at)
    return skills


@slow_agent.tool
async def read_skill(ctx: RunContext[SlowThinkDeps], skill_name: str) -> str:
    """读取指定 Skill 的 SKILL.md 内容。

    Args:
        skill_name: skill 目录名，如 "diary"、"breathing-ground"、"relationship-guide"。
    """
    started_at = time.monotonic()
    ctx.deps.tool_call_history.append(f"read_skill({skill_name})")
    skill_path = SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_path.exists():
        available = ", ".join(
            p.name for p in SKILLS_DIR.iterdir() if p.is_dir()
        )
        _log_slow_tool_call(ctx, tool="read_skill", started_at=started_at)
        return f"Skill not found: {skill_name}. Available: {available}"
    content = skill_path.read_text(encoding="utf-8")
    _log_slow_tool_call(ctx, tool="read_skill", started_at=started_at, text_len=len(content))
    return content


@slow_agent.tool
async def write_memory(
    ctx: RunContext[SlowThinkDeps],
    section: str,
    content: str,
) -> str:
    """把长期记忆条目追加到 MEMORY.md 的指定小节。

    Args:
        section: MEMORY.md 里的二级标题，如 "## 跨关系模式"、"## 重要时间节点"、
            "## 核心信念变化轨迹"；如不存在会自动创建。
        content: 要追加的 Markdown 内容（建议一行 bullet，含日期标签）。
    """
    started_at = time.monotonic()
    ctx.deps.tool_call_history.append(f"write_memory({section})")
    _append_to_memory_section(section, content, ctx.deps.session_id)
    _log_slow_tool_call(ctx, tool="write_memory", started_at=started_at, text_len=len(content))
    return f"written to {section}"


@slow_agent.tool
async def slow_inject_to_fast(ctx: RunContext[SlowThinkDeps], system_text: str) -> str:
    """Inject short same-turn system guidance into the voice Fast agent."""
    started_at = time.monotonic()
    ctx.deps.tool_call_history.append("slow_inject_to_fast")
    if ctx.deps.fast_deps is None:
        ctx.deps.mutation_count_this_iter += 1
        _log_slow_tool_call(
            ctx,
            tool="slow_inject_to_fast",
            started_at=started_at,
            text_len=len(system_text),
        )
        return "skipped: fast_deps unavailable"
    ctx.deps.fast_deps.dynamic_inject.append(system_text)
    _append_lru(ctx.deps.carryover_inject, system_text, limit=3)
    ctx.deps.reasoning_trail.append(f"inject:{system_text[:80]}")
    ctx.deps.mutation_count_this_iter += 1
    _log_slow_tool_call(
        ctx,
        tool="slow_inject_to_fast",
        started_at=started_at,
        text_len=len(system_text),
    )
    return "injected to fast"


@slow_agent.tool
async def slow_set_fast_retrieval(ctx: RunContext[SlowThinkDeps], block: str) -> str:
    """Replace the voice Fast agent's same-turn retrieval block."""
    started_at = time.monotonic()
    ctx.deps.tool_call_history.append("slow_set_fast_retrieval")
    compact_block = block.strip()
    if len(compact_block) > 200:
        compact_block = compact_block[:197].rstrip() + "..."
    if ctx.deps.fast_deps is None:
        ctx.deps.mutation_count_this_iter += 1
        _log_slow_tool_call(
            ctx,
            tool="slow_set_fast_retrieval",
            started_at=started_at,
            text_len=len(compact_block),
        )
        return "skipped: fast_deps unavailable"
    ctx.deps.fast_deps.retrieval_block = compact_block
    ctx.deps.carryover_retrieval = compact_block
    ctx.deps.search_cache[ctx.deps.user_message] = compact_block
    ctx.deps.mutation_count_this_iter += 1
    _log_slow_tool_call(
        ctx,
        tool="slow_set_fast_retrieval",
        started_at=started_at,
        text_len=len(compact_block),
    )
    return "retrieval block set"


@slow_agent.tool
async def slow_attach_skill_to_fast(ctx: RunContext[SlowThinkDeps], skill_name: str) -> str:
    """Read one Skill and attach its content to the voice Fast agent."""
    started_at = time.monotonic()
    ctx.deps.tool_call_history.append(f"slow_attach_skill_to_fast({skill_name})")
    skill_text = await read_skill(ctx, skill_name)
    if skill_text.startswith("Skill not found:"):
        ctx.deps.mutation_count_this_iter += 1
        _log_slow_tool_call(
            ctx,
            tool="slow_attach_skill_to_fast",
            started_at=started_at,
            text_len=len(skill_text),
        )
        return skill_text
    if ctx.deps.fast_deps is None:
        ctx.deps.mutation_count_this_iter += 1
        _log_slow_tool_call(
            ctx,
            tool="slow_attach_skill_to_fast",
            started_at=started_at,
            text_len=len(skill_text),
        )
        return "skipped: fast_deps unavailable"
    ctx.deps.fast_deps.skill_bundle.append(skill_text)
    if skill_text not in ctx.deps.carryover_skills:
        ctx.deps.carryover_skills.append(skill_text)
    ctx.deps.reasoning_trail.append(f"skill:{skill_name}")
    ctx.deps.mutation_count_this_iter += 1
    _log_slow_tool_call(
        ctx,
        tool="slow_attach_skill_to_fast",
        started_at=started_at,
        text_len=len(skill_text),
    )
    return f"attached skill to fast: {skill_name}"


def _append_to_memory_section(section: str, content: str, session_id: str) -> None:
    """将 content 追加到 MEMORY.md 的指定 section 下；section 不存在则创建。"""
    header = section if section.startswith("## ") else f"## {section}"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"- [{stamp} / {session_id}] {content.strip()}"

    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""

    if header in existing:
        lines = existing.split("\n")
        new_lines: list[str] = []
        inserted = False
        in_target_section = False
        for line in lines:
            if line.strip() == header:
                new_lines.append(line)
                in_target_section = True
                continue
            if in_target_section and line.startswith("## ") and line.strip() != header:
                if not inserted:
                    new_lines.append(entry)
                    inserted = True
                in_target_section = False
            new_lines.append(line)
        if in_target_section and not inserted:
            new_lines.append(entry)
        MEMORY_FILE.write_text("\n".join(new_lines), encoding="utf-8")
    else:
        block = existing.rstrip() + f"\n\n{header}\n{entry}\n"
        MEMORY_FILE.write_text(block, encoding="utf-8")


def reset_memory_file_for_demo() -> None:
    """供 CLI/测试调用：把 MEMORY.md 重置到初始骨架。"""
    skeleton = (
        "# 长期记忆锚点\n\n"
        "<!-- 此文件由慢思考 write_memory 维护 -->\n\n"
        "## 跨关系模式\n\n"
        "## 重要时间节点\n\n"
        "## 核心信念变化轨迹\n"
    )
    MEMORY_FILE.write_text(skeleton, encoding="utf-8")
