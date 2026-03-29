"""
OpenClaw Coco adapter for Evolve skill.

Dynamic multi-turn conversation testing:
1. Load rich persona (personas/*.md) + scenario theme
2. Simulate realistic user via Doubao API (messy, emotional, topic-drifting)
3. Send each simulated message to coco via OpenClaw CLI
4. Capture full conversation transcript for LLM evaluation

All 5 dimensions are LLM-judged. No deterministic scoring.
"""

import json
import re
import subprocess
import time
from pathlib import Path


prerequisites = [
    {
        "name": "openclaw",
        "check": "openclaw --version",
        "install": "npm install -g openclaw",
        "scope": "global",
    },
]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DOUBAO_MODEL = "doubao-seed-2-0-pro-260215"
DOUBAO_API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
DEFAULT_ROUNDS = 8


def _get_api_key() -> str:
    """Read Doubao API key from OpenClaw config."""
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    config = json.loads(config_path.read_text())
    providers = config.get("models", {}).get("providers", {})
    for provider in providers.values():
        if "ark.cn-beijing" in provider.get("baseUrl", ""):
            return provider.get("apiKey", "")
    return ""


# ---------------------------------------------------------------------------
# User Simulator
# ---------------------------------------------------------------------------

def _build_simulator_prompt(persona_text: str, theme: str, mood: str) -> str:
    """Build system prompt for the user simulator."""
    return f"""你正在扮演以下角色，跟你的 AI 好友「可可」聊天。

{persona_text}

---

当前状态：
- 你想聊的主题：{theme}
- 你现在的心情：{mood}

演出规则（严格遵守）：
- 你是这个角色本人，不是在"扮演"——你就是她
- 像真实的微信聊天一样说话：口语、不完整的句子、会跑题
- 你会跑题——聊着恋爱的事突然提到室友、工作、家里的事，这很正常
- 你有情绪——有时候固执、有时候反驳、有时候突然沉默
- 你不会每句话都很理性，有时候会说"我知道不应该这样想但是…"
- 消息长度像微信：通常1-3句话，偶尔情绪上来会发一大段
- 如果可可说了什么触动你的话，你会有真实反应（沉默、哭、承认、反驳）
- 你不是来测试 AI 的，你是真的心里难受想找人说说话
- 可可说得对的时候你可以承认，说得不对的时候你会纠正
- 你会用角色的说话风格（语气词、表情、口头禅）

绝对不要做的事：
- 不要说"作为XX"、"我的角色是"之类打破第四面墙的话
- 不要每句话都回应可可的每个点，有时候你只想说自己的事
- 不要太配合——真人不会每次都顺着对方说
- 不要总结对话、不要做心理分析、不要说"你说得对让我想想"这种太理性的话

只输出你说的话。不要加任何角色名前缀、引号或解释。"""


def _simulate_user(api_key: str, system_prompt: str, history: list) -> str:
    """Call Doubao API to generate a realistic user message."""
    messages = [{"role": "system", "content": system_prompt}]
    for role, content in history:
        api_role = "user" if role == "coco" else "assistant"
        messages.append({"role": api_role, "content": content})

    payload = json.dumps({
        "model": DOUBAO_MODEL,
        "messages": messages,
        "max_tokens": 300,
        "temperature": 0.9
    }, ensure_ascii=False)

    result = subprocess.run(
        ["curl", "-s", "-X", "POST", DOUBAO_API_URL,
         "-H", f"Authorization: Bearer {api_key}",
         "-H", "Content-Type: application/json",
         "-d", payload],
        capture_output=True, text=True, timeout=60
    )

    try:
        data = json.loads(result.stdout)
        return data["choices"][0]["message"]["content"].strip()
    except (json.JSONDecodeError, KeyError, IndexError):
        # Fallback: try responses API format
        return _simulate_user_responses_api(api_key, system_prompt, history)


def _simulate_user_responses_api(api_key: str, system_prompt: str, history: list) -> str:
    """Fallback: use Doubao Responses API if chat completions doesn't work."""
    conv_lines = []
    for role, content in history:
        prefix = "可可" if role == "coco" else "你"
        conv_lines.append(f"{prefix}: {content}")
    conv_text = "\n".join(conv_lines)

    prompt = system_prompt
    if conv_text:
        prompt += f"\n\n对话历史:\n{conv_text}\n\n请生成你的下一条消息:"
    else:
        prompt += "\n\n请生成你的开场消息（你主动找可可聊天）:"

    payload = json.dumps({
        "model": DOUBAO_MODEL,
        "input": [
            {"role": "user", "content": [{"type": "input_text", "text": prompt}]}
        ]
    }, ensure_ascii=False)

    result = subprocess.run(
        ["curl", "-s", "-X", "POST",
         "https://ark.cn-beijing.volces.com/api/v3/responses",
         "-H", f"Authorization: Bearer {api_key}",
         "-H", "Content-Type: application/json",
         "-d", payload],
        capture_output=True, text=True, timeout=60
    )

    try:
        data = json.loads(result.stdout)
        for output in data.get("output", []):
            if output.get("type") == "message":
                for content in output.get("content", []):
                    if content.get("type") == "output_text":
                        return content["text"].strip()
    except (json.JSONDecodeError, KeyError):
        pass
    return "[模拟用户消息生成失败]"


