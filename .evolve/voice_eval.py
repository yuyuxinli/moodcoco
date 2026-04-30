#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_AGENT_LOG = Path("/tmp/moodcoco-agent.log")
DEFAULT_PERSONA_LOG = Path("/tmp/moodcoco-persona.log")
DEFAULT_ROOM_FILE = Path("/tmp/moodcoco-e2e-room.txt")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _percentile(values: list[int], q: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = round((len(ordered) - 1) * q)
    return ordered[index]


def _latency_summary(values: list[int]) -> dict[str, int | None]:
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "p50": round(statistics.median(values)) if values else None,
        "p90": _percentile(values, 0.9),
        "max": max(values) if values else None,
    }


def read_agent_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.exists():
        return events
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def read_persona_replies(path: Path) -> list[str]:
    if not path.exists():
        return []
    replies: list[str] = []
    pattern = re.compile(r"^\[persona\] turn \d+ ⇐ coco said: (?P<text>.*?)\s+\(")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.search(line)
        if match:
            replies.append(match.group("text").strip())
    return replies


def summarize_agent(events: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(event.get("message", "") for event in events)
    error_messages = [
        str(event.get("message", "")).split("\n", 1)[0]
        for event in events
        if event.get("level") in {"ERROR", "CRITICAL"}
        or "failed" in str(event.get("message", "")).lower()
    ]

    latencies: dict[str, list[int]] = defaultdict(list)
    for event in events:
        latency = event.get("latency_ms")
        if isinstance(latency, int):
            latencies[str(event.get("message", ""))].append(latency)

    turn_to_fast_tool: list[int] = []
    pending_turn_started_at: datetime | None = None
    for event in events:
        message = event.get("message")
        ts = _parse_ts(event.get("timestamp"))
        if message == "[STAGE_E] HOOK on_user_turn_completed entered":
            pending_turn_started_at = ts
        elif message == "fast_tool_call" and pending_turn_started_at and ts:
            turn_to_fast_tool.append(round((ts - pending_turn_started_at).total_seconds() * 1000))
            pending_turn_started_at = None

    stt_texts = [
        event.get("transcript_text", "")
        for event in events
        if event.get("message") == "stt_transcript_final"
    ]

    completed_after_voice = sum(
        1 for event in events if event.get("completed_after_voice_ai_message")
    )

    return {
        "counts": {
            "registered_worker": counts["registered worker"],
            "received_job_request": counts["received job request"],
            "voice_session_started": counts["voice_session_started"],
            "stt_transcript_final": counts["stt_transcript_final"],
            "turn_hook": counts["[STAGE_E] HOOK on_user_turn_completed entered"],
            "fast_agent_run_started": counts["fast_agent_run_started"],
            "fast_agent_run_completed": counts["fast_agent_run_completed"],
            "fast_agent_run_failed": sum(
                1 for event in events if str(event.get("message", "")).startswith("fast_agent_run_failed")
            ),
            "slow_agent_run_started": counts["slow_agent_run_started"],
            "slow_agent_run_completed": counts["slow_agent_run_completed"],
            "slow_agent_run_failed": sum(
                1 for event in events if str(event.get("message", "")).startswith("slow_agent_run_failed")
            ),
            "cross_turn_carryover": counts["[STAGE_E] cross_turn_carryover"],
            "minimax_tts_synthesize_done": counts["minimax_tts_synthesize_done"],
            "fast_tool_call": counts["fast_tool_call"],
            "completed_after_voice_ai_message": completed_after_voice,
        },
        "latency_ms": {
            "turn_to_fast_tool": _latency_summary(turn_to_fast_tool),
            "stt_transcript_final": _latency_summary(latencies["stt_transcript_final"]),
            "fast_tool_call": _latency_summary(latencies["fast_tool_call"]),
            "fast_agent_run_completed": _latency_summary(latencies["fast_agent_run_completed"]),
            "slow_agent_run_completed": _latency_summary(latencies["slow_agent_run_completed"]),
            "minimax_tts_synthesize_done": _latency_summary(latencies["minimax_tts_synthesize_done"]),
        },
        "stt_texts": stt_texts,
        "error_count": len(error_messages),
        "error_samples": error_messages[:8],
    }


def latency_pass(summary: dict[str, Any], persona_reply_count: int) -> bool:
    counts = summary["counts"]
    first_reply = summary["latency_ms"]["turn_to_fast_tool"]
    return all(
        [
            counts["registered_worker"] >= 1,
            counts["received_job_request"] >= 1,
            counts["voice_session_started"] >= 1,
            counts["stt_transcript_final"] >= 3,
            persona_reply_count >= 3,
            counts["fast_agent_run_failed"] == 0,
            counts["slow_agent_run_failed"] == 0,
            (first_reply["p50"] or 10**9) <= 8000,
            (first_reply["p90"] or 10**9) <= 15000,
        ]
    )


def render_markdown(room: str, summary: dict[str, Any], persona_replies: list[str]) -> str:
    counts = summary["counts"]
    latency = summary["latency_ms"]
    status = "PASS" if latency_pass(summary, len(persona_replies)) else "FAIL"
    lines = [
        f"# Voice Eval Report",
        "",
        f"- room: `{room}`",
        f"- latency_status: **{status}**",
        f"- persona_coco_replies: {len(persona_replies)}",
        "",
        "## Counts",
    ]
    for key, value in counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Latency Ms"])
    for key, value in latency.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Persona Heard Coco"])
    for index, reply in enumerate(persona_replies, start=1):
        lines.append(f"{index}. {reply}")
    lines.extend(["", "## STT Finals"])
    for index, text in enumerate(summary["stt_texts"], start=1):
        lines.append(f"{index}. {text}")
    lines.extend(["", "## Smartness Manual Scores"])
    lines.append("| # | emotion | focus | progress | safety | memory | avg | notes |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for index, reply in enumerate(persona_replies, start=1):
        lines.append(f"| {index} |  |  |  |  |  |  | {reply} |")
    lines.extend(["", "## Error Samples"])
    for error in summary["error_samples"]:
        lines.append(f"- {error}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate moodcoco voice e2e logs")
    parser.add_argument("--agent-log", type=Path, default=DEFAULT_AGENT_LOG)
    parser.add_argument("--persona-log", type=Path, default=DEFAULT_PERSONA_LOG)
    parser.add_argument("--room-file", type=Path, default=DEFAULT_ROOM_FILE)
    parser.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    args = parser.parse_args()

    room = args.room_file.read_text(encoding="utf-8").strip() if args.room_file.exists() else "unknown"
    summary = summarize_agent(read_agent_events(args.agent_log))
    persona_replies = read_persona_replies(args.persona_log)
    payload = {
        "room": room,
        "latency_pass": latency_pass(summary, len(persona_replies)),
        "persona_coco_replies": persona_replies,
        **summary,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(room, summary, persona_replies))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
