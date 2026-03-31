"""F10 旅程流转 — 深度功能校验 (pytest)

T-F10-01: cross_week_pattern 端到端检测
T-F10-02: 缓存写入 → 读取 → 8 周清理
T-F10-03: cross_week_pattern 模糊匹配路径
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

_SCRIPTS_DIR = str(
    Path(__file__).resolve().parent.parent
    / "ai-companion"
    / "skills"
    / "weekly-reflection"
    / "scripts"
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import weekly_review  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: create weekly cache file with given themes
# ---------------------------------------------------------------------------

def _write_cache(memory_dir: Path, week_label: str, themes: list[dict]) -> None:
    """Write a weekly cache file manually for test setup."""
    cache_dir = memory_dir / "weekly_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_data = {
        "week": week_label,
        "emotion_summary": [],
        "repeated_themes": themes,
        "person_mention_count": {},
        "emotion_clusters": {},
        "growth_signals": [],
    }
    (cache_dir / f"{week_label}.json").write_text(
        json.dumps(cache_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ===========================================================================
# T-F10-01: cross_week_pattern 端到端检测
# ===========================================================================


class TestCrossWeekPatternE2E:
    """Verify detect_cross_week_pattern() returns detected:True when
    previous and current week share a matching theme."""

    def test_exact_match_detected(self, tmp_path: Path) -> None:
        """Same emotion theme in both weeks → detected: True."""
        memory_dir = tmp_path / "memory"
        today = date.today()
        monday = today - timedelta(days=today.weekday())

        # Previous week cache
        last_monday = monday - timedelta(weeks=1)
        last_label = weekly_review.iso_week_label(last_monday)
        _write_cache(memory_dir, last_label, [
            {"type": "emotion", "word": "焦虑族", "count": 4},
        ])

        # Current week themes
        current_themes = [
            {"type": "emotion", "word": "焦虑族", "count": 3},
        ]

        from collections import Counter
        result = weekly_review.detect_cross_week_pattern(
            current_themes, Counter(), str(memory_dir), monday,
        )

        assert result["detected"] is True
        assert len(result["themes"]) >= 1
        matched = result["themes"][0]
        assert matched["current_week_count"] == 3
        assert matched["previous_week_count"] == 4
        assert matched["span_weeks"] >= 2

    def test_previous_themes_empty(self, tmp_path: Path) -> None:
        """Previous week cache exists but repeated_themes is empty → detected: False."""
        memory_dir = tmp_path / "memory"
        today = date.today()
        monday = today - timedelta(days=today.weekday())

        last_monday = monday - timedelta(weeks=1)
        last_label = weekly_review.iso_week_label(last_monday)
        _write_cache(memory_dir, last_label, [])  # empty themes

        current_themes = [
            {"type": "emotion", "word": "焦虑族", "count": 3},
        ]

        from collections import Counter
        result = weekly_review.detect_cross_week_pattern(
            current_themes, Counter(), str(memory_dir), monday,
        )

        assert result["detected"] is False
        assert result["themes"] == []

    def test_no_previous_cache(self, tmp_path: Path) -> None:
        """No previous week cache file → detected: False."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        today = date.today()
        monday = today - timedelta(days=today.weekday())

        current_themes = [
            {"type": "emotion", "word": "焦虑族", "count": 3},
        ]

        from collections import Counter
        result = weekly_review.detect_cross_week_pattern(
            current_themes, Counter(), str(memory_dir), monday,
        )

        assert result["detected"] is False
        assert result["themes"] == []

    def test_current_themes_empty(self, tmp_path: Path) -> None:
        """Current week themes empty → guard clause returns no_match immediately."""
        memory_dir = tmp_path / "memory"
        today = date.today()
        monday = today - timedelta(days=today.weekday())

        last_monday = monday - timedelta(weeks=1)
        last_label = weekly_review.iso_week_label(last_monday)
        _write_cache(memory_dir, last_label, [
            {"type": "emotion", "word": "焦虑族", "count": 4},
        ])

        from collections import Counter
        result = weekly_review.detect_cross_week_pattern(
            [], Counter(), str(memory_dir), monday,
        )

        assert result["detected"] is False
        assert result["themes"] == []


# ===========================================================================
# T-F10-02: 缓存写入 → 读取 → 8 周清理
# ===========================================================================


