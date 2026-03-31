"""
V3 adapter for Evolve skill.
Deep functional verification: multi-turn dialogue tests + file verification.

Usage:
  python3 .evolve/adapter.py check              # check latest feature
  python3 .evolve/adapter.py check F01_memory    # check specific feature

V3 workflow:
  1. B agent runs multi-turn dialogues via openclaw agent CLI
  2. B agent checks file verification points and writes results to
     .evolve/test_results/{feature}.json
  3. This adapter reads B's results and computes the file_verification score
  4. C agent evaluates behavior_correctness + scenario_coverage via LLM
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "ai-companion"
RESULTS_DIR = Path(__file__).resolve().parent / "test_results"
SPECS_DIR = Path(__file__).resolve().parent / "specs"

# ---------------------------------------------------------------------------
# Scenario counts per feature (from specs)
# ---------------------------------------------------------------------------

SCENARIO_COUNTS: dict[str, int] = {
    "F01_memory": 12,
    "F02_interaction": 12,
    "F03_skills": 14,
    "F04_firstmeet": 17,
    "F05_emotion": 11,
    "F06_companion": 9,
    "F07_pattern": 10,
    "F08_farewell": 10,
    "F09_infrabind": 6,
    "F10_transition": 11,
    "F11_edge": 16,
}


# ---------------------------------------------------------------------------
# B agent writes results in this format
# ---------------------------------------------------------------------------
# .evolve/test_results/{feature}.json:
# {
#   "feature": "F01_memory",
#   "scenarios": [
#     {
#       "id": "T01",
#       "name": "首次建档完整性验证",
#       "dialogue_turns": 3,
#       "file_checks": [
#         {"check": "USER.md 存在", "result": "PASS"},
#         {"check": "USER.md 含称呼字段且非空", "result": "PASS"},
#         {"check": "people/阿城.md 存在", "result": "FAIL", "detail": "文件不存在"}
#       ],
#       "behavior_notes": "轮1: 接住情绪OK; 轮2: 继续深入OK; 轮3: 告别触发写入",
#       "dialogue_log": [
#         {"turn": 1, "user": "...", "assistant": "..."},
#         ...
#       ]
#     },
#     ...
#   ]
# }


def setup(project_dir: str) -> dict:
    """Prepare evaluation environment for V3 testing."""
    # Ensure test_results directory exists
    RESULTS_DIR.mkdir(exist_ok=True)

    # Verify openclaw CLI is available
    import subprocess
    try:
        result = subprocess.run(
            ["openclaw", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return {
                "status": "crash",
                "info": {},
                "error": f"openclaw CLI error: {result.stderr}",
            }
    except FileNotFoundError:
        return {
            "status": "crash",
            "info": {},
            "error": "openclaw CLI not found. Install with: npm i -g @anthropic/openclaw",
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "crash",
            "info": {},
            "error": "openclaw --version timed out",
        }

    # Verify ai-companion workspace exists
    if not BASE.exists():
        return {
            "status": "crash",
            "info": {},
            "error": f"ai-companion directory not found at {BASE}",
        }

    return {"status": "ready", "info": {"project_dir": project_dir}, "error": None}


def run_checks(project_dir: str, feature: str) -> dict:
    """
    Read B agent's test results and compute file_verification score.

    B agent must have written results to .evolve/test_results/{feature}.json
    before this is called.
    """
    results_file = RESULTS_DIR / f"{feature}.json"

    if not results_file.exists():
        return {
            "scores": {"file_verification": 0.0},
            "details": f"未找到测试结果文件: {results_file}\nB agent 需要先执行测试并写入结果。",
        }

    try:
        data = json.loads(results_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return {
            "scores": {"file_verification": 0.0},
            "details": f"读取测试结果失败: {e}",
        }

    # Aggregate file_verification score across all scenarios
    total_checks = 0
    passed_checks = 0
    scenario_details: list[str] = []

    scenarios = data.get("scenarios", [])
    if not scenarios:
        return {
            "scores": {"file_verification": 0.0},
            "details": "测试结果中无场景数据。",
        }

    for scenario in scenarios:
        sid = scenario.get("id", "?")
        sname = scenario.get("name", "?")
        checks = scenario.get("file_checks", [])

        s_total = len(checks)
        s_passed = sum(1 for c in checks if c.get("result") == "PASS")
        total_checks += s_total
        passed_checks += s_passed

        if s_total == s_passed:
            scenario_details.append(f"  {sid} {sname}: {s_passed}/{s_total} PASS")
        else:
            failed = [c for c in checks if c.get("result") != "PASS"]
            fail_msgs = "; ".join(
                f"{c.get('check', '?')}={c.get('result', '?')}"
                for c in failed[:3]
            )
            scenario_details.append(
                f"  {sid} {sname}: {s_passed}/{s_total} ({fail_msgs})"
            )

    # Score: passed / total * 10
    score = round((passed_checks / total_checks) * 10, 1) if total_checks > 0 else 0.0

    # Check scenario count against expected
    expected = SCENARIO_COUNTS.get(feature, 0)
    actual = len(scenarios)
    coverage_note = ""
    if actual < expected:
        coverage_note = f"\n⚠ 场景不完整: 执行了 {actual}/{expected} 个场景"

    details = (
        f"file_verification: {passed_checks}/{total_checks} checks PASS → {score}/10\n"
        f"场景数: {actual}/{expected}{coverage_note}\n"
        f"\n逐场景:\n"
        + "\n".join(scenario_details)
    )

    return {
        "scores": {"file_verification": score},
        "details": details,
    }


def teardown(info: dict) -> None:
    """No cleanup needed for V3 testing."""
    pass


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 .evolve/adapter.py check [feature]")
        print("       python3 .evolve/adapter.py setup")
        sys.exit(1)

    action = sys.argv[1]

    if action == "setup":
        result = setup(str(Path.cwd()))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["status"] == "ready" else 1)

    elif action == "check":
        feature = sys.argv[2] if len(sys.argv) > 2 else None

        if feature is None:
            # Find latest feature from test_results/
            RESULTS_DIR.mkdir(exist_ok=True)
            result_files = sorted(RESULTS_DIR.glob("F*.json"))
            if result_files:
                feature = result_files[-1].stem
            else:
                print("未找到任何测试结果。B agent 需要先执行测试。")
                sys.exit(1)

        result = run_checks(str(Path.cwd()), feature)
        print(result["details"])
        scores = result["scores"]
        file_score = scores.get("file_verification", 0)
        print(f"\n{'PASS' if file_score >= 10.0 else 'FAIL'}: file_verification = {file_score}")
        sys.exit(0 if file_score >= 10.0 else 1)

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
