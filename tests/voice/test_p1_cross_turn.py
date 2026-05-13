"""P1 TDD tests — cross-turn features for Speaker+Thinker architecture.

Tests define expected behavior BEFORE implementation.
All tests should FAIL initially (red), then pass after code is written (green).

Three feature groups:
  1. next_likely_contexts — Thinker 预测 + Context 预组装 + Speaker 读取
  2. keyword_filter — Speaker 输出前的关键词/正则过滤 (L2 安全)
  3. async_safety_review — Thinker 审查 Speaker 输出，发现问题下轮修正 (L3 安全)
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# Group 1: next_likely_contexts — Thinker 预测 + Context 预组装
# ═══════════════════════════════════════════════════════════════════════════════


class TestNextLikelyContexts:
    """Thinker outputs next_likely_contexts, bridge pre-assembles, Speaker reads."""

    def test_slow_think_deps_has_next_likely_contexts_field(self):
        """SlowThinkDeps should have a next_likely_contexts list field."""
        from backend.slow import SlowThinkDeps

        deps = SlowThinkDeps(session_id="s1", user_message="hi")
        assert hasattr(deps, "next_likely_contexts")
        assert deps.next_likely_contexts == []

    def test_fast_think_deps_has_prewarmed_contexts_field(self):
        """FastThinkDeps should have a prewarmed_contexts dict field."""
        from backend.fast import FastThinkDeps

        deps = FastThinkDeps(session_id="s1", memory_text="")
        assert hasattr(deps, "prewarmed_contexts")
        assert deps.prewarmed_contexts == {}

    def test_slow_set_next_likely_contexts_tool_exists(self):
        """Thinker should have a tool to set next_likely_contexts."""
        from backend.slow import slow_agent

        tool_names = list(slow_agent._function_toolset.tools)
        assert "slow_set_next_likely_contexts" in tool_names

    @pytest.mark.asyncio
    async def test_slow_set_next_likely_contexts_writes_to_deps(self):
        """The tool should write predicted contexts to SlowThinkDeps."""
        from backend.slow import SlowThinkDeps, slow_set_next_likely_contexts

        deps = SlowThinkDeps(session_id="s1", user_message="我好烦")
        ctx = SimpleNamespace(deps=deps)

        await slow_set_next_likely_contexts(ctx, ["untangle(困惑)", "calm-body(焦虑)"])

        assert deps.next_likely_contexts == ["untangle(困惑)", "calm-body(焦虑)"]

    def test_fast_voice_system_extras_includes_prewarmed_hit(self):
        """When prewarmed context matches current skill, extras should include it."""
        from backend.fast import FastThinkDeps

        deps = FastThinkDeps(
            session_id="s1",
            memory_text="",
            voice_session=object(),
            prewarmed_contexts={"untangle": "预组装的 untangle context 内容"},
            skill_bundle=["untangle skill text"],
        )
        extras = deps.voice_system_extras()
        assert "预组装的 untangle context 内容" in extras


# ═══════════════════════════════════════════════════════════════════════════════
# Group 2: keyword_filter — Speaker 输出前关键词/正则过滤 (L2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestKeywordFilter:
    """L2 safety: keyword/regex filter applied before Speaker output."""

    def test_keyword_filter_module_exists(self):
        """backend.safety module should exist with a filter function."""
        from backend.safety import keyword_filter

        assert callable(keyword_filter)

    def test_keyword_filter_blocks_dangerous_content(self):
        """Filter should block text containing crisis-level harmful content."""
        from backend.safety import keyword_filter

        result = keyword_filter("你可以尝试割腕来释放压力")
        assert result.blocked is True
        assert result.reason  # should explain why

    def test_keyword_filter_passes_normal_content(self):
        """Filter should pass normal emotional content through."""
        from backend.safety import keyword_filter

        result = keyword_filter("我理解你现在的感受，这确实很难受。")
        assert result.blocked is False

    def test_keyword_filter_blocks_diagnosis(self):
        """Filter should block text that sounds like clinical diagnosis."""
        from backend.safety import keyword_filter

        result = keyword_filter("根据你的描述，你可能患有抑郁症")
        assert result.blocked is True

    def test_keyword_filter_returns_sanitized_text(self):
        """When blocked, filter should provide a safe replacement."""
        from backend.safety import keyword_filter

        result = keyword_filter("你应该去死")
        assert result.blocked is True
        assert result.safe_replacement  # should have a fallback


# ═══════════════════════════════════════════════════════════════════════════════
# Group 3: async_safety_review — Thinker 异步审查 Speaker 输出 (L3)
# ═══════════════════════════════════════════════════════════════════════════════


class TestAsyncSafetyReview:
    """L3 safety: Thinker reviews Speaker output, injects correction next turn."""

    def test_slow_think_deps_has_speaker_output_field(self):
        """SlowThinkDeps should accept Speaker's output for review."""
        from backend.slow import SlowThinkDeps

        deps = SlowThinkDeps(
            session_id="s1",
            user_message="hi",
            speaker_output="Speaker 上轮说的话",
        )
        assert deps.speaker_output == "Speaker 上轮说的话"

    def test_slow_think_deps_speaker_output_defaults_empty(self):
        """speaker_output should default to empty string."""
        from backend.slow import SlowThinkDeps

        deps = SlowThinkDeps(session_id="s1", user_message="hi")
        assert deps.speaker_output == ""

    @pytest.mark.asyncio
    async def test_slow_safety_review_tool_exists(self):
        """Thinker should have a safety review tool."""
        from backend.slow import slow_agent

        tool_names = list(slow_agent._function_toolset.tools)
        assert "slow_safety_review" in tool_names

    @pytest.mark.asyncio
    async def test_slow_safety_review_injects_correction(self):
        """When Speaker output has issues, review should inject correction."""
        from backend.slow import SlowThinkDeps, slow_safety_review

        deps = SlowThinkDeps(
            session_id="s1",
            user_message="我很焦虑",
            speaker_output="你可能有焦虑症，建议去看医生。",
        )
        ctx = SimpleNamespace(deps=deps)

        result = await slow_safety_review(ctx)

        assert "correction" in result.lower()
        assert deps.carryover_inject
        assert deps.mutation_count_this_iter > 0

    @pytest.mark.asyncio
    async def test_slow_safety_review_no_issue_no_injection(self):
        """When Speaker output is fine, review should not inject anything."""
        from backend.slow import SlowThinkDeps, slow_safety_review

        deps = SlowThinkDeps(
            session_id="s1",
            user_message="我很焦虑",
            speaker_output="我听到你说很焦虑，能多说说是什么让你这样吗？",
        )
        ctx = SimpleNamespace(deps=deps)

        initial_inject_count = len(deps.carryover_inject)
        await slow_safety_review(ctx)

        assert len(deps.carryover_inject) == initial_inject_count
