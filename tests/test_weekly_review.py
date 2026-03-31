"""weekly_review.py integration tests — check-in parsing + basic analysis."""

from __future__ import annotations

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
# check-in parsing from memory/
# ---------------------------------------------------------------------------

_MEMORY_CHECKIN = """\
# {date}

## check-in

- time: 22:30
- emotion: 焦虑
- source: heartbeat
- note: 今天工作压力好大

## 日记摘要

随便写点什么。
"""


def _create_memory_files(
    memory_dir: Path, start: date, days: int, emotion: str = "焦虑"
) -> None:
    """Create memory files with check-in blocks for N consecutive days."""
    memory_dir.mkdir(parents=True, exist_ok=True)
    for i in range(days):
        d = start + timedelta(days=i)
        content = _MEMORY_CHECKIN.format(date=d.isoformat()).replace("焦虑", emotion)
        (memory_dir / f"{d.isoformat()}.md").write_text(content, encoding="utf-8")


def test_parse_checkins_from_memory(tmp_path: Path) -> None:
    """parse_checkins_from_memory extracts emotion + note from ## check-in blocks."""
    memory_dir = tmp_path / "memory"
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    _create_memory_files(memory_dir, monday, 3, emotion="焦虑")

    checkins = weekly_review.parse_checkins_from_memory(
        str(memory_dir), monday, sunday
    )

    assert len(checkins) == 3
    for ci in checkins:
        assert ci["emotion"] == "焦虑"
        assert ci["time"] == "22:30"
        assert "工作压力" in ci.get("note", "")


def test_parse_checkins_empty_dir(tmp_path: Path) -> None:
    """Empty memory dir returns empty list."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    checkins = weekly_review.parse_checkins_from_memory(
        str(memory_dir), monday, sunday
    )
    assert checkins == []


# ---------------------------------------------------------------------------
# analyze_week with memory-dir check-in data only (no diary)
# ---------------------------------------------------------------------------


def test_analyze_week_checkin_only(tmp_path: Path) -> None:
    """analyze_week works with check-in data when no diary files exist."""
    memory_dir = tmp_path / "memory"
    today = date.today()
    monday = today - timedelta(days=today.weekday())

    _create_memory_files(memory_dir, monday, 4, emotion="焦虑")

    result = weekly_review.analyze_week(
        diary_files=[],
        people_dir=None,
        memory_dir=str(memory_dir),
    )

    assert result["status"] == "ok"
    assert result["entries"] >= 4
    # Check-in emotions should be counted
    assert result["emotion_clusters"]["焦虑"] >= 4


def test_analyze_week_no_data(tmp_path: Path) -> None:
    """analyze_week with no diary and no memory returns ok with zero entries."""
    result = weekly_review.analyze_week(
        diary_files=[],
        people_dir=None,
        memory_dir=None,
    )

    assert result["status"] == "ok"
    assert result["entries"] == 0