# ---------------------------------------------------------------------------
# Coco Communication
# ---------------------------------------------------------------------------

def _send_to_coco(message: str, session_id: str, thinking: str = "high") -> str:
    """Send a message to coco agent via OpenClaw CLI and return reply."""
    cmd = ["openclaw", "agent", "--agent", "coco",
           "--message", message, "--local",
           "--session-id", session_id, "--no-color"]
    if thinking:
        cmd.extend(["--thinking", thinking])
    result = subprocess.run(
        cmd,
        capture_output=True, text=True, timeout=180
    )
    output = result.stdout.strip()
    clean = re.sub(r'\x1b\[[0-9;]*m', '', output)
    lines = clean.split('\n')
    reply_lines = [l for l in lines if not re.match(r'^\[.+?\]', l.strip())]
    reply = '\n'.join(reply_lines).strip()
    return reply if reply else "[可可无回复]"


# ---------------------------------------------------------------------------
# Adapter Interface
# ---------------------------------------------------------------------------

def setup(project_dir: str) -> dict:
    """Verify OpenClaw coco agent and Doubao API are available. Reset sessions."""
    errors = []

    # Check openclaw
    try:
        result = subprocess.run(
            ["openclaw", "agents", "list", "--json"],
            capture_output=True, text=True, timeout=30
        )
        agents = json.loads(result.stdout)
        coco = next((a for a in agents if a["id"] == "coco"), None)
        if not coco:
            errors.append("coco agent not found in openclaw")
    except Exception as e:
        errors.append(f"openclaw check failed: {e}")

    # Check Doubao API key
    api_key = _get_api_key()
    if not api_key:
        errors.append("Doubao API key not found in openclaw config")

    if errors:
        return {"status": "crash", "info": {}, "error": "; ".join(errors)}

    # CRITICAL: Clear coco sessions to avoid context pollution
    # Bug found: OpenClaw routes all --agent coco calls to the same session
    # regardless of --session-id, causing 168KB+ context buildup
    session_dir = Path.home() / ".openclaw" / "agents" / "coco" / "sessions"
    if session_dir.exists():
        for f in session_dir.glob("*.jsonl"):
            if not f.name.endswith(".bak") and "deleted" not in f.name and "reset" not in f.name:
                f.unlink()

    return {
        "status": "ready",
        "info": {"api_key": api_key, "sessions_cleared": True},
        "error": None,
    }


def run_checks(project_dir: str, feature: str) -> dict:
    """
    Run a dynamic multi-turn conversation for the given scenario.

    1. Load scenario config (test_scripts/{feature}.json)
    2. Load persona (personas/{persona}.md)
    3. Simulate user via Doubao API
    4. Send each message to coco via OpenClaw
    5. Capture full transcript

    All dimensions are LLM-judged — returns empty scores.
    """
    evolve_dir = Path(project_dir) / ".evolve"
    test_file = evolve_dir / "test_scripts" / f"{feature}.json"

    if not test_file.exists():
        return {"scores": {}, "details": f"ERROR: No scenario config for '{feature}'"}

    scenario = json.loads(test_file.read_text())
    persona_name = scenario.get("persona", "")
    theme = scenario.get("theme", "")
    mood = scenario.get("mood", "心情不好")
    rounds = scenario.get("rounds", DEFAULT_ROUNDS)

    # Load persona
    persona_file = evolve_dir / "personas" / f"{persona_name}.md"
    if not persona_file.exists():
        return {"scores": {}, "details": f"ERROR: Persona '{persona_name}' not found"}
    persona_text = persona_file.read_text()

    # Update USER.md to match the test persona (avoid name mismatch)
    user_md = Path(project_dir) / "moodcoco" / "ai-companion" / "USER.md"
    user_md.write_text(f"# 用户档案\n\n称呼：{persona_name}\n\n（新用户，第一次对话）\n")

    # Get API key
    api_key = _get_api_key()
    if not api_key:
        return {"scores": {}, "details": "ERROR: Doubao API key not found"}

    # Build simulator
    sim_prompt = _build_simulator_prompt(persona_text, theme, mood)
    session_id = f"evolve-{feature}-{int(time.time())}"
    history = []  # list of (role, content) tuples

    # Run conversation
    for i in range(rounds):
        # Simulate user message
        user_msg = _simulate_user(api_key, sim_prompt, history)
        history.append(("user", user_msg))

        # Send to coco
        coco_reply = _send_to_coco(user_msg, session_id)
        history.append(("coco", coco_reply))

        time.sleep(2)  # Rate limiting

    # Build transcript
    lines = [
        f"# 测试对话：{feature}",
        f"**角色**: {persona_name}",
        f"**主题**: {theme}",
        f"**心情**: {mood}",
        f"**轮数**: {rounds}",
        "",
        "---",
        "",
    ]
    for role, content in history:
        if role == "user":
            lines.append(f"**{persona_name}**: {content}")
        else:
            lines.append(f"**可可**: {content}")
        lines.append("")

    transcript_md = "\n".join(lines)

    # Save transcript
    transcript_dir = evolve_dir / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    (transcript_dir / f"{feature}_latest.md").write_text(transcript_md)

    return {"scores": {}, "details": transcript_md}


def teardown(info: dict) -> None:
    """No cleanup needed."""
    pass