class TestWeeklyCacheLifecycle:
    """Verify write_weekly_cache, _load_weekly_cache, and _cleanup_old_caches."""

    def test_write_and_read_roundtrip(self, tmp_path: Path) -> None:
        """Written cache can be read back with identical repeated_themes."""
        memory_dir = tmp_path / "memory"
        analysis = {
            "emotion_summary": [{"emotion": "焦虑", "day": "2026-03-25"}],
            "repeated_themes": [
                {"type": "emotion", "word": "焦虑族", "count": 4},
                {"type": "trigger", "word": "不回消息", "count": 2},
            ],
            "person_mention_count": {"小凯": 3},
            "emotion_clusters": {"焦虑": 4},
            "growth_signals": [],
        }

        week_label = "2026-W13"
        weekly_review.write_weekly_cache(str(memory_dir), week_label, analysis)

        loaded = weekly_review._load_weekly_cache(str(memory_dir), week_label)
        assert loaded is not None
        assert loaded["week"] == week_label
        assert loaded["repeated_themes"] == analysis["repeated_themes"]
        assert loaded["emotion_summary"] == analysis["emotion_summary"]

    def test_cleanup_keeps_only_8_weeks(self, tmp_path: Path) -> None:
        """Writing 9 weeks of cache → oldest is deleted, 8 remain."""
        memory_dir = tmp_path / "memory"
        base_monday = date(2026, 1, 5)  # A Monday

        for i in range(9):
            week_monday = base_monday + timedelta(weeks=i)
            label = weekly_review.iso_week_label(week_monday)
            analysis = {
                "repeated_themes": [{"type": "emotion", "word": f"theme-{i}", "count": i}],
            }
            weekly_review.write_weekly_cache(str(memory_dir), label, analysis)

        cache_dir = memory_dir / "weekly_cache"
        remaining_files = sorted(cache_dir.glob("*.json"))
        assert len(remaining_files) == 8

        # Oldest (W02 of 2026, first week) should be gone
        oldest_label = weekly_review.iso_week_label(base_monday)
        assert not (cache_dir / f"{oldest_label}.json").exists()

        # Newest should still exist
        newest_label = weekly_review.iso_week_label(base_monday + timedelta(weeks=8))
        assert (cache_dir / f"{newest_label}.json").exists()

    def test_load_nonexistent_cache(self, tmp_path: Path) -> None:
        """Loading a non-existent cache returns None."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        result = weekly_review._load_weekly_cache(str(memory_dir), "2026-W99")
        assert result is None

    def test_load_corrupt_json(self, tmp_path: Path) -> None:
        """Loading a corrupt JSON file returns None (not crash)."""
        memory_dir = tmp_path / "memory"
        cache_dir = memory_dir / "weekly_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "2026-W13.json").write_text("not valid json{{{", encoding="utf-8")

        result = weekly_review._load_weekly_cache(str(memory_dir), "2026-W13")
        assert result is None


# ===========================================================================
# T-F10-03: cross_week_pattern 模糊匹配路径
# ===========================================================================


class TestFuzzyMatchPath:
    """Verify _fuzzy_match_theme and its integration in detect_cross_week_pattern."""

    def test_fuzzy_match_partial_overlap(self, tmp_path: Path) -> None:
        """Trigger themes with ~66% word overlap → fuzzy match succeeds → detected: True."""
        memory_dir = tmp_path / "memory"
        today = date.today()
        monday = today - timedelta(days=today.weekday())

        last_monday = monday - timedelta(weeks=1)
        last_label = weekly_review.iso_week_label(last_monday)
        _write_cache(memory_dir, last_label, [
            {"type": "trigger", "word": "不回消息怀疑自己", "count": 2},
        ])

        current_themes = [
            {"type": "trigger", "word": "不回消息", "count": 3},
        ]

        from collections import Counter
        result = weekly_review.detect_cross_week_pattern(
            current_themes, Counter(), str(memory_dir), monday,
        )

        assert result["detected"] is True
        assert len(result["themes"]) >= 1

    def test_different_type_no_match(self, tmp_path: Path) -> None:
        """Different type (trigger vs emotion) → no fuzzy match → detected: False."""
        memory_dir = tmp_path / "memory"
        today = date.today()
        monday = today - timedelta(days=today.weekday())

        last_monday = monday - timedelta(weeks=1)
        last_label = weekly_review.iso_week_label(last_monday)
        _write_cache(memory_dir, last_label, [
            {"type": "trigger", "word": "分手冲动", "count": 2},
        ])

        current_themes = [
            {"type": "emotion", "word": "焦虑族", "count": 3},
        ]

        from collections import Counter
        result = weekly_review.detect_cross_week_pattern(
            current_themes, Counter(), str(memory_dir), monday,
        )

        assert result["detected"] is False
        assert result["themes"] == []

    def test_fuzzy_match_function_directly(self) -> None:
        """Direct test of _fuzzy_match_theme with overlapping Chinese tokens."""
        current = {"type": "trigger", "word": "不回消息"}
        previous_themes = [
            {"type": "trigger", "word": "不回消息怀疑自己"},
        ]

        match = weekly_review._fuzzy_match_theme(current, previous_themes)
        assert match is not None

    def test_fuzzy_match_below_threshold(self) -> None:
        """Completely different words → no fuzzy match (< 50% overlap)."""
        current = {"type": "trigger", "word": "工作压力"}
        previous_themes = [
            {"type": "trigger", "word": "不回消息怀疑自己"},
        ]

        match = weekly_review._fuzzy_match_theme(current, previous_themes)
        assert match is None
