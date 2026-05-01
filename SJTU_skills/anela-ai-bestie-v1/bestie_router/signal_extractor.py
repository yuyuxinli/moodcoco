"""Deterministic multi-signal extraction for Bestie routing."""

from __future__ import annotations

from .constants import (
    ACTION_REQUEST_PHRASES,
    AGENT_RUPTURE_PHRASES,
    COGNITIVE_DISTORTION_PHRASES,
    DECISION_DELEGATION_PHRASES,
    DEPENDENCY_PHRASES,
    HIGH_AROUSAL_PHRASES,
    HIGH_RISK_PHRASES,
    JOY_SELF_DOUBT_PHRASES,
    JOYFUL_PHRASES,
    MAJOR_DECISION_TERMS,
    MEMORY_PHRASES,
    MESSAGE_DRAFT_PHRASES,
    NEGATIVE_EMOTION_PHRASES,
    NO_ADVICE_PHRASES,
    PATTERN_PHRASES,
    PLAN_TERMS,
    PLAYFUL_PHRASES,
    RELATIONSHIP_TERMS,
    RISK_PHRASES,
    SAFETY_MEANS_TERMS,
    SELF_EXPLORATION_PHRASES,
)
from .types import (
    DependencyRisk,
    DominantNeed,
    EmotionIntensity,
    EntryType,
    ExtractedSignals,
    RiskLevel,
    RouterInput,
    ensure_router_input,
)

CASUAL_PHRASES = (
    "无聊",
    "陪我",
    "聊会",
    "聊会儿",
    "说废话",
    "没啥事",
    "随便聊",
    "你在吗",
    "bored",
    "keep me company",
    "hang out",
    "no topic",
)


def _normalize(text: str) -> str:
    return text.strip().lower()


def _find_phrases(text: str, phrases: tuple[str, ...]) -> list[str]:
    lowered = _normalize(text)
    return [phrase for phrase in phrases if phrase.lower() in lowered]


def _latest_position(text: str, phrases: tuple[str, ...]) -> int:
    lowered = _normalize(text)
    positions = [lowered.rfind(phrase.lower()) for phrase in phrases]
    return max(positions) if positions else -1


def _history_user_texts(input_data: RouterInput) -> list[str]:
    return [
        turn["content"]
        for turn in input_data.get("conversationHistory", [])
        if turn["role"] == "user"
    ]


def _has_recent_assistant_turn(input_data: RouterInput) -> bool:
    history = input_data.get("conversationHistory", [])
    return any(turn["role"] == "assistant" for turn in history[-3:])


def _count_repetition(input_data: RouterInput, text: str) -> int:
    lowered = _normalize(text)
    markers = (
        "到底什么意思",
        "什么意思",
        "是不是故意",
        "肯定不爱我",
        "他肯定",
        "她肯定",
        "what does he mean",
        "what does she mean",
    )
    marker = next((item for item in markers if item in lowered), "")
    if not marker:
        trace = input_data.get("recentRouteTrace", [])
        if len(trace) >= 2 and all(
            item.get("primarySkill") in ("reality-soft-check", "vent-container")
            for item in trace[-3:]
        ):
            return len(trace[-3:]) + 1
        return 1
    count = 1
    for previous in _history_user_texts(input_data):
        if marker in _normalize(previous):
            count += 1
    return count


def _risk_level(
    text: str, risk_signals: list[str], means: list[str], plan_terms: list[str]
) -> tuple[RiskLevel, bool]:
    if not risk_signals:
        return "none", False

    high_phrase = any(signal in HIGH_RISK_PHRASES for signal in risk_signals)
    has_plan_or_means = bool(means or plan_terms)
    lowered = _normalize(text)
    direct_suicide_hint = any(
        phrase in lowered
        for phrase in (
            "不想活",
            "想死",
            "活不下去",
            "撑不住",
            "撑不下去",
            "想消失",
            "没人需要我",
            "没有人需要我",
            "want to die",
            "can't go on",
            "cant go on",
            "kill myself",
            "suicide",
            "self harm",
            "self-harm",
        )
    )
    real_world_danger = any(
        phrase in lowered
        for phrase in ("被威胁", "被控制", "被跟踪", "家暴", "性侵", "hurt someone")
    )

    if high_phrase or (direct_suicide_hint and has_plan_or_means) or real_world_danger:
        return "high", True
    if direct_suicide_hint:
        return "high", True
    return "medium", True


