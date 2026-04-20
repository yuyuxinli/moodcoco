"""Slow Thinking Agent — PydanticAI 实现。

Agent loop：读 Skill → 写记忆 → 必要时多轮迭代，直到产出**给快思考的指导**。
不限时，由 agent 自己决定何时结束。

**关键语义**：Slow 的 output 不是给用户看的气泡，而是写入 `ai-companion/SLOW_GUIDANCE.md`
作为**下一轮 Fast 的 instructions 参考**。Fast 自己决定是否采用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from pydantic_ai import Agent, RunContext

from backend.llm_provider import PROJECT_ROOT, create_agent_model, load_prompt

SKILLS_DIR = PROJECT_ROOT / "ai-companion" / "skills"
MEMORY_FILE = PROJECT_ROOT / "ai-companion" / "MEMORY.md"


@dataclass
class SlowThinkDeps:
    """慢思考 Agent 的运行时依赖。"""

    session_id: str
    user_message: str
    fast_reply_text: str = ""  # 同轮 fast-think 回复，用于避免复读
    tool_call_history: list[str] = field(default_factory=list)


SLOW_SYSTEM_PROMPT = "\n\n".join(
    [
        load_prompt("ai-companion/SOUL.md"),
        load_prompt("ai-companion/IDENTITY.md"),
        load_prompt("ai-companion/AGENTS.md"),
        load_prompt("backend/prompts/slow-instructions.md"),
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


@slow_agent.tool
async def list_skills(ctx: RunContext[SlowThinkDeps]) -> list[str]:
    """列出所有可用 Skill 名称。"""
    ctx.deps.tool_call_history.append("list_skills")
    if not SKILLS_DIR.exists():
        return []
    return sorted(
        p.name for p in SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").exists()
    )


@slow_agent.tool
async def read_skill(ctx: RunContext[SlowThinkDeps], skill_name: str) -> str:
    """读取指定 Skill 的 SKILL.md 内容。

    Args:
        skill_name: skill 目录名，如 "diary"、"breathing-ground"、"relationship-guide"。
    """
    ctx.deps.tool_call_history.append(f"read_skill({skill_name})")
    skill_path = SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_path.exists():
        available = ", ".join(
            p.name for p in SKILLS_DIR.iterdir() if p.is_dir()
        )
        return f"Skill not found: {skill_name}. Available: {available}"
    return skill_path.read_text(encoding="utf-8")


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
    ctx.deps.tool_call_history.append(f"write_memory({section})")
    _append_to_memory_section(section, content, ctx.deps.session_id)
    return f"written to {section}"


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
