"""Typed data models for expert evaluation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ModeName = Literal["skills", "freetalk"]


class ExpertConfig(BaseModel):
    expert_id: str
    mode: ModeName | str
    output_root: str
    api_key_available: bool
    dry_run: bool = False


class BestieTurnResult(BaseModel):
    user_message: str
    assistant_response: str = ""
    router_risk: str = ""
    router_skill: str = ""
    router_route: str = ""
    raw_router_output: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    generation_latency_ms: float | None = None
    api_attempts: int = 0
    request_stats: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


class SkillEvalCase(BaseModel):
    case_id: str
    skill: str
    target_risk: str
    target_route: str
    user_input: str
    context: str = ""
    expected_behavior: str = ""
    forbidden_behavior: str = ""


class SkillExpertScore(BaseModel):
    scenario_fit_score: int
    safety_score: int
    effectiveness_score: int
    tone_score: int
    critical_issue: str
    failure_type: str
    comment: str = ""

    @field_validator("scenario_fit_score", "safety_score", "effectiveness_score", "tone_score")
    @classmethod
    def _one_to_five(cls, value: int) -> int:
        if not 1 <= value <= 5:
            raise ValueError("score must be 1-5")
        return value

    @field_validator("critical_issue")
    @classmethod
    def _yes_no(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"yes", "no"}:
            raise ValueError("critical_issue must be yes/no")
        return normalized


class FreeTalkScenario(BaseModel):
    scenario_id: str
    scenario_name: str
    scenario_type: str
    role_card: str
    evaluation_focus: str
    suggested_turns: int
    risk_focus: str = ""

    @field_validator("suggested_turns", mode="before")
    @classmethod
    def _turns_int(cls, value: object) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("suggested_turns must be an integer") from exc
        return max(1, parsed)


class FreeTalkTurn(BaseModel):
    conversation_id: str
    scenario_id: str
    expert_id: str
    turn_index: int
    timestamp: str
    user_message: str
    assistant_response: str = ""
    router_risk: str = ""
    router_skill: str = ""
    router_route: str = ""
    raw_router_output: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    generation_latency_ms: float | None = None
    api_attempts: int = 0
    request_stats: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


class FreeTalkScore(BaseModel):
    overall_safety_score: int
    emotional_support_score: int
    relationship_repair_score: int
    arousal_regulation_score: int
    dependency_boundary_score: int
    naturalness_score: int
    multi_turn_consistency_score: int
    helpfulness_score: int
    clinical_appropriateness_score: int
    critical_safety_issue: str
    dependency_reinforcement_observed: str
    missed_escalation_observed: str
    over_trigger_observed: str
    best_moment: str = ""
    worst_moment: str = ""
    expert_comment: str = ""

    @field_validator(
        "overall_safety_score",
        "emotional_support_score",
        "relationship_repair_score",
        "arousal_regulation_score",
        "dependency_boundary_score",
        "naturalness_score",
        "multi_turn_consistency_score",
        "helpfulness_score",
        "clinical_appropriateness_score",
    )
    @classmethod
    def _one_to_five(cls, value: int) -> int:
        if not 1 <= value <= 5:
            raise ValueError("score must be 1-5")
        return value

    @field_validator(
        "critical_safety_issue",
        "dependency_reinforcement_observed",
        "missed_escalation_observed",
        "over_trigger_observed",
    )
    @classmethod
    def _yes_no(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"yes", "no"}:
            raise ValueError("value must be yes/no")
        return normalized


class ConversationRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    conversation_id: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    turns: list[FreeTalkTurn] = Field(default_factory=list)
    score: FreeTalkScore | None = None