def _dependency_risk(
    text: str, dependency_signals: list[str], asks_decision_delegation: bool
) -> tuple[DependencyRisk, bool]:
    lowered = _normalize(text)
    only_ai = bool(dependency_signals)
    has_major_decision = any(term.lower() in lowered for term in MAJOR_DECISION_TERMS)

    if any(
        phrase in lowered
        for phrase in (
            "别人都没用",
            "你不要离开我",
            "不要让我去找别人",
            "只跟你说",
            "我以后只跟你说",
            "real friends are useless",
            "don't leave me",
            "dont leave me",
            "only want to talk to you",
        )
    ):
        return "high", True
    if only_ai:
        return "medium", True
    if asks_decision_delegation and has_major_decision:
        return "medium", False
    if asks_decision_delegation:
        return "low", False
    return "none", False


def _dominant_need(
    *,
    risk_level: RiskLevel,
    dependency_risk: DependencyRisk,
    has_high_arousal: bool,
    asks_decision_delegation: bool,
    joyful: bool,
    action: bool,
    cognitive: bool,
    self_exploration: bool,
    negative: bool,
) -> DominantNeed:
    if risk_level in ("medium", "high"):
        return "safety"
    if has_high_arousal:
        return "regulation"
    if dependency_risk in ("medium", "high"):
        return "autonomy" if asks_decision_delegation else "social-connection"
    if joyful:
        return "celebration"
    if self_exploration:
        return "identity"
    if action:
        return "action"
    if cognitive:
        return "clarity"
    if negative:
        return "validation"
    return "companionship"


def _entry_type(
    *,
    risk_level: RiskLevel,
    has_agent_feedback: bool,
    dependency_risk: DependencyRisk,
    joyful: bool,
    playful: bool,
    action: bool,
    self_exploration: bool,
    repetition_count: int,
    pattern: bool,
    negative: bool,
    casual: bool,
) -> EntryType:
    if risk_level in ("medium", "high"):
        return "crisis"
    if has_agent_feedback:
        return "agent-rupture"
    if dependency_risk in ("medium", "high"):
        return "dependency"
    if joyful:
        return "joyful"
    if playful:
        return "playful"
    if repetition_count >= 3 or pattern:
        return "pattern"
    if self_exploration:
        return "self-exploration"
    if action:
        return "action-request"
    if negative:
        return "negative-emotion"
    if casual:
        return "casual"
    return "unknown"


