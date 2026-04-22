"""
moodcoco Fast/Slow Thinking MVP adapter for Evolve V2.

Dynamic multi-turn conversation testing:
1. Load rich persona (personas/*.md) + scenario (test_scripts/*.json)
2. Simulate realistic user via Claude Opus 4.7 (messy, emotional, topic-drifting)
3. Send each simulated message to moodcoco's Fast+Slow coordinator
   (backend.coordinator.run_turn — NOT OpenClaw CLI; we've migrated away)
4. Capture full transcript with fast tool_calls + slow tool_call_history + MEMORY diff

All dimensions are LLM-judged by Codex (Evolve V2 C agent). Adapter returns
scores={} and lets the framework handle scoring.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Make backend/ importable when evolve engine loads this adapter from project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

prerequisites = [
    {
        "name": "python-venv",
        "check": f"test -x {PROJECT_ROOT}/.venv/bin/python",
        "install": f"cd {PROJECT_ROOT} && python3 -m venv .venv && .venv/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e .",
        "scope": "project",
    },
    {
        "name": "env-file",
        "check": f"test -f {PROJECT_ROOT}/.env",
        "install": f"cp {PROJECT_ROOT}/.env.example {PROJECT_ROOT}/.env  # then fill OPENROUTER_API_KEY",
        "scope": "project",
    },
]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
PERSONA_MODEL = "anthropic/claude-opus-4.7"   # LLM 扮 persona
COCO_MODEL_ENV = "minimax/minimax-m2.7"        # moodcoco backend 用；通过 .env 注入
DEFAULT_ROUNDS = 4

MEMORY_FILE = PROJECT_ROOT / "ai-companion" / "MEMORY.md"
TRANSCRIPTS_DIR = PROJECT_ROOT / ".evolve" / "transcripts"
TEST_SCRIPTS_DIR = PROJECT_ROOT / ".evolve" / "test_scripts"
PERSONAS_DIR = PROJECT_ROOT / ".evolve" / "personas"


# ---------------------------------------------------------------------------
# API Key helpers
# ---------------------------------------------------------------------------

def _load_dotenv_if_needed() -> None:
    """Ensure .env values are in os.environ."""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        # Resolve ${VAR} references (e.g. OPENAI_API_KEY=${OPENROUTER_API_KEY})
        if v.startswith("${") and v.endswith("}"):
            v = os.environ.get(v[2:-1], "")
        if k and k not in os.environ:
            os.environ[k] = v


def _openrouter_key() -> str:
    _load_dotenv_if_needed()
    key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    return key


# ---------------------------------------------------------------------------
# User Simulator (Claude Opus via OpenRouter)
# ---------------------------------------------------------------------------

def _build_simulator_prompt(persona_text: str, theme: str, mood: str) -> str:
    return f"""你正在扮演以下角色，跟你的 AI 好友「可可」聊天。

{persona_text}

---

当前状态：
- 你想聊的主题：{theme}
- 你现在的心情：{mood}

演出规则（严格遵守）：
- 你是这个角色本人，不是在"扮演"——你就是她
- 像真实的微信聊天一样说话：口语、不完整的句子、会跑题
- 你会跑题——聊着事突然提到室友、工作、家里的事，这很正常
- 你有情绪——有时候固执、有时候反驳、有时候突然沉默
- 你不会每句话都很理性，有时候会说"我知道不应该这样想但是…"
- 消息长度像微信：通常 1-3 句话，偶尔情绪上来会发一大段
- 如果可可说了什么触动你的话，你会有真实反应（沉默、哭、承认、反驳）
- 你不是来测试 AI 的，你是真的心里难受想找人说说话
- 可可说得对的时候你可以承认，说得不对的时候你会纠正
- 你会用角色的说话风格（语气词、表情、口头禅）

绝对不要做的事：
- 不要说"作为 XX"、"我的角色是"之类打破第四面墙的话
- 不要每句话都回应可可的每个点，有时候你只想说自己的事
- 不要太配合——真人不会每次都顺着对方说
- 不要总结对话、不要做心理分析、不要说"你说得对让我想想"这种太理性的话

