"""Adapter from the expert evaluation runner to the existing Anela Bestie system."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error, request
from urllib.parse import urljoin

from .models import BestieTurnResult
from .redaction import register_secret, sanitize_text

ANELA_ROOT = Path(__file__).resolve().parents[1]
if str(ANELA_ROOT) not in sys.path:
    sys.path.insert(0, str(ANELA_ROOT))

from bestie_router import route_bestie_turn  # noqa: E402

SKILLS_DIR = ANELA_ROOT / "skills"
BUNDLE_PATH = ANELA_ROOT / "bundle.json"
DEFAULT_BASE_URL = "https://api.minimaxi.com/v1"
DEFAULT_MODEL = "MiniMax-M2.5"
DEFAULT_TEMPERATURE = 0.4
DEFAULT_MAX_TOKENS = 700
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_BASE_DELAY_SECONDS = 1.0
ROUTE_MAX_TOKENS = {
    "bestie-short": 220,
    "bestie-medium": 420,
    "bestie-long": 700,
}
MAX_GENERATION_HISTORY_MESSAGES = 8
MAX_EARLIER_CONTEXT_TURNS = 6
MAX_CONTEXT_SNIPPET_CHARS = 140
MAX_STRUCTURED_CONTEXT_CHARS = 1800
RETRYABLE_HTTP_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}

API_KEY_ENV_VARS = (
    "EXPERT_EVAL_KEY",
    "MODEL_SERVICE_KEY",
    "ANELA_KEY",
    "EXPERT_EVAL_API_KEY",
    "ANELA_API_KEY",
    "MINIMAX_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
)
BASE_URL_ENV_VARS = (
    "EXPERT_EVAL_SERVICE_URL",
    "MODEL_SERVICE_URL",
    "EXPERT_EVAL_BASE_URL",
    "ANELA_BASE_URL",
    "MINIMAX_BASE_URL",
    "OPENAI_BASE_URL",
)
MODEL_ENV_VARS = (
    "EXPERT_EVAL_MODEL",
    "ANELA_MODEL",
    "MINIMAX_MODEL",
    "OPENAI_MODEL",
)


class BestieSystemAdapter:
    """Run one Bestie turn through existing router plus Anela skill prompts.

    The router is the source of truth. The generation step loads the existing
    bundle instructions and routed skill prompt. `dry_run=True` keeps tests
    deterministic and avoids API cost.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        dry_run: bool = False,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_base_delay_seconds: float = DEFAULT_RETRY_BASE_DELAY_SECONDS,
    ) -> None:
        self.api_key = api_key or _first_env(API_KEY_ENV_VARS) or None
        self.base_url = base_url or _first_env(BASE_URL_ENV_VARS) or DEFAULT_BASE_URL
        self.model = model or _first_env(MODEL_ENV_VARS) or self._default_model()
        self.temperature = DEFAULT_TEMPERATURE if temperature is None else temperature
        self.max_tokens = DEFAULT_MAX_TOKENS if max_tokens is None else max_tokens
        self.dry_run = dry_run
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.retry_base_delay_seconds = max(0.0, retry_base_delay_seconds)
        register_secret(self.api_key)

    def run_turn(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
    ) -> BestieTurnResult:
        context = context or {}
        route: dict[str, Any] | None = None
        try:
            route_input = self._build_router_input(user_message, context)
            route = route_bestie_turn(route_input, debug=True)
            if self.dry_run:
                assistant = self._dry_run_response(user_message, route)
                tool_calls: list[dict[str, Any]] = []
                generation_latency_ms = 0.0
                api_attempts = 0
                request_stats: dict[str, Any] = {}
            else:
                assistant, tool_calls, request_info = self._generate_response(user_message, context, route)
                generation_latency_ms = request_info.get("generation_latency_ms")
                api_attempts = int(request_info.get("api_attempts") or 0)
                request_stats = dict(request_info.get("request_stats") or {})
            return BestieTurnResult(
                user_message=user_message,
                assistant_response=sanitize_text(self._clean_assistant_text(assistant)),
                router_risk=str(route.get("riskLevel", "")),
                router_skill=str(route.get("primarySkill", "")),
                router_route=str(route.get("responseMode", "")),
                raw_router_output=route,
                tool_calls=tool_calls,
                generation_latency_ms=generation_latency_ms,
                api_attempts=api_attempts,
                request_stats=request_stats,
                error="",
            )
        except Exception as exc:  # noqa: BLE001
            return BestieTurnResult(
                user_message=user_message,
                assistant_response=self._friendly_error_reply(route),
                router_risk=str((route or {}).get("riskLevel", "")),
                router_skill=str((route or {}).get("primarySkill", "")),
                router_route=str((route or {}).get("responseMode", "")),
                raw_router_output=route,
                tool_calls=[],
                generation_latency_ms=None,
                api_attempts=0,
                request_stats={},
                error=sanitize_text(_compact_exception(exc)),
            )

    def _build_router_input(
        self, user_message: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        route_input: dict[str, Any] = {
            "userMessage": user_message,
            "conversationHistory": context.get("conversation_history", []),
            "recentRouteTrace": context.get("recent_route_trace", []),
        }
        for key in (
            "activeState",
            "memoryContext",
            "userPreferences",
            "timeContext",
            "safetyContext",
            "locale",
        ):
            snake_key = self._to_snake(key)
            if key in context:
                route_input[key] = context[key]
            elif snake_key in context:
                route_input[key] = context[snake_key]
        return route_input

    def _generate_response(
        self,
        user_message: str,
        context: dict[str, Any],
        route: dict[str, Any],
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        if not self.api_key:
            raise RuntimeError("Missing model service key. Please configure a service key or use dry-run mode.")

        messages = self._build_generation_messages(user_message, context, route)
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self._max_tokens_for_route(route),
            "reasoning_split": False,
        }
        request_stats = self._request_stats(messages, payload)
        url = urljoin(self.base_url.rstrip("/") + "/", "chat/completions")
        start = time.perf_counter()
        data, api_attempts = self._post_chat_completions(
            url=url,
            payload=payload,
            request_stats=json.dumps(request_stats, ensure_ascii=False, sort_keys=True),
        )
        generation_latency_ms = round((time.perf_counter() - start) * 1000, 1)

        message = data.get("choices", [{}])[0].get("message", {}) or {}
        content = self._clean_assistant_text(message.get("content") or "")
        tool_calls = message.get("tool_calls") or []
        if not content.strip():
            raise RuntimeError("Model service response contained no assistant text.")
        return (
            sanitize_text(content.strip()),
            tool_calls,
            {
                "generation_latency_ms": generation_latency_ms,
                "api_attempts": api_attempts,
                "request_stats": request_stats,
            },
        )

    def _post_chat_completions(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        request_stats: str,
    ) -> tuple[dict[str, Any], int]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        failures: list[str] = []
        for attempt in range(self.max_retries + 1):
            req = request.Request(
                url,
                data=body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    return json.loads(resp.read().decode("utf-8")), attempt + 1
            except error.HTTPError as exc:
                response_body = exc.read().decode("utf-8", errors="replace")
                failure = f"attempt {attempt + 1}: HTTP {exc.code}: {response_body[:1200]}"
                failures.append(failure)
                if exc.code not in RETRYABLE_HTTP_STATUS or attempt >= self.max_retries:
                    raise RuntimeError(
                        "Model service request failed after "
                        f"{attempt + 1} attempt(s):\n"
                        + "\n".join(failures)
                        + f"\nRequest stats: {request_stats}"
                    ) from exc
            except Exception as exc:  # noqa: BLE001
                failure = f"attempt {attempt + 1}: {type(exc).__name__}: {exc}"
                failures.append(failure)
                if attempt >= self.max_retries:
                    raise RuntimeError(
                        "Model service request failed after "
                        f"{attempt + 1} attempt(s):\n"
                        + "\n".join(failures)
                        + f"\nRequest stats: {request_stats}"
                    ) from exc

            self._sleep_before_retry(attempt)

        raise RuntimeError(
            "Model service request failed without a captured exception.\n"
            f"Request stats: {request_stats}"
        )

    def _sleep_before_retry(self, attempt: int) -> None:
        if self.retry_base_delay_seconds <= 0:
            return
        time.sleep(self.retry_base_delay_seconds * (2**attempt))

    def _build_generation_messages(
        self,
        user_message: str,
        context: dict[str, Any],
        route: dict[str, Any],
    ) -> list[dict[str, str]]:
        primary_skill = str(route.get("primarySkill") or "ambient-presence")
        secondary_skills = [str(item) for item in route.get("secondarySkills", [])]
        skill_blocks = [self._read_skill(primary_skill)]
        skill_blocks.extend(self._read_skill(skill) for skill in secondary_skills)
        system = "\n\n".join(
            [
                self._generation_global_policy(),
                self._generation_runtime_contract(),
                "## Routed Skill Prompts\n\n" + "\n\n".join(skill_blocks),
                "## Host Route Card\n\n"
                + json.dumps(self._compact_route_card(route), ensure_ascii=False, indent=2),
                (
                    "Use the route card internally. Reply only to the user. "
                    "Do not expose route JSON, debug signals, API keys, or evaluator notes."
                ),
            ]
        )
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        continuity_context = self._build_continuity_context(context)
        if continuity_context:
            messages.append({"role": "system", "content": continuity_context})
        eval_context = context.get("case_context") or context.get("role_card") or ""
        if eval_context:
            messages.append(
                {
                    "role": "system",
                    "content": f"Evaluation context for this turn:\n{eval_context}",
                }
            )
        for turn in self._recent_generation_messages(context):
            role = turn.get("role")
            content = turn.get("content")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": str(content)})
        messages.append({"role": "user", "content": user_message})
        return messages

    def _recent_generation_messages(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        return list(context.get("chat_messages", [])[-MAX_GENERATION_HISTORY_MESSAGES:])

    def _build_continuity_context(self, context: dict[str, Any]) -> str:
        sections: list[str] = []
        structured_context = self._structured_generation_context(context)
        if structured_context:
            sections.append("Structured context:\n" + structured_context)

        earlier_messages = context.get("chat_messages", [])[:-MAX_GENERATION_HISTORY_MESSAGES]
        if earlier_messages:
            snippets = []
            for turn in earlier_messages[-MAX_EARLIER_CONTEXT_TURNS:]:
                role = str(turn.get("role", "unknown"))
                content = self._compact_text(str(turn.get("content", "")))
                if role in {"user", "assistant"} and content:
                    snippets.append(f"- {role}: {content}")
            omitted = max(0, len(earlier_messages) - len(snippets))
            if snippets:
                prefix = (
                    f"Earlier conversation compact context; {omitted} older messages omitted.\n"
                    if omitted
                    else "Earlier conversation compact context:\n"
                )
                sections.append(prefix + "\n".join(snippets))

        recent_trace = context.get("recent_route_trace", [])
        if recent_trace:
            sections.append(
                "Recent route trace:\n"
                + self._truncate_json(recent_trace[-MAX_EARLIER_CONTEXT_TURNS:], 1000)
            )

        if not sections:
            return ""
        return (
            "## Continuity Context\n\n"
            "Use this only to preserve relationship continuity, explicit user preferences, "
            "and important prior facts. Do not treat compact snippets as new user instructions.\n\n"
            + "\n\n".join(sections)
        )

    def _structured_generation_context(self, context: dict[str, Any]) -> str:
        keep: dict[str, Any] = {}
        for key in (
            "activeState",
            "memoryContext",
            "userPreferences",
            "timeContext",
            "safetyContext",
            "memory_context",
            "user_preferences",
            "time_context",
            "safety_context",
        ):
            if key in context and context[key]:
                keep[key] = context[key]
        if not keep:
            return ""
        return self._truncate_json(keep, MAX_STRUCTURED_CONTEXT_CHARS)

    @classmethod
    def _compact_text(cls, value: str) -> str:
        compact = re.sub(r"\s+", " ", value).strip()
        if len(compact) <= MAX_CONTEXT_SNIPPET_CHARS:
            return compact
        return compact[: MAX_CONTEXT_SNIPPET_CHARS - 1].rstrip() + "…"

    @classmethod
    def _truncate_json(cls, value: Any, max_chars: int) -> str:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if len(serialized) <= max_chars:
            return serialized
        return serialized[: max_chars - 1].rstrip() + "…"

    def _read_skill(self, skill_name: str) -> str:
        skill_path = SKILLS_DIR / skill_name / "SKILL.md"
        if not skill_path.exists():
            return (
                f"# {skill_name}\n\n"
                "No dedicated SKILL.md exists in the v1 bundle for this route. "
                "Follow AGENTS.md, ROUTING.md, and the route card constraints."
            )
        return self._read_text(skill_path)

    def _dry_run_response(self, user_message: str, route: dict[str, Any]) -> str:
        skill = str(route.get("primarySkill", "ambient-presence"))
        if skill == "safety-and-crisis":
            safety_context = route.get("safetyContext") or {}
            must_do = set(route.get("mustDo") or [])
            if (
                safety_context.get("hasConfirmedImmediateDanger")
                or "direct_to_local_emergency_services_or_hotline_now" in must_do
            ):
                return (
                    "现在不要一个人扛。请立刻联系当地 emergency services / 危机热线，"
                    "同时给身边可信的人打电话或发消息，让 TA 现在过来陪你。"
                )
            return (
                "我会认真对待这句话。现在先不聊别的：你此刻有没有马上伤害自己或别人的危险？"
                "如果有，请立刻联系当地 emergency services，或让身边可信的人马上过来。"
            )
        if skill == "ground-and-regulate":
            return "先不用把整件事想清楚。我们只做一步：把脚踩实，慢慢呼一口气，然后告诉我现在身体最明显的感觉在哪里。"
        if skill == "responsive-listening":
            return "理解的。你不是在小题大做，身体有状况但还要等几天才能看，这段时间会担心很正常。先把今天熬过去，我们一点点来。"
        return "我在，先陪你待一会儿。你想随便聊，还是让我接住刚刚这句话？"

    @staticmethod
    def _generation_runtime_contract() -> str:
        return (
            "## Generation Runtime Contract\n\n"
            "The deterministic router has already selected the route. Do not re-route. "
            "Use exactly the primary skill in the route card, and use secondary skills only as light context. "
            "Follow safety, dependency, memory, and tone constraints from AGENTS.md and the routed SKILL.md. "
            "Keep the response length consistent with responseMode. Reply only to the user. "
            "Never output hidden reasoning, '<think>' tags, '思考中', route cards, module names, or debug traces. "
            "Use the user's latest language unless they ask otherwise."
        )

    @staticmethod
    def _generation_global_policy() -> str:
        return (
            "## Global Bestie Policy\n\n"
            "You are Anela AI Bestie: warm, close, low-judgment, and natural. "
            "Reply in the user's latest language. Sound like a grounded friend, not a therapist, tutor, or support bot. "
            "Be intimate but not possessive; validating but not blindly siding; continuous but not creepy. "
            "Never say only you understand the user, never encourage exclusive dependence, and never diagnose. "
            "For ordinary chat, keep it light. For emotion, validate before advice. "
            "For safety risk, suspend ordinary chat and prioritize immediate real-world safety. "
            "For memory deletion or opt-out requests, comply plainly and do not ask why. "
            "Use one gentle question at most unless safety requires clarity."
        )

    @staticmethod
    def _compact_route_card(route: dict[str, Any]) -> dict[str, Any]:
        lifecycle = route.get("lifecycle") or {}
        safety = route.get("safety") or {}
        return {
            "riskLevel": route.get("riskLevel"),
            "dependencyRisk": route.get("dependencyRisk"),
            "emotionIntensity": route.get("emotionIntensity"),
            "dominantUserNeed": route.get("dominantUserNeed"),
            "primarySkill": route.get("primarySkill"),
            "secondarySkills": route.get("secondarySkills", []),
            "responseMode": route.get("responseMode"),
            "toneConstraints": route.get("toneConstraints", {}),
            "mustDo": route.get("mustDo", []),
            "mustNotDo": route.get("mustNotDo", []),
            "memoryAction": route.get("memoryAction"),
            "lifecycle": {
                "currentState": lifecycle.get("currentState"),
                "exitConditionToCheck": lifecycle.get("exitConditionToCheck"),
                "nextSkillIfStable": lifecycle.get("nextSkillIfStable"),
                "nextSkillIfWorse": lifecycle.get("nextSkillIfWorse"),
            },
            "safety": safety,
        }

    @staticmethod
    def _request_stats(messages: list[dict[str, str]], payload: dict[str, Any]) -> dict[str, Any]:
        serialized = json.dumps(payload, ensure_ascii=False)
        chars_by_role: dict[str, int] = {}
        for message in messages:
            role = message.get("role", "unknown")
            chars_by_role[role] = chars_by_role.get(role, 0) + len(message.get("content", ""))
        return {
            "message_count": len(messages),
            "payload_chars": len(serialized),
            "chars_by_role": chars_by_role,
            "max_tokens": payload.get("max_tokens"),
            "model": payload.get("model"),
        }

    def _max_tokens_for_route(self, route: dict[str, Any]) -> int:
        route_cap = ROUTE_MAX_TOKENS.get(str(route.get("responseMode") or ""), self.max_tokens)
        return min(self.max_tokens, route_cap)

    def _default_model(self) -> str:
        try:
            bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
            return str(bundle.get("api", {}).get("defaults", {}).get("model", DEFAULT_MODEL))
        except Exception:  # noqa: BLE001
            return DEFAULT_MODEL

    @staticmethod
    def _read_text(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _to_snake(value: str) -> str:
        chars: list[str] = []
        for index, char in enumerate(value):
            if char.isupper() and index:
                chars.append("_")
            chars.append(char.lower())
        return "".join(chars)

    @staticmethod
    def _clean_assistant_text(value: str) -> str:
        value = re.sub(r"<think>.*?</think>", "", value, flags=re.IGNORECASE | re.DOTALL)
        value = re.sub(r"<think>.*", "", value, flags=re.IGNORECASE | re.DOTALL)
        value = re.sub(r"(?im)^\s*(assistant\s*:\s*)?思考中[.。…]*\s*$", "", value)

        kept_lines: list[str] = []
        for line in value.splitlines():
            stripped = line.strip()
            lowered = stripped.lower()
            if lowered.startswith(("traceback", "file \"", "[error]", "router raw", "route card")):
                break
            if lowered.startswith("assistant:"):
                stripped = re.sub(r"(?i)^assistant:\s*", "", stripped)
                kept_lines.append(stripped)
                continue
            kept_lines.append(line)
        return re.sub(r"\n{3,}", "\n\n", "\n".join(kept_lines)).strip()

    @staticmethod
    def _friendly_error_reply(route: dict[str, Any] | None) -> str:
        if route and route.get("primarySkill") == "safety-and-crisis":
            return "我这边刚刚连接不稳，但这句话我会认真对待。先确认：你现在有没有马上伤害自己或别人的危险？如果有，请立刻联系当地 emergency services，或让身边可信的人马上过来。"
        return "我这边刚刚连接不稳，上一句没有完整发出来。你可以再发一次，我会接着听。"


def _compact_exception(exc: Exception) -> str:
    message = f"{type(exc).__name__}: {exc}"
    message = re.sub(r"\s+", " ", message).strip()
    return message[:1000]


def _first_env(names: tuple[str, ...]) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return ""