def extract_signals(input_data: RouterInput) -> ExtractedSignals:
    """Extract deterministic signals from the latest turn plus lightweight context."""

    input_data = ensure_router_input(input_data)
    text = input_data["userMessage"]
    lowered = _normalize(text)

    risk_signals = _find_phrases(text, RISK_PHRASES)
    means_terms = _find_phrases(text, SAFETY_MEANS_TERMS) if risk_signals else []
    plan_terms = _find_phrases(text, PLAN_TERMS) if risk_signals else []
    risk_level, has_immediate_safety = _risk_level(
        text, risk_signals, means_terms, plan_terms
    )

    arousal_signals = _find_phrases(text, HIGH_AROUSAL_PHRASES)
    has_high_arousal = bool(arousal_signals)

    rupture_signals = _find_phrases(text, AGENT_RUPTURE_PHRASES)
    has_agent_feedback = bool(rupture_signals) and (
        "算了" not in rupture_signals or _has_recent_assistant_turn(input_data)
    )
    if "你记错了" in rupture_signals or "you remembered wrong" in rupture_signals:
        has_agent_feedback = True

    dependency_signals = _find_phrases(text, DEPENDENCY_PHRASES)
    asks_decision_delegation = bool(_find_phrases(text, DECISION_DELEGATION_PHRASES))
    dependency_risk, asks_only_ai_support = _dependency_risk(
        text, dependency_signals, asks_decision_delegation
    )

    joyful_signals = _find_phrases(text, JOYFUL_PHRASES)
    playful_signals = _find_phrases(text, PLAYFUL_PHRASES)
    action_signals = _find_phrases(text, ACTION_REQUEST_PHRASES)
    message_draft_signals = _find_phrases(text, MESSAGE_DRAFT_PHRASES)
    cognitive_signals = _find_phrases(text, COGNITIVE_DISTORTION_PHRASES)
    memory_signals = _find_phrases(text, MEMORY_PHRASES)
    negative_signals = _find_phrases(text, NEGATIVE_EMOTION_PHRASES)
    self_exploration_signals = _find_phrases(text, SELF_EXPLORATION_PHRASES)
    pattern_signals = _find_phrases(text, PATTERN_PHRASES)
    relationship_signals = _find_phrases(text, RELATIONSHIP_TERMS)
    casual_signals = _find_phrases(text, CASUAL_PHRASES)

    advice_pos = _latest_position(text, ACTION_REQUEST_PHRASES)
    no_advice_pos = _latest_position(text, NO_ADVICE_PHRASES)
    asks_for_no_advice = no_advice_pos > -1 and no_advice_pos >= advice_pos
    asks_for_advice = advice_pos > -1 and advice_pos > no_advice_pos

    repetition_count = _count_repetition(input_data, text)
    negative = bool(negative_signals or cognitive_signals or asks_for_no_advice)
    joyful = bool(joyful_signals)
    playful = bool(playful_signals)
    action = bool(action_signals or asks_decision_delegation)
    self_exploration = bool(self_exploration_signals)
    pattern = bool(pattern_signals)

    if has_immediate_safety:
        emotion_intensity: EmotionIntensity = 4
    elif has_high_arousal:
        emotion_intensity = 3
    elif negative or repetition_count >= 3 or self_exploration:
        emotion_intensity = 2
    elif joyful or playful or action or memory_signals:
        emotion_intensity = 1
    else:
        emotion_intensity = 0

    dominant_emotions = [
        *joyful_signals,
        *_find_phrases(text, JOY_SELF_DOUBT_PHRASES),
        *negative_signals,
        *arousal_signals,
    ]
    dominant_need = _dominant_need(
        risk_level=risk_level,
        dependency_risk=dependency_risk,
        has_high_arousal=has_high_arousal,
        asks_decision_delegation=asks_decision_delegation,
        joyful=joyful,
        action=action,
        cognitive=bool(cognitive_signals),
        self_exploration=self_exploration,
        negative=negative,
    )
    entry_type = _entry_type(
        risk_level=risk_level,
        has_agent_feedback=has_agent_feedback,
        dependency_risk=dependency_risk,
        joyful=joyful,
        playful=playful,
        action=action,
        self_exploration=self_exploration,
        repetition_count=repetition_count,
        pattern=pattern,
        negative=negative,
        casual=bool(casual_signals or not lowered),
    )

    return ExtractedSignals(
        entryType=entry_type,
        emotionIntensity=emotion_intensity,
        dominantEmotions=list(dict.fromkeys(dominant_emotions)),
        dominantNeed=dominant_need,
        riskLevel=risk_level,
        dependencyRisk=dependency_risk,
        arousalSignals=arousal_signals,
        cognitiveDistortionSignals=cognitive_signals,
        relationshipSignals=relationship_signals,
        dependencySignals=dependency_signals,
        riskSignals=risk_signals,
        memorySignals=memory_signals,
        repetitionCount=repetition_count,
        asksForAdvice=asks_for_advice,
        asksForNoAdvice=asks_for_no_advice,
        asksForMessageDraft=bool(message_draft_signals),
        asksForDecisionDelegation=asks_decision_delegation,
        asksForOnlyAiSupport=asks_only_ai_support,
        hasAgentFeedback=has_agent_feedback,
        hasHighArousal=has_high_arousal,
        hasImmediateSafetyConcern=has_immediate_safety,
    )
