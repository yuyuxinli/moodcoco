"""archive_manager.py functional tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Make script importable
_SCRIPTS_DIR = str(
    Path(__file__).resolve().parent.parent
    / "ai-companion"
    / "skills"
    / "farewell"
    / "scripts"
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import archive_manager  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_PEOPLE_CONTENT = """\
# 小凯

关系类型：恋人
认识时间：2024-06
首次提及：2024-06-15
当前状态：活跃

## 关系阶段
- 2024-06: 热恋期，"他好体贴"

## 退出信号
- 2025-01: 触发事件 "聊未来" → 用户反应 "不舒服" → 结果 "冷战"

## 我们之间的模式
- 每次吵架都是我先道歉
- 他提未来我就想逃

## 跨关系匹配
- 与小李的相似模式：退缩

## 关键事件
- 第一次旅行
"""

_DIARY_CONTENT = """\
# 2025-01-15

## 22:30 和小凯聊天

小凯又提到结婚的事了，我好烦。

> "我觉得不舒服"

**情绪**：焦虑
**强度**：7
"""


def _setup_workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create standard people/diary/memory dirs with test content."""
    people_dir = tmp_path / "people"
    diary_dir = tmp_path / "diary"
    memory_dir = tmp_path / "memory"
    people_dir.mkdir()
    diary_dir.mkdir()
    memory_dir.mkdir()

    (people_dir / "小凯.md").write_text(_PEOPLE_CONTENT, encoding="utf-8")
    (diary_dir / "2025-01-15.md").write_text(_DIARY_CONTENT, encoding="utf-8")
    (memory_dir / "pattern_log.md").write_text(
        "# Pattern Log\n\n## 小凯相关\n- 退缩模式\n", encoding="utf-8"
    )

    return people_dir, diary_dir, memory_dir


# ---------------------------------------------------------------------------
# extract_pattern_insights
# ---------------------------------------------------------------------------


def test_extract_pattern_insights(tmp_path: Path) -> None:
    """Extracts pattern insights and anonymizes name."""
    people_dir, _, _ = _setup_workspace(tmp_path)
    insights = archive_manager.extract_pattern_insights(str(people_dir / "小凯.md"))

    assert len(insights) >= 1
    # Check that name is anonymized
    for insight in insights:
        assert "小凯" not in insight["content"], (
            f"Name should be anonymized but found in: {insight['content']}"
        )
    # Check that pattern content is preserved
    contents = [i["content"] for i in insights]
    assert any("道歉" in c for c in contents)


def test_extract_pattern_insights_nonexistent() -> None:
    """Non-existent file -> returns empty list."""
    result = archive_manager.extract_pattern_insights("/nonexistent/file.md")
    assert result == []


# ---------------------------------------------------------------------------
# archive_person
# ---------------------------------------------------------------------------


def test_archive_creates_backup_and_modifies(tmp_path: Path) -> None:
    """archive_person() creates backup dir + marks people file as archived."""
    people_dir, diary_dir, memory_dir = _setup_workspace(tmp_path)

    result = archive_manager.archive_person(
        str(people_dir), str(diary_dir), str(memory_dir), "小凯"
    )

    assert result["status"] == "ok"
    assert result["action"] == "archive"
    assert len(result["files_affected"]) >= 1
    assert result["backup_path"] != ""

    # Verify backup dir exists
    backup_path = Path(result["backup_path"])
    assert backup_path.exists()
    assert (backup_path / "小凯.md").exists()

    # Verify people file is marked as archived
    archived_text = (people_dir / "小凯.md").read_text(encoding="utf-8")
    assert "当前状态：封存" in archived_text
    assert "已封存" in archived_text

    # Verify pattern insights were extracted
    assert len(result["pattern_insights"]) >= 1


def test_archive_already_archived(tmp_path: Path) -> None:
    """Archive already-archived person -> already_archived status."""
    people_dir, diary_dir, memory_dir = _setup_workspace(tmp_path)

    # Archive once
    archive_manager.archive_person(
        str(people_dir), str(diary_dir), str(memory_dir), "小凯"
    )

    # Archive again
    result = archive_manager.archive_person(
        str(people_dir), str(diary_dir), str(memory_dir), "小凯"
    )
    assert result["status"] == "already_archived"


def test_archive_not_found(tmp_path: Path) -> None:
    """Archive non-existent person -> not_found status."""
    people_dir = tmp_path / "people"
    people_dir.mkdir()

    result = archive_manager.archive_person(
        str(people_dir), str(tmp_path / "diary"), str(tmp_path / "memory"), "不存在"
    )
    assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# archive -> restore roundtrip (DEEP TEST)
# ---------------------------------------------------------------------------


def test_archive_restore_roundtrip(tmp_path: Path) -> None:
    """Archive -> restore -> files match original content. THIS IS THE DEEP TEST."""
    people_dir, diary_dir, memory_dir = _setup_workspace(tmp_path)

    # Capture original content
    original_people = (people_dir / "小凯.md").read_text(encoding="utf-8")
    original_diary = (diary_dir / "2025-01-15.md").read_text(encoding="utf-8")

    # Step 1: Archive
    archive_result = archive_manager.archive_person(
        str(people_dir), str(diary_dir), str(memory_dir), "小凯"
    )
    assert archive_result["status"] == "ok"

    # Verify files are modified (not same as original)
    archived_people = (people_dir / "小凯.md").read_text(encoding="utf-8")
    assert "当前状态：封存" in archived_people
    assert archived_people != original_people

    # Step 2: Restore
    restore_result = archive_manager.restore_person(
        str(people_dir), str(diary_dir), str(memory_dir), "小凯"
    )
    assert restore_result["status"] == "ok"
    assert len(restore_result["files_affected"]) >= 1

    # Step 3: Verify restored content matches original
    restored_people = (people_dir / "小凯.md").read_text(encoding="utf-8")
    assert restored_people == original_people, (
        "Restored people file should match original"
    )

    restored_diary = (diary_dir / "2025-01-15.md").read_text(encoding="utf-8")
    assert restored_diary == original_diary, (
        "Restored diary file should match original"
    )


def test_restore_not_found(tmp_path: Path) -> None:
    """Restore without prior archive -> not_found."""
    people_dir = tmp_path / "people"
    people_dir.mkdir()

    result = archive_manager.restore_person(
        str(people_dir), str(tmp_path / "diary"), str(tmp_path / "memory"), "不存在"
    )
    assert result["status"] == "not_found"
