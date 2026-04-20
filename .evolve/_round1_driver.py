"""
Round driver — sequential adapter.run_checks for N features.
Avoids MEMORY.md race by serializing.  Codex evaluation is dispatched
separately by O after transcripts are ready.

Usage:
    python .evolve/_round1_driver.py <round_n> [feat1 feat2 ...]
    (no args → defaults to round 1 + 5 freechat features below)

Logs to .evolve/run.log per feedback_log_driven memory rule.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".claude/skills/evolve"))

LOG = ROOT / ".evolve/run.log"
RESULTS = ROOT / ".evolve/results.tsv"

DEFAULT_FEATURES = [
    "freechat-hi-greeting",
    "freechat-daily-fatigue",
    "freechat-food-share",
    "freechat-weekend-plan",
    "freechat-weather",
]

# CLI: argv[1] = round_n (default 1); argv[2:] = feature names (default DEFAULT_FEATURES)
ROUND_N = int(sys.argv[1]) if len(sys.argv) > 1 else 1
FEATURES = sys.argv[2:] if len(sys.argv) > 2 else DEFAULT_FEATURES
TRANSCRIPT_NAME = f"transcript_round{ROUND_N}.md"
SUMMARY_NAME = f"round{ROUND_N}_summary.json"


def log(msg: str) -> None:
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [round{ROUND_N}-driver] {msg}\n")


def update_lock_heartbeat() -> None:
    from prepare import update_lock
    try:
        update_lock(".evolve", f"round{ROUND_N}-transcripts", "in-progress")
    except Exception as e:
        log(f"update_lock failed: {e}")


def main() -> int:
    from prepare import load_adapter, append_result
    adapter = load_adapter(".evolve/adapter.py")
    log(f"adapter loaded, round={ROUND_N}, plan={FEATURES}")

    setup = adapter.setup(".")
    log(f"setup status={setup.get('status')} error={setup.get('error')}")
    if setup.get("status") != "ready":
        log("ABORT: setup not ready")
        return 2

    info = setup.get("info", {})
    summary: list[dict] = []

    for i, feat in enumerate(FEATURES, 1):
        update_lock_heartbeat()
        feat_dir = ROOT / f".evolve/{feat}"
        feat_dir.mkdir(parents=True, exist_ok=True)
        log(f"[{i}/{len(FEATURES)}] starting feature={feat}")

        t0 = time.time()
        try:
            result = adapter.run_checks(".", feat)
        except Exception as e:
            elapsed = time.time() - t0
            log(f"  CRASH after {elapsed:.1f}s: {e}\n{traceback.format_exc()}")
            append_result(str(RESULTS), {
                "commit": "round1", "phase": "build", "feature": feat,
                "scores": "-", "total": "0", "status": "crash",
                "summary": f"adapter.run_checks crashed: {str(e)[:100]}",
            })
            summary.append({"feature": feat, "status": "crash", "error": str(e)})
            continue

        elapsed = time.time() - t0
        details = result.get("details", "")
        transcript_path = feat_dir / TRANSCRIPT_NAME
        transcript_path.write_text(details, encoding="utf-8")

        # Quick routing summary from transcript footer for log
        deep_line = next(
            (ln for ln in details.split("\n") if "needs_deep_analysis=True" in ln),
            "(no routing line)",
        )
        skill_line = next(
            (ln for ln in details.split("\n") if "read_skill" in ln and "实际加载" in ln),
            "(no skill line)",
        )

        log(f"  done in {elapsed:.1f}s, transcript={transcript_path.name} ({len(details)} chars)")
        log(f"  routing: {deep_line.strip()}")
        log(f"  skills:  {skill_line.strip()}")

        # Mark as needs_eval (build phase done — transcript ready, awaits codex scoring)
        append_result(str(RESULTS), {
            "commit": f"round{ROUND_N}", "phase": "build", "feature": feat,
            "scores": "-", "total": "-", "status": "keep",
            "summary": f"transcript captured ({len(details)}c, {elapsed:.0f}s)",
        })
        summary.append({
            "feature": feat,
            "status": "ready",
            "transcript": str(transcript_path),
            "elapsed_s": round(elapsed, 1),
        })

    adapter.teardown(info)
    log(f"DONE. summary={json.dumps(summary, ensure_ascii=False)}")

    # Write summary for O to read next round
    summary_path = ROOT / f".evolve/{SUMMARY_NAME}"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"summary -> {summary_path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"DRIVER CRASH: {e}\n{traceback.format_exc()}")
        sys.exit(1)
