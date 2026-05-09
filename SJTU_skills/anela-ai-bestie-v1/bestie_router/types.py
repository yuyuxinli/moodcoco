"""Pydantic schemas for the Anela AI Friend policy router."""

from __future__ import annotations

from typing import Any, Awaitable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

SkillName = Literal[
    "ambient-presence",
    "active-celebration",
    "playful-attunement",
    "relationship-memory",
    "ritual-checkin",
    "responsive-listening",
    "emotion-labeling",
    "vent-container",
    "ground-and-regulate",
    "reality-soft-check",
    "rupture-repair",
    "collaborative-untangling",
    "agency-next-step",
    "identity-mirror",
    "pattern-witness",
    "social-bridge",
    "safety-and-crisis",
]

ConversationState = Literal[
    "light-connection",
    "emotional-opening",
    "high-arousal",
    "meaning-making",
    "action-planning",
    "relationship-repair",
    "dependency-boundary",
    "safety-crisis",
    "unknown",
]

EntryType = Literal[
    "casual",
    "joyful",
    "playful",
    "negative-emotion",
    "action-request",
    "self-exploration",
    "pattern",
    "dependency",
    "agent-rupture",
    "crisis",
    "unknown",
]

DominantNeed = Literal[
    "companionship",
    "celebration",
    "validation",
    "regulation",
    "clarity",
    "action",
    "identity",
    "belonging",
    "autonomy",
    "social-connection",
    "safety",
    "unknown",
]

RiskLevel = Literal["none", "low", "medium", "high"]
DependencyRisk = Literal["none", "low", "medium", "high"]
EmotionIntensity = Literal[0, 1, 2, 3, 4]
ResponseMode = Literal[
    "bestie-short",
    "bestie-medium",
    "structured",
    "crisis",
    "repair",
    "playful",
    "celebratory",
]
MemoryAction = Literal[
    "none",
    "read",
    "write-candidate",
    "update",
    "delete",
    "ask-authorization",
]
MemoryTargetType = Literal[
    "preference",
    "relationship",
    "goal",
    "emotional-pattern",
    "milestone",
    "sensitive",
]
Sensitivity = Literal["low", "medium", "high"]


