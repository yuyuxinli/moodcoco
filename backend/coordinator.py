"""Fast ↔ Slow 协调器。

协作模式：慢思考产出**下一轮快思考的指导**，不是直接回用户。

- Fast 本轮：读 MEMORY.md + 上一轮的 SLOW_GUIDANCE.md → tool_call
- 若 `needs_deep_analysis=True` → 同步 await Slow loop
- Slow 产出写入 `backend/state/SLOW_GUIDANCE.md`，作为**下一轮** Fast 的 instructions
- 慢思考不再有"补充气泡"发给用户；用户只看到 Fast 一条回复
- 快思考对"上一轮指导"有最终决定权：可采用、部分采用、或忽略
"""

from __future__ import annotations

from typing import Any

from backend.fast import FastThinkDeps, fast_agent
from backend.llm_provider import PROJECT_ROOT
from backend.slow import SlowThinkDeps, slow_agent

MEMORY_FILE = PROJECT_ROOT / "backend" / "state" / "MEMORY.md"
GUIDANCE_FILE = PROJECT_ROOT / "backend" / "state" / "SLOW_GUIDANCE.md"


def _format_tool_call(tc: dict[str, Any]) -> str:
    name = tc["name"]
    args = tc["args"]
    if name == "ai_message":
        msgs = args.get("messages", [])
        tag = " ⚡deep" if args.get("needs_deep_analysis") else ""
        return f"💬 {' '.join(msgs)}{tag}"
    if name == "ai_options":
        opts = args.get("options", [])
        return f"🔘 options: {opts}"
    if name == "ai_mood_select":
        return f"🎚  mood_select: {args.get('greeting', '')}"
    if name == "ai_praise_popup":
        return f"✨ {args.get('text', '')}"
    if name == "ai_complete_conversation":
        return f"🏁 {args.get('summary', '')}"
    if name == "ai_body_sensation":
        return f"🫁 {args.get('description', '')}"
    if name == "ai_safety_brake":
        return f"🛑 SAFETY[{args.get('risk_level')}] {args.get('response', '')}"
    return f"{name}({args})"


def _read_guidance() -> str:
    if not GUIDANCE_FILE.exists():
        return ""
    return GUIDANCE_FILE.read_text(encoding="utf-8").strip()


def _write_guidance(text: str) -> None:
    GUIDANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    GUIDANCE_FILE.write_text(text.strip() + "\n" if text.strip() else "", encoding="utf-8")


def reset_guidance_for_demo() -> None:
    """清空 SLOW_GUIDANCE.md（session 开始或 adapter 跑新 feature 前调用）。"""
    _write_guidance("")


async def run_turn(user_msg: str, session_id: str = "demo-session") -> dict[str, Any]:
    """跑一轮对话：fast → (可选) slow → 写下一轮 guidance。

    Returns 本轮事件字典，供 CLI 打印和评估 adapter 诊断：
      - fast_tool_calls / fast_reply_text / needs_deep
      - slow_history：慢思考 tool 调用轨迹
      - slow_guidance_for_next_turn：写入 SLOW_GUIDANCE.md 的内容（不给用户）
      - supplement_text：**保留但语义改变** = slow_guidance_for_next_turn 的别名
        （为了向后兼容诊断代码，未来可删）
    """
    memory_text = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""
    prior_guidance = _read_guidance()

    fast_deps = FastThinkDeps(
        session_id=session_id,
        memory_text=memory_text,
        slow_guidance=prior_guidance,
    )
    await fast_agent.run(user_msg, deps=fast_deps)

    fast_reply_text = ""
    needs_deep = False
    print("\n[快思考]")
    if prior_guidance:
        print(f"  (referencing prior slow guidance {len(prior_guidance)} chars)")
    if not fast_deps.collected_tool_calls:
        print("  ⚠ (no tool call)")
    for tc in fast_deps.collected_tool_calls:
        print(f"  {_format_tool_call(tc)}")
        if tc["name"] == "ai_message":
            fast_reply_text = " ".join(tc["args"].get("messages", []))
            if tc["args"].get("needs_deep_analysis"):
                needs_deep = True

    slow_guidance_for_next_turn = ""
    slow_history: list[str] = []
    if needs_deep:
        print("\n[慢思考 loop 运行中（产出下一轮指导，不回用户）…]")
        slow_deps = SlowThinkDeps(
            session_id=session_id,
            user_message=user_msg,
            fast_reply_text=fast_reply_text,
        )
        result = await slow_agent.run(user_msg, deps=slow_deps)
        slow_guidance_for_next_turn = (result.output or "").strip()
        slow_history = list(slow_deps.tool_call_history)
        print(f"  tool 轨迹: {slow_history}")
        _write_guidance(slow_guidance_for_next_turn)
        if slow_guidance_for_next_turn:
            preview = slow_guidance_for_next_turn.replace("\n", " ")[:100]
            print(f"  → 已写入 SLOW_GUIDANCE.md（下一轮 Fast 参考）: {preview}…")

    return {
        "fast_tool_calls": fast_deps.collected_tool_calls,
        "fast_reply_text": fast_reply_text,
        "needs_deep": needs_deep,
        "slow_guidance_for_next_turn": slow_guidance_for_next_turn,
        "supplement_text": slow_guidance_for_next_turn,  # deprecated alias
        "slow_history": slow_history,
        "prior_guidance_used": bool(prior_guidance),
    }
