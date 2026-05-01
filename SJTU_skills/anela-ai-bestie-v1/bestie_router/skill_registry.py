"""Canonical skill registry and alias resolution."""

from __future__ import annotations

from typing import TypedDict

from .constants import CANONICAL_SKILLS, CONTEXTUAL_ALIASES, SKILL_ALIASES
from .types import SkillName


class SkillMetadata(TypedDict):
    name: SkillName
    layer: str
    description: str
    lifecycleExit: str


SKILL_REGISTRY: dict[SkillName, SkillMetadata] = {
    "ambient-presence": {
        "name": "ambient-presence",
        "layer": "companionship",
        "description": "Low-pressure everyday presence and light connection.",
        "lifecycleExit": "User offers an event, emotion, task, risk, or deeper need.",
    },
    "active-celebration": {
        "name": "active-celebration",
        "layer": "companionship",
        "description": "Specific celebration of good news, effort, and milestones.",
        "lifecycleExit": "Joy is received; user asks to save, plan, or process doubt.",
    },
    "playful-attunement": {
        "name": "playful-attunement",
        "layer": "companionship",
        "description": "Banter, memes, captions, playful co-creation, and light ranting.",
        "lifecycleExit": "Play covers pain, danger, cruelty, or a practical request.",
    },
    "relationship-memory": {
        "name": "relationship-memory",
        "layer": "companionship",
        "description": "Visible, authorized memory read/write/update/delete routing.",
        "lifecycleExit": "Memory scope is confirmed, declined, updated, or deleted.",
    },
    "ritual-checkin": {
        "name": "ritual-checkin",
        "layer": "companionship",
        "description": "Light authorized check-ins around user-approved rituals.",
        "lifecycleExit": "Check-in is received or a stronger user need appears.",
    },
    "responsive-listening": {
        "name": "responsive-listening",
        "layer": "emotion-regulation",
        "description": "Specific validation and low-judgment emotional holding.",
        "lifecycleExit": "User feels heard or asks for labeling, clarity, or action.",
    },
    "emotion-labeling": {
        "name": "emotion-labeling",
        "layer": "emotion-regulation",
        "description": "Tentative naming of mixed, unclear, or shame-heavy emotions.",
        "lifecycleExit": "User accepts, corrects, or refines the label.",
    },
    "vent-container": {
        "name": "vent-container",
        "layer": "emotion-regulation",
        "description": "Contained venting without cruelty, revenge, or co-rumination.",
        "lifecycleExit": "Venting loops, escalates, or user wants clarity/action.",
    },
    "ground-and-regulate": {
        "name": "ground-and-regulate",
        "layer": "emotion-regulation",
        "description": "Short body-based down-regulation for high arousal or impulse waves.",
        "lifecycleExit": "User can stay with one short exchange or safety risk appears.",
    },
    "reality-soft-check": {
        "name": "reality-soft-check",
        "layer": "emotion-regulation",
        "description": "Gentle separation of facts, feelings, guesses, and confirmable data.",
        "lifecycleExit": "Facts and guesses are separated enough for a small next step.",
    },
    "rupture-repair": {
        "name": "rupture-repair",
        "layer": "emotion-regulation",
        "description": "Repair when the user says the AI missed, hurt, forgot, or overanalyzed.",
        "lifecycleExit": "User confirms adjusted direction or a higher safety signal appears.",
    },
    "collaborative-untangling": {
        "name": "collaborative-untangling",
        "layer": "growth",
        "description": "Jointly structure a messy issue into event, feeling, need, and step.",
        "lifecycleExit": "The issue is clear enough for action, rest, or deeper pattern work.",
    },
    "agency-next-step": {
        "name": "agency-next-step",
        "layer": "growth",
        "description": "Autonomy-preserving options, tradeoffs, and a small reversible next step.",
        "lifecycleExit": "One small step is chosen or arousal/dependency rises.",
    },
    "identity-mirror": {
        "name": "identity-mirror",
        "layer": "growth",
        "description": "Low-label self-concept, value, and identity reflection.",
        "lifecycleExit": "User finds a useful hypothesis or wants action/grounding.",
    },
    "pattern-witness": {
        "name": "pattern-witness",
        "layer": "growth",
        "description": "Longitudinal repeated-pattern noticing with memory boundaries.",
        "lifecycleExit": "Pattern is named lightly and user chooses a small experiment.",
    },
    "social-bridge": {
        "name": "social-bridge",
        "layer": "growth",
        "description": "Bridge AI support toward real relationships and user-authored expression.",
        "lifecycleExit": "User has one real-world support/action option or risk escalates.",
    },
    "safety-and-crisis": {
        "name": "safety-and-crisis",
        "layer": "safety",
        "description": "Hard safety route for self-harm, suicide, harm, coercion, or real danger.",
        "lifecycleExit": "Immediate danger is lower and real-world support/action is in place.",
    },
}


def is_valid_skill(skill: str) -> bool:
    return skill in CANONICAL_SKILLS


def normalize_skill_name(name: str, context_hint: str | None = None) -> SkillName:
    """Resolve canonical and legacy skill names.

    Contextual aliases are disambiguated conservatively:
    - cognitive-untangle: reality check when the hint includes guesses/motives,
      otherwise collaborative untangling.
    - co-rumination-guard: reality check for speculation loops, otherwise vent.
    - belonging-repair: social bridge for real-world connection, otherwise listening.
    """

    if is_valid_skill(name):
        return name  # type: ignore[return-value]
    if name in SKILL_ALIASES:
        return SKILL_ALIASES[name]

    hint = (context_hint or "").lower()
    if name == "cognitive-untangle":
        if any(token in hint for token in ("guess", "motive", "肯定", "故意", "什么意思")):
            return "reality-soft-check"
        return "collaborative-untangling"
    if name == "co-rumination-guard":
        if any(token in hint for token in ("loop", "speculat", "反复", "到底什么意思")):
            return "reality-soft-check"
        return "vent-container"
    if name == "belonging-repair":
        if any(token in hint for token in ("friend", "现实", "关系", "连接", "support")):
            return "social-bridge"
        return "responsive-listening"

    raise ValueError(f"Unknown skill name: {name}")


def get_all_skill_names() -> tuple[SkillName, ...]:
    return CANONICAL_SKILLS


def get_alias_map() -> dict[str, SkillName]:
    return dict(SKILL_ALIASES)


def get_contextual_alias_map() -> dict[str, tuple[SkillName, SkillName]]:
    return dict(CONTEXTUAL_ALIASES)
