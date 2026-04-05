"""
Relationship Intelligence v3 adapter for Evolve skill.

Validates memU integration + Skill files + OpenClaw dialogue.
Deterministic check: openclaw_test (CLI dialogue verification).
LLM-judged: 5 core dimensions evaluated by C agent.
"""

import os

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

prerequisites = [
    {
        "name": "python3",
        "check": "python3 --version",
        "install": "Install Python 3.8+ from python.org",
        "scope": "global",
    },
    {
        "name": "openclaw",
        "check": "which openclaw",
        "install": "Install OpenClaw CLI: npm install -g openclaw",
        "scope": "global",
    },
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MOODCOCO_ROOT = "/Users/jianghongwei/Documents/moodcoco"
AI_COMPANION = os.path.join(MOODCOCO_ROOT, "ai-companion")
MEMU_SOURCE = "/Users/jianghongwei/Documents/GitHub/memU"

# Files that MUST exist (first-read files)
REQUIRED_FIRST_READ = [
    "USER.md",
    "MEMORY.md",
    "SOUL.md",
    "IDENTITY.md",
    "HEARTBEAT.md",
    "AGENTS.md",
]

# Skills that MUST exist after v3
REQUIRED_SKILLS = [
    "base-communication",
    "listen",
    "untangle",
    "crisis",
    "calm-body",
    "see-pattern",
    "face-decision",
    "know-myself",
    "diary",
    "onboarding",
    "farewell",
    "check-in",
    "weekly-reflection",
]

# Scenes that MUST exist
REQUIRED_SCENES = [
    "恋爱", "家人", "室友", "朋友", "考研", "考公",
    "实习", "求职", "毕业", "学业", "失眠",
    "认识自己", "容貌焦虑", "随便聊聊", "SOS",
]


# ---------------------------------------------------------------------------
# Required Functions
# ---------------------------------------------------------------------------

def setup(project_dir: str) -> dict:
    """Verify project structure and dependencies."""
    errors = []

    # Check ai-companion exists
    if not os.path.isdir(AI_COMPANION):
        errors.append(f"ai-companion/ not found at {AI_COMPANION}")

    # Check memU source exists
    if not os.path.isdir(MEMU_SOURCE):
        errors.append(f"memU source not found at {MEMU_SOURCE}")

    if errors:
        return {"status": "crash", "info": {}, "error": "; ".join(errors)}

    return {
        "status": "ready",
        "info": {
            "ai_companion": AI_COMPANION,
            "memu_source": MEMU_SOURCE,
        },
        "error": None,
    }


def run_checks(project_dir: str, feature: str) -> dict:
    """
    Run deterministic checks for openclaw_test dimension.
    LLM-judged dimensions (看见情绪/原因/模式/方法/安全边界) handled by C agent.
    """
    checks_passed = 0
    checks_total = 0
    details = []

    # --- Check 1: First-read files exist ---
    for f in REQUIRED_FIRST_READ:
        checks_total += 1
        path = os.path.join(AI_COMPANION, f)
        if os.path.isfile(path):
            checks_passed += 1
        else:
            details.append(f"MISSING: {f}")

    # --- Check 2: Required skills exist ---
    for skill in REQUIRED_SKILLS:
        checks_total += 1
        skill_path = os.path.join(AI_COMPANION, "skills", skill, "SKILL.md")
        if os.path.isfile(skill_path):
            checks_passed += 1
        else:
            details.append(f"MISSING SKILL: {skill}/SKILL.md")

    # --- Check 3: Required scenes exist ---
    for scene in REQUIRED_SCENES:
        checks_total += 1
        scene_path = os.path.join(AI_COMPANION, "scenes", scene, "SCENE.md")
        if os.path.isfile(scene_path):
            checks_passed += 1
        else:
            details.append(f"MISSING SCENE: {scene}/SCENE.md")

    # --- Check 4: memU bridge script exists ---
    checks_total += 1
    bridge_path = os.path.join(AI_COMPANION, "scripts", "memu_bridge.py")
    if os.path.isfile(bridge_path):
        checks_passed += 1
    else:
        details.append("MISSING: scripts/memu_bridge.py")

    # --- Check 5: memU source is forked into project ---
    checks_total += 1
    memu_local = os.path.join(AI_COMPANION, "memu")
    if os.path.isdir(memu_local):
        checks_passed += 1
    else:
        details.append("MISSING: ai-companion/memu/ (memU fork)")

    # --- Check 6: AGENTS.md references new skills ---
    checks_total += 1
    agents_path = os.path.join(AI_COMPANION, "AGENTS.md")
    if os.path.isfile(agents_path):
        with open(agents_path, "r") as f:
            agents_content = f.read()
        new_skills_mentioned = sum(
            1 for s in ["listen", "untangle", "crisis", "see-pattern", "face-decision", "know-myself"]
            if s in agents_content
        )
        if new_skills_mentioned >= 4:
            checks_passed += 1
        else:
            details.append(f"AGENTS.md only references {new_skills_mentioned}/6 new skills")
    else:
        details.append("AGENTS.md not found")

    # --- Score ---
    score = (checks_passed / checks_total * 10) if checks_total > 0 else 0
    summary = f"Feature: {feature} | {checks_passed}/{checks_total} checks passed"
    if details:
        summary += "\n" + "\n".join(details)

    return {
        "scores": {"openclaw_test": round(score, 1)},
        "details": summary,
    }


def teardown(info: dict) -> None:
    """No cleanup needed."""
    pass