只输出你说的话。不要加任何角色名前缀、引号或解释。"""


def _simulate_user(api_key: str, system_prompt: str, history: list) -> str:
    """Call Claude Opus via OpenRouter for a realistic user message."""
    messages = [{"role": "system", "content": system_prompt}]
    for role, content in history:
        # In history: role == "coco" means assistant spoke TO the user; so from
        # the persona LLM's POV, coco's line is the *user-facing* message it
        # should reply to => map to "user" for the persona LLM's input.
        api_role = "user" if role == "coco" else "assistant"
        messages.append({"role": api_role, "content": content})

    payload = json.dumps(
        {
            "model": PERSONA_MODEL,
            "messages": messages,
            "max_tokens": 400,
            "temperature": 0.9,
        },
        ensure_ascii=False,
    )

    result = subprocess.run(
        [
            "curl", "-sS", "-X", "POST",
            f"{OPENROUTER_BASE_URL}/chat/completions",
            "-H", f"Authorization: Bearer {api_key}",
            "-H", "Content-Type: application/json",
            "-H", "HTTP-Referer: https://github.com/jhwleo/moodcoco",
            "-H", "X-Title: moodcoco-evolve",
            "--data-binary", "@-",
        ],
        input=payload,
        capture_output=True, text=True, timeout=90,
    )
    try:
        data = json.loads(result.stdout)
        return data["choices"][0]["message"]["content"].strip()
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        snippet = (result.stdout or result.stderr or "")[:200]
        raise RuntimeError(
            f"Persona simulator failed: {exc}. Response: {snippet!r}"
        ) from exc


# ---------------------------------------------------------------------------
# Coco Communication (moodcoco backend, NOT OpenClaw)
# ---------------------------------------------------------------------------

def _run_turn_sync(user_msg: str, session_id: str) -> dict[str, Any]:
    """Wrap async coordinator.run_turn for synchronous adapter calls."""
    from backend.coordinator import run_turn  # local import after sys.path fix
    return asyncio.run(run_turn(user_msg, session_id=session_id))


def _format_coco_reply(turn_result: dict[str, Any]) -> str:
    """Compose what the persona LLM sees as coco's reply.

    Only fast tool_calls are user-visible. Slow output is internal guidance
    for the next turn's fast agent (NOT a user bubble), so it is NOT appended.
    Non-message UI tool_calls (options/mood slider/safety brake) are annotated
    in square brackets so persona knows an UI event happened.
    """
    chunks: list[str] = []
    for tc in turn_result.get("fast_tool_calls", []):
        name = tc["name"]
        args = tc["args"]
        if name == "ai_message":
            chunks.extend(args.get("messages", []))
        elif name == "ai_options":
            chunks.append(f"[选项卡：{args.get('options')}]")
        elif name == "ai_mood_select":
            chunks.append(f"[弹出心情滑块：{args.get('greeting', '')}]")
        elif name == "ai_praise_popup":
            chunks.append(f"[✦夸夸：{args.get('text', '')}]")
        elif name == "ai_complete_conversation":
            chunks.append(f"[对话小结：{args.get('summary', '')}]")
        elif name == "ai_body_sensation":
            chunks.append(f"[身体感知引导：{args.get('description', '')}]")
        elif name == "ai_safety_brake":
            chunks.append(
                f"[⚠ 安全响应 risk={args.get('risk_level')}: {args.get('response', '')}]"
            )
    return "\n".join(c for c in chunks if c) or "[可可无回复]"


# ---------------------------------------------------------------------------
# Adapter Interface
# ---------------------------------------------------------------------------

def setup(project_dir: str) -> dict:
    """Reset MEMORY.md to clean state; verify keys and imports."""
    errors: list[str] = []

    # OpenRouter key
    api_key = _openrouter_key()
    if not api_key:
        errors.append(
            "OPENROUTER_API_KEY 未配置。从 ~/.openclaw/openclaw.json 的 "
            "agents.defaults.memorySearch.remote.apiKey 复制到 .env。"
        )

    # backend import check
    try:
        from backend.slow import reset_memory_file_for_demo  # noqa: F401
        from backend.coordinator import (  # noqa: F401
            reset_guidance_for_demo,
            run_turn,
        )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"backend import failed: {exc!r}")

    if errors:
        return {"status": "crash", "info": {}, "error": "; ".join(errors)}

    # Reset state so each feature starts clean
    from backend.coordinator import reset_guidance_for_demo
    from backend.slow import reset_memory_file_for_demo
    reset_memory_file_for_demo()
    reset_guidance_for_demo()
    memory_before = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""

    return {
        "status": "ready",
        "info": {
            "api_key_present": True,
            "memory_before": memory_before,
        },
        "error": None,
    }


def run_checks(project_dir: str, feature: str) -> dict:
    """
    Run one scenario as a multi-turn persona-driven conversation.

    Returns:
        {"scores": {}, "details": transcript_markdown}

    Scores is empty because all 5 dimensions are LLM-judged by Codex
    (handled by Evolve V2 C agent, not this adapter).
    """
    test_file = TEST_SCRIPTS_DIR / f"{feature}.json"
    if not test_file.exists():
        return {
            "scores": {},
            "details": f"ERROR: No scenario config for feature={feature!r}. "
                       f"Looked for {test_file}",
        }

    scenario = json.loads(test_file.read_text(encoding="utf-8"))
    persona_name = scenario.get("persona", "")
    theme = scenario.get("theme", "")
    mood = scenario.get("mood", "心情不好")
    rounds = scenario.get("rounds", DEFAULT_ROUNDS)
    expected_skill = scenario.get("skill")  # str (skill name) or None (freechat)

    persona_file = PERSONAS_DIR / f"{persona_name}.md"
    if not persona_file.exists():
        return {
            "scores": {},
            "details": f"ERROR: Persona {persona_name!r} not found at {persona_file}",
        }
    persona_text = persona_file.read_text(encoding="utf-8")

    api_key = _openrouter_key()
    if not api_key:
        return {"scores": {}, "details": "ERROR: OPENROUTER_API_KEY missing"}

    # Reset memory + guidance per feature so we see only THIS scenario's writes
    from backend.coordinator import reset_guidance_for_demo
    from backend.slow import reset_memory_file_for_demo
    reset_memory_file_for_demo()
    reset_guidance_for_demo()
    memory_before = MEMORY_FILE.read_text(encoding="utf-8")

    sim_prompt = _build_simulator_prompt(persona_text, theme, mood)
    session_id = f"evolve-{feature}-{int(time.time())}"
    history: list[tuple[str, str]] = []
    fast_tool_summary: list[str] = []
    slow_trace: list[list[str]] = []
    needs_deep_count = 0
    read_skill_names: list[str] = []

    for i in range(rounds):
        # Step 1: persona speaks
        try:
            user_msg = _simulate_user(api_key, sim_prompt, history)
        except Exception as exc:  # noqa: BLE001
            user_msg = f"[persona simulator crashed turn {i+1}: {exc}]"
        history.append(("user", user_msg))

        # Step 2: coco replies (fast + maybe slow)
        try:
            turn = _run_turn_sync(user_msg, session_id)
        except Exception as exc:  # noqa: BLE001
            turn = {
                "fast_tool_calls": [],
                "fast_reply_text": "",
                "needs_deep": False,
                "supplement_text": f"[coco crashed turn {i+1}: {exc}]",
                "slow_history": [],
            }
        coco_reply = _format_coco_reply(turn)
        history.append(("coco", coco_reply))

        # Collect diagnostic info for transcript footer
        fast_tool_summary.extend(
            f"T{i+1}: {tc['name']}({json.dumps(tc['args'], ensure_ascii=False)[:120]})"
            for tc in turn.get("fast_tool_calls", [])
        )
        slow_trace.append(turn.get("slow_history", []))
        if turn.get("needs_deep"):
            needs_deep_count += 1
        for step in turn.get("slow_history", []):
            if step.startswith("read_skill("):
                name = step[len("read_skill("):].rstrip(")").strip().strip("'\"")
                read_skill_names.append(name)

        time.sleep(1)  # gentle rate limiting

    memory_after = MEMORY_FILE.read_text(encoding="utf-8")
    memory_diff = _unified_diff(memory_before, memory_after)

    # ------------------------------------------------------------------
    # Build transcript
    # ------------------------------------------------------------------
    lines: list[str] = [
        f"# 评估对话：{feature}",
        "",
        f"- **角色**：{persona_name}",
        f"- **场景主题**：{theme}",
        f"- **心情**：{mood}",
        f"- **轮数**：{rounds}",
        f"- **期望触发 skill**：{expected_skill or '（freechat：不应深度触发）'}",
        "",
        "---",
        "",
        "## 对话全文",
        "",
    ]
    for role, content in history:
        speaker = persona_name if role == "user" else "可可"
        lines.append(f"**{speaker}**: {content}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 运行轨迹（供 Critic 参考，非评分依据）")
    lines.append("")
    lines.append(f"- `needs_deep_analysis=True` 命中次数：{needs_deep_count} / {rounds}")
    lines.append(
        f"- 慢思考 `read_skill` 实际加载过：{read_skill_names or '（无）'}"
    )
    if expected_skill:
        hit = expected_skill in read_skill_names
        lines.append(
            f"- 期望 skill `{expected_skill}` 是否真被加载：{'✅ 是' if hit else '❌ 否'}"
        )
    else:
        lines.append(
            f"- 自由对话场景，`needs_deep_analysis` 命中过多（>1/{rounds}）视为过度触发"
        )
    lines.append("")
    lines.append("<details><summary>快思考 tool_calls 明细</summary>")
    lines.append("")
    for line in fast_tool_summary:
        lines.append(f"- {line}")
    lines.append("")
    lines.append("</details>")
    lines.append("")
    lines.append("<details><summary>MEMORY.md diff（慢思考写入）</summary>")
    lines.append("")
    lines.append("```diff")
    lines.append(memory_diff or "(no changes)")
    lines.append("```")
    lines.append("")
    lines.append("</details>")

    transcript_md = "\n".join(lines)

    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    (TRANSCRIPTS_DIR / f"{feature}_latest.md").write_text(
        transcript_md, encoding="utf-8"
    )

    return {"scores": {}, "details": transcript_md}


def teardown(info: dict) -> None:
    """No global cleanup needed — MEMORY.md is reset per feature."""
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unified_diff(before: str, after: str) -> str:
    import difflib
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile="MEMORY.before.md",
        tofile="MEMORY.after.md",
        n=1,
    )
    return "".join(diff)
