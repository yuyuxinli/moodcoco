"""模拟人类用户的 Persona Agent。

从 eval-reference/personas/ 读 md 做 system prompt。
和 Coco（fast_agent / slow_agent）完全独立的 pydantic-ai Agent 实例，
只通过纯文本对话互通，不存在 prompt 串扰。
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from backend.llm_provider import PROJECT_ROOT, create_agent_model

PERSONA_DIR = PROJECT_ROOT / "eval-reference" / "personas"

PERSONA_IDS: dict[str, str] = {
    "yuyu": "玉玉.md",
    "ayao": "阿瑶.md",
    "xiaoyu": "小雨.md",
    "xiaoju": "小桔.md",
}

PERSONA_WRAPPER = """你正在扮演以下角色，与一个 AI 心理陪伴助手 Coco 对话。
严格保持角色的口吻、情绪、压力点、说话风格。

重要约束：
- 不调用任何工具、不输出 JSON、不用 markdown（列表、代码块、**加粗** 等）。
- 不用括号描写动作或心理（如「她皱了皱眉」这种不许）。
- 不跳出角色、不说「我是 AI/模型/用户」。
- 每次只说 1-3 句自然的中文对话台词，就像真人在微信里聊天。
- 允许错别字、不通顺、省略、没头没尾，真人本来就这样聊。

---

{persona_md}
"""


def list_personas() -> list[dict]:
    """返回可用的 persona 清单：[{id, name, preview}]。"""
    personas: list[dict] = []
    for pid, filename in PERSONA_IDS.items():
        path = PERSONA_DIR / filename
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        name = filename.removesuffix(".md")
        content_lines = [
            ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")
        ]
        preview = (" ".join(content_lines))[:100]
        personas.append({"id": pid, "name": name, "preview": preview})
    return personas


def _build_persona_system_prompt(persona_id: str) -> str:
    if persona_id not in PERSONA_IDS:
        raise ValueError(f"Unknown persona_id: {persona_id}")
    path = PERSONA_DIR / PERSONA_IDS[persona_id]
    persona_md = path.read_text(encoding="utf-8")
    return PERSONA_WRAPPER.format(persona_md=persona_md)


def _history_to_messages(history: list[dict]) -> list[ModelMessage]:
    """把 [{role: 'coco'|'persona', text}] 翻译成 pydantic-ai message list。

    从 persona agent 视角：Coco 的话是 user，persona 自己的话是 assistant。
    """
    messages: list[ModelMessage] = []
    for item in history:
        role = item.get("role")
        text = (item.get("text") or "").strip()
        if not text:
            continue
        if role == "coco":
            messages.append(ModelRequest(parts=[UserPromptPart(content=text)]))
        elif role == "persona":
            messages.append(ModelResponse(parts=[TextPart(content=text)]))
    return messages


async def run_persona_turn(
    persona_id: str,
    history: list[dict],
    latest_coco_msg: str | None,
) -> str:
    """跑一轮 persona 回复。

    Args:
        persona_id: yuyu / ayao / xiaoyu / xiaoju
        history: 之前的完整对话（不含本轮 latest_coco_msg）
        latest_coco_msg: 本轮 Coco 最新的话；首轮为 None（persona 主动开口）

    Returns:
        persona 的下一句台词
    """
    system_prompt = _build_persona_system_prompt(persona_id)
    agent: Agent[None, str] = Agent(
        create_agent_model(),
        system_prompt=system_prompt,
        retries=1,
    )

    message_history = _history_to_messages(history)

    if latest_coco_msg:
        user_msg = latest_coco_msg
    else:
        user_msg = (
            "（对话开始）现在你主动找 Coco 倾诉。"
            "请以这个角色的口吻，说一句最想对 Coco 说的开场白——"
            "可以是最近困扰你的事，或者想聊的话题。"
            "1-2 句话，像真人发微信那样，别太正式。"
        )

    result = await agent.run(user_msg, message_history=message_history)
    return (result.output or "").strip()
