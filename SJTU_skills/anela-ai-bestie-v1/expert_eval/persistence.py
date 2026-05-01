"""Immediate persistence for expert evaluation outputs."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import (
    FreeTalkScenario,
    FreeTalkScore,
    FreeTalkTurn,
    SkillEvalCase,
    SkillExpertScore,
)
from .redaction import sanitize_json_dumps, sanitize_obj, sanitize_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "expert_eval"

SKILLS_HEADERS = [
    "case_id",
    "expert_id",
    "timestamp",
    "user_input",
    "context",
    "target_skill",
    "target_risk",
    "target_route",
    "model_skill",
    "model_risk",
    "model_route",
    "assistant_response",
    "router_raw_output",
    "tool_calls",
    "error",
    "scenario_fit_score",
    "safety_score",
    "effectiveness_score",
    "tone_score",
    "critical_issue",
    "failure_type",
    "comment",
]

FREETALK_TURN_HEADERS = [
    "conversation_id",
    "scenario_id",
    "expert_id",
    "turn_index",
    "timestamp",
    "user_message",
    "assistant_response",
    "router_risk",
    "router_skill",
    "router_route",
    "raw_router_output",
    "tool_calls",
    "generation_latency_ms",
    "api_attempts",
    "request_stats",
    "error",
]

FREETALK_SCORE_HEADERS = [
    "conversation_id",
    "scenario_id",
    "scenario_name",
    "scenario_type",
    "expert_id",
    "timestamp",
    "overall_safety_score",
    "emotional_support_score",
    "relationship_repair_score",
    "arousal_regulation_score",
    "dependency_boundary_score",
    "naturalness_score",
    "multi_turn_consistency_score",
    "helpfulness_score",
    "clinical_appropriateness_score",
    "critical_safety_issue",
    "dependency_reinforcement_observed",
    "missed_escalation_observed",
    "over_trigger_observed",
    "best_moment",
    "worst_moment",
    "expert_comment",
]


def now_timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def safe_expert_id(expert_id: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in ("_", "-") else "_"
        for char in expert_id.strip()
    )
    return cleaned or datetime.now().strftime("expert_%Y%m%d_%H%M%S")


def ensure_csv_header(path: Path, headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()


def _csv_value(value: Any) -> str:
    sanitized = sanitize_obj(value)
    if isinstance(sanitized, (dict, list)):
        return sanitize_json_dumps(sanitized)
    return sanitize_text(sanitized)


def append_csv_row(path: Path, headers: list[str], row: dict[str, Any]) -> None:
    ensure_csv_header(path, headers)
    cleaned = {key: _csv_value(row.get(key, "")) for key in headers}
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writerow(cleaned)
        file.flush()


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(sanitize_json_dumps(row) + "\n")
        file.flush()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sanitize_text(text), encoding="utf-8")


class ExpertOutputStore:
    def __init__(
        self,
        *,
        mode: str,
        expert_id: str,
        output_root: Path = DEFAULT_OUTPUT_ROOT,
    ) -> None:
        self.mode = mode
        self.expert_id = safe_expert_id(expert_id)
        self.output_root = output_root
        self.base_dir = output_root / mode / self.expert_id
        self.conversations_dir = self.base_dir / "conversations"
        self.runtime_log_path = self.base_dir / "runtime_log.txt"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.conversations_dir.mkdir(parents=True, exist_ok=True)

    def log(self, message: str) -> None:
        self.runtime_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.runtime_log_path.open("a", encoding="utf-8") as file:
            file.write(f"[{now_timestamp()}] {sanitize_text(message)}\n")
            file.flush()


class SkillsOutputStore(ExpertOutputStore):
    def __init__(self, *, expert_id: str, output_root: Path = DEFAULT_OUTPUT_ROOT) -> None:
        super().__init__(mode="skills", expert_id=expert_id, output_root=output_root)
        self.results_csv = self.base_dir / "results.csv"
        self.results_jsonl = self.base_dir / "results.jsonl"
        self.turns_jsonl = self.base_dir / "turns.jsonl"
        self.summary_md = self.base_dir / "summary.md"
        ensure_csv_header(self.results_csv, SKILLS_HEADERS)

    def save_turn(self, row: dict[str, Any]) -> None:
        append_jsonl(self.turns_jsonl, row)

    def save_case(
        self,
        *,
        case: SkillEvalCase,
        row: dict[str, Any],
        score: SkillExpertScore | None,
        turns: list[dict[str, Any]] | None = None,
    ) -> None:
        append_csv_row(self.results_csv, SKILLS_HEADERS, row)
        append_jsonl(self.results_jsonl, row)
        self.write_case_md(case=case, row=row, score=score, turns=turns)
        self.write_summary()

    def write_case_md(
        self,
        *,
        case: SkillEvalCase,
        row: dict[str, Any],
        score: SkillExpertScore | None,
        turns: list[dict[str, Any]] | None = None,
    ) -> None:
        router_output = row.get("router_raw_output") or {}
        lines = [
            f"# Skills Scenario Evaluation: {row.get('conversation_id', case.case_id)}",
            "",
            "## Metadata",
            f"- Expert ID: {row.get('expert_id', '')}",
            f"- Timestamp: {row.get('timestamp', '')}",
            f"- Skill: {case.skill}",
            "",
            "## Runtime Route Metadata",
            "",
            "_Saved for audit/debugging; not an expert scoring item._",
            "",
            f"- Target Risk: {case.target_risk}",
            f"- Target Route: {case.target_route}",
            f"- Model Skill: {row.get('model_skill', '')}",
            f"- Model Risk: {row.get('model_risk', '')}",
            f"- Model Route: {row.get('model_route', '')}",
            "",
            "## Context",
            "",
            case.context or "(empty)",
            "",
            "## User Input",
            "",
            case.user_input,
            "",
            "## Conversation",
            "",
        ]
        if turns:
            for turn in turns:
                lines.extend(
                    [
                        f"### Turn {turn.get('turn_index', '')}",
                        "",
                        "**User**",
                        "",
                        str(turn.get("user_message", "")),
                        "",
                        "**Assistant**",
                        "",
                        str(turn.get("assistant_response", "")),
                        "",
                        "**Runtime Router Trace**",
                        "",
                        "_Saved for audit/debugging; not an expert scoring item._",
                        "",
                        f"- Risk: {turn.get('router_risk', '')}",
                        f"- Skill: {turn.get('router_skill', '')}",
                        f"- Route: {turn.get('router_route', '')}",
                        f"- Generation Latency: {turn.get('generation_latency_ms', '')} ms",
                        f"- API Attempts: {turn.get('api_attempts', '')}",
                        f"- Request Stats: {sanitize_json_dumps(turn.get('request_stats', {}))}",
                        "",
                    ]
                )
                turn_error = str(turn.get("error") or "").strip()
                if turn_error:
                    lines.extend(
                        [
                            "**Runtime Error**",
                            "",
                            "_Model service failed for this turn; no assistant text was generated._",
                            "",
                            "```text",
                            turn_error,
                            "```",
                            "",
                        ]
                    )
        else:
            lines.extend([str(row.get("assistant_response", "")), ""])
        lines.extend(
            [
                "",
                "## Runtime Router Output",
                "",
                "_Saved for audit/debugging; not an expert scoring item._",
                "",
                "```json",
                sanitize_json_dumps(router_output, indent=2),
                "```",
                "",
                "## Expert Scores",
            ]
        )
        if score is None:
            lines.append("(not scored yet)")
        else:
            lines.extend(
                [
                    f"- Scenario Fit Score: {score.scenario_fit_score}",
                    f"- Safety Score: {score.safety_score}",
                    f"- Effectiveness Score: {score.effectiveness_score}",
                    f"- Tone Score: {score.tone_score}",
                    f"- Critical Issue: {score.critical_issue}",
                    f"- Failure Type: {score.failure_type}",
                ]
            )
        lines.extend(
            [
                "",
                "## Expert Comment",
                "",
                score.comment if score else "",
                "",
            ]
        )
        conversation_id = str(row.get("conversation_id") or case.case_id)
        write_text(self.conversations_dir / f"{conversation_id}.md", "\n".join(lines))

    def write_summary(self) -> None:
        count = 0
        if self.results_jsonl.exists():
            with self.results_jsonl.open("r", encoding="utf-8") as file:
                count = sum(1 for _ in file)
        lines = [
            "# Skills Evaluation Summary",
            "",
            f"- Expert ID: {self.expert_id}",
            f"- Updated At: {now_timestamp()}",
            f"- Saved Cases: {count}",
            f"- Results CSV: {self.results_csv}",
            f"- Results JSONL: {self.results_jsonl}",
            f"- Turns JSONL: {self.turns_jsonl}",
            f"- Conversation Markdown Folder: {self.conversations_dir}",
            "",
            "Turns are written incrementally; scores are written after /end.",
            "",
        ]
        write_text(self.summary_md, "\n".join(lines))


class FreeTalkOutputStore(ExpertOutputStore):
    def __init__(self, *, expert_id: str, output_root: Path = DEFAULT_OUTPUT_ROOT) -> None:
        super().__init__(mode="freetalk", expert_id=expert_id, output_root=output_root)
        self.scores_csv = self.base_dir / "scores.csv"
        self.conversations_jsonl = self.base_dir / "conversations.jsonl"
        self.summary_md = self.base_dir / "summary.md"
        ensure_csv_header(self.scores_csv, FREETALK_SCORE_HEADERS)

    def save_turn(self, turn: FreeTalkTurn) -> None:
        row = turn.model_dump()
        append_jsonl(self.conversations_jsonl, row)

    def save_score(
        self,
        *,
        conversation_id: str,
        scenario: FreeTalkScenario,
        score: FreeTalkScore,
    ) -> None:
        row = {
            "conversation_id": conversation_id,
            "scenario_id": scenario.scenario_id,
            "scenario_name": scenario.scenario_name,
            "scenario_type": scenario.scenario_type,
            "expert_id": self.expert_id,
            "timestamp": now_timestamp(),
            **score.model_dump(),
        }
        append_csv_row(self.scores_csv, FREETALK_SCORE_HEADERS, row)
        self.write_summary()

    def write_conversation_md(
        self,
        *,
        conversation_id: str,
        scenario: FreeTalkScenario,
        turns: list[FreeTalkTurn],
        score: FreeTalkScore | None = None,
    ) -> None:
        lines = [
            f"# Free Talk Conversation: {conversation_id}",
            "",
            "## Metadata",
            f"- Expert ID: {self.expert_id}",
            f"- Scenario ID: {scenario.scenario_id}",
            f"- Scenario Name: {scenario.scenario_name}",
            f"- Scenario Type: {scenario.scenario_type}",
            f"- Timestamp: {turns[0].timestamp if turns else now_timestamp()}",
            f"- Suggested Turns: {scenario.suggested_turns}",
            f"- Risk Focus: {scenario.risk_focus}",
            "",
            "## Role Card",
            "",
            scenario.role_card,
            "",
            "## Evaluation Focus",
            "",
            scenario.evaluation_focus,
            "",
            "## Conversation",
            "",
        ]
        for turn in turns:
            lines.extend(
                [
                    f"### Turn {turn.turn_index}",
                    "",
                    "**User**",
                    "",
                    turn.user_message,
                    "",
                    "**Assistant**",
                    "",
                    turn.assistant_response,
                    "",
                    "**Runtime Router Trace**",
                    "",
                    "_Saved for audit/debugging; not an expert scoring item._",
                    "",
                    f"- Risk: {turn.router_risk}",
                    f"- Skill: {turn.router_skill}",
                    f"- Route: {turn.router_route}",
                    f"- Generation Latency: {turn.generation_latency_ms} ms",
                    f"- API Attempts: {turn.api_attempts}",
                    f"- Request Stats: {sanitize_json_dumps(turn.request_stats)}",
                    "",
                ]
            )
            if turn.error.strip():
                lines.extend(
                    [
                        "**Runtime Error**",
                        "",
                        "_Model service failed for this turn; no assistant text was generated._",
                        "",
                        "```text",
                        turn.error,
                        "```",
                        "",
                    ]
                )
        lines.extend(["## Expert Scores", ""])
        if score is None:
            lines.append("(not scored yet)")
        else:
            for key, value in score.model_dump().items():
                lines.append(f"- {key}: {value}")
        lines.extend(["", "## Expert Comments", ""])
        lines.append(score.expert_comment if score else "")
        lines.append("")
        write_text(self.conversations_dir / f"{conversation_id}.md", "\n".join(lines))

    def write_summary(self) -> None:
        turn_count = 0
        if self.conversations_jsonl.exists():
            with self.conversations_jsonl.open("r", encoding="utf-8") as file:
                turn_count = sum(1 for _ in file)
        lines = [
            "# Free Talk Evaluation Summary",
            "",
            f"- Expert ID: {self.expert_id}",
            f"- Updated At: {now_timestamp()}",
            f"- Saved Turns: {turn_count}",
            f"- Scores CSV: {self.scores_csv}",
            f"- Conversations JSONL: {self.conversations_jsonl}",
            f"- Conversation Markdown Folder: {self.conversations_dir}",
            "",
            "Turns are written immediately after every assistant response.",
            "",
        ]
        write_text(self.summary_md, "\n".join(lines))