class DictLikeModel(BaseModel):
    """BaseModel with dict-style access for incremental migration.

    The router now validates its schemas with Pydantic, while existing host code
    and tests can continue using `obj["field"]`, `obj.get("field")`, and
    `field in obj`. Public helpers dump models to plain JSON-serializable dicts.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def __delitem__(self, key: str) -> None:
        if key not in self.model_fields:
            raise KeyError(key)
        setattr(self, key, None)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str) or key not in self.model_fields:
            return False
        return getattr(self, key) is not None

    def get(self, key: str, default: Any = None) -> Any:
        if key not in self.model_fields:
            return default
        value = getattr(self, key)
        return default if value is None else value


class ToneConstraints(DictLikeModel):
    warmth: Literal["low", "medium", "high"]
    playfulness: Literal["none", "low", "medium", "high"]
    analysisDepth: Literal["none", "low", "medium", "high"]
    directiveLevel: Literal["low", "medium", "high"]
    clinicalLanguageAllowed: bool
    bestieToneRequired: bool


class MemoryTarget(DictLikeModel):
    type: MemoryTargetType
    content: str
    sensitivity: Sensitivity
    authorizationRequired: bool
    canProactivelyRecall: bool
    reason: str


class LifecycleBlock(DictLikeModel):
    currentState: ConversationState
    enterReason: str
    exitConditionToCheck: str
    nextSkillIfStable: SkillName | None = None
    nextSkillIfWorse: SkillName | None = None
    forbiddenTransitions: list[SkillName] = Field(default_factory=list)


class SafetyBlock(DictLikeModel):
    ordinaryChatSuspended: bool
    requiresRealitySupport: bool
    askRiskQuestions: bool
    crisisResourceNeeded: bool
    hardLocked: bool


class ExtractedSignals(DictLikeModel):
    entryType: EntryType
    emotionIntensity: EmotionIntensity
    dominantEmotions: list[str] = Field(default_factory=list)
    dominantNeed: DominantNeed
    riskLevel: RiskLevel
    dependencyRisk: DependencyRisk
    arousalSignals: list[str] = Field(default_factory=list)
    cognitiveDistortionSignals: list[str] = Field(default_factory=list)
    relationshipSignals: list[str] = Field(default_factory=list)
    dependencySignals: list[str] = Field(default_factory=list)
    riskSignals: list[str] = Field(default_factory=list)
    memorySignals: list[str] = Field(default_factory=list)
    repetitionCount: int = 1
    asksForAdvice: bool = False
    asksForNoAdvice: bool = False
    asksForMessageDraft: bool = False
    asksForDecisionDelegation: bool = False
    asksForOnlyAiSupport: bool = False
    hasAgentFeedback: bool = False
    hasHighArousal: bool = False
    hasImmediateSafetyConcern: bool = False


class RouteCard(DictLikeModel):
    routeVersion: str
    riskLevel: RiskLevel
    dependencyRisk: DependencyRisk
    emotionIntensity: EmotionIntensity
    dominantUserNeed: DominantNeed
    primarySkill: SkillName
    secondarySkills: list[SkillName] = Field(default_factory=list, max_length=2)
    responseMode: ResponseMode
    toneConstraints: ToneConstraints
    mustDo: list[str] = Field(default_factory=list)
    mustNotDo: list[str] = Field(default_factory=list)
    memoryAction: MemoryAction = "none"
    memoryTargets: list[MemoryTarget] | None = None
    lifecycle: LifecycleBlock
    safety: SafetyBlock
    routeReason: str
    confidence: float = Field(ge=0.0, le=1.0)
    debugSignals: ExtractedSignals | None = None

    @field_validator("secondarySkills")
    @classmethod
    def _secondary_skill_limit(cls, value: list[SkillName]) -> list[SkillName]:
        return value[:2]


class ConversationTurn(DictLikeModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str | None = None
    routeCard: RouteCard | None = None


class RouteTraceItem(DictLikeModel):
    primarySkill: SkillName
    timestamp: str | None = None
    emotionIntensity: EmotionIntensity | None = None
    riskLevel: RiskLevel | None = None
    routeReason: str | None = None


class MemoryContext(DictLikeModel):
    visibleFacts: list[str] = Field(default_factory=list)
    permissions: dict[str, bool] = Field(default_factory=dict)
    lastMemoryAction: MemoryAction | None = None


class UserPreferences(DictLikeModel):
    language: str | None = None
    nickname: str | None = None
    preferredTone: str | None = None
    memoryOptIn: bool | None = None


class TimeContext(DictLikeModel):
    nowIso: str | None = None
    timezone: str | None = None
    localDate: str | None = None


class SafetyContext(DictLikeModel):
    activeSafetyLock: bool = False
    lastRiskLevel: RiskLevel | None = None
    hasConfirmedImmediateDanger: bool = False
    hasConfirmedLowerRisk: bool = False
    hasRealitySupport: bool = False


class RouterInput(DictLikeModel):
    userMessage: str
    conversationHistory: list[ConversationTurn] = Field(default_factory=list)
    activeState: ConversationState | None = None
    recentRouteTrace: list[RouteTraceItem] = Field(default_factory=list)
    memoryContext: MemoryContext | None = None
    userPreferences: UserPreferences | None = None
    timeContext: TimeContext | None = None
    safetyContext: SafetyContext | None = None
    locale: str | None = None


class SoftRouteSuggestion(DictLikeModel):
    """Non-authoritative LLM/Pydantic-AI output.

    It can suggest a route direction, but it is never a final RouteCard and
    cannot bypass hard gates, deterministic merge, validation, or memory policy.
    """

    primarySkill: SkillName | None = None
    secondarySkills: list[SkillName] = Field(default_factory=list, max_length=2)
    dominantUserNeed: DominantNeed | None = None
    suggestedMemoryAction: MemoryAction | None = None
    routeReason: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class SoftRouteSuggestionProvider(Protocol):
    """Optional provider, including a Pydantic AI-backed implementation."""

    def classify(
        self, input_data: RouterInput, signals: ExtractedSignals
    ) -> (
        SoftRouteSuggestion
        | dict[str, Any]
        | Awaitable[SoftRouteSuggestion | dict[str, Any]]
    ):
        """Return a SoftRouteSuggestion, not a final RouteCard."""


LlmRouteClassifier = SoftRouteSuggestionProvider


class BenchmarkCase(DictLikeModel):
    id: str
    userMessage: str
    optionalHistory: list[ConversationTurn] = Field(default_factory=list)
    expectedPrimarySkill: SkillName
    expectedRiskLevel: RiskLevel
    expectedDependencyRisk: DependencyRisk
    expectedMemoryAction: MemoryAction | None = None
    shouldIncludeMustDo: list[str] = Field(default_factory=list)
    shouldIncludeMustNotDo: list[str] = Field(default_factory=list)


def ensure_router_input(input_data: RouterInput | dict[str, Any]) -> RouterInput:
    if isinstance(input_data, RouterInput):
        return input_data
    return RouterInput.model_validate(input_data)


def ensure_signals(signals: ExtractedSignals | dict[str, Any]) -> ExtractedSignals:
    if isinstance(signals, ExtractedSignals):
        return signals
    return ExtractedSignals.model_validate(signals)


def ensure_route_card(route: RouteCard | dict[str, Any]) -> RouteCard:
    if isinstance(route, RouteCard):
        return route
    return RouteCard.model_validate(route)


def ensure_soft_suggestion(
    suggestion: SoftRouteSuggestion | dict[str, Any] | None,
) -> SoftRouteSuggestion | None:
    if suggestion is None:
        return None
    if isinstance(suggestion, SoftRouteSuggestion):
        return suggestion
    return SoftRouteSuggestion.model_validate(suggestion)
