"""archive_manager.py functional tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Make script importable
_SCRIPTS_DIR = str(
    Path(__file__).resolve().parent.parent
    / "backend"
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
    assert len(result["insights"]) >= 1


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


# ---------------------------------------------------------------------------
# delete_person — pending_followup + time_capsules cleanup (P0 bug fix)
# ---------------------------------------------------------------------------

_PENDING_FOLLOWUP_CONTENT = """\
# Pending Followup

## 小凯冷战后续
- 类型：情绪跟进
- 人物：小凯
- 日期：2025-01-20

---

## 工作压力跟进
- 类型：日常关怀
- 日期：2025-01-22

---
"""

_TIME_CAPSULES_CONTENT = """\
# 时间胶囊

## capsule_20250115_220000

- 封存日期：2025-01-15
- 开启日期：2025-04-15
- 状态：sealed

> 希望小凯和我都能找到更好的自己

---

## capsule_20250120_100000

- 封存日期：2025-01-20
- 开启日期：2025-04-20
- 状态：sealed

> 希望三个月后工作顺利

---
"""


def test_delete_cleans_pending_followup(tmp_path: Path) -> None:
    """delete_person() removes person-related entries from pending_followup.md."""
    people_dir, diary_dir, memory_dir = _setup_workspace(tmp_path)
    (memory_dir / "pending_followup.md").write_text(
        _PENDING_FOLLOWUP_CONTENT, encoding="utf-8"
    )

    result = archive_manager.delete_person(
        str(people_dir), str(diary_dir), str(memory_dir), "小凯"
    )

    # pending_followup.md should still exist (has unrelated entries)
    pf = memory_dir / "pending_followup.md"
    assert pf.exists()
    pf_text = pf.read_text(encoding="utf-8")

    # 小凯-related section should be removed
    assert "小凯" not in pf_text, (
        "pending_followup.md should not contain 小凯 after delete"
    )
    # Unrelated entry should be preserved
    assert "工作压力跟进" in pf_text, (
        "Unrelated entries in pending_followup.md should be preserved"
    )
    # Should be listed in deleted_files
    assert any("pending_followup" in f for f in result["deleted_files"])


def test_delete_cleans_time_capsules(tmp_path: Path) -> None:
    """delete_person() removes person-related entries from time_capsules.md."""
    people_dir, diary_dir, memory_dir = _setup_workspace(tmp_path)
    (memory_dir / "time_capsules.md").write_text(
        _TIME_CAPSULES_CONTENT, encoding="utf-8"
    )

    result = archive_manager.delete_person(
        str(people_dir), str(diary_dir), str(memory_dir), "小凯"
    )

    tc = memory_dir / "time_capsules.md"
    assert tc.exists()
    tc_text = tc.read_text(encoding="utf-8")

    # 小凯-related capsule should be removed
    assert "小凯" not in tc_text, (
        "time_capsules.md should not contain 小凯 after delete"
    )
    # Unrelated capsule should be preserved
    assert "工作顺利" in tc_text, (
        "Unrelated capsules in time_capsules.md should be preserved"
    )
    assert any("time_capsules" in f for f in result["deleted_files"])


# ---------------------------------------------------------------------------
# Ritual paths: burn-belief + belief-write, time capsule
# ---------------------------------------------------------------------------


def test_archive_with_burn_belief_ritual(tmp_path: Path) -> None:
    """Archive via 'burn belief' ritual: insights extracted before body cleared."""
    people_dir, diary_dir, memory_dir = _setup_workspace(tmp_path)

    result = archive_manager.archive_person(
        str(people_dir), str(diary_dir), str(memory_dir), "小凯",
        ritual_type="standard",
    )

    assert result["status"] == "ok"
    assert result["action"] == "archive"

    # Insights must be non-empty (burn-belief = keep pattern, discard events)
    assert len(result["insights"]) >= 1

    # Body should be cleared — no event details remain
    archived_text = (people_dir / "小凯.md").read_text(encoding="utf-8")
    assert "当前状态：封存" in archived_text
    # The specific event content ("第一次旅行") should be gone from active file
    assert "第一次旅行" not in archived_text


def test_archive_belief_write_to_user_md(tmp_path: Path) -> None:
    """After archive, insights can be written to USER.md (belief-write step)."""
    people_dir, diary_dir, memory_dir = _setup_workspace(tmp_path)

    result = archive_manager.archive_person(
        str(people_dir), str(diary_dir), str(memory_dir), "小凯",
    )

    # Simulate the belief-write step: write insights to USER.md
    insights = result["insights"]
    assert len(insights) >= 1

    user_md = memory_dir / "USER.md"
    user_md.write_text(
        "# 用户画像\n\n## 模式级洞察\n\n"
        + "\n".join(f"- {i}" for i in insights)
        + "\n",
        encoding="utf-8",
    )

    text = user_md.read_text(encoding="utf-8")
    assert "模式级洞察" in text
    # Insights should be anonymized (no original name)
    assert "小凯" not in text


def test_time_capsule_creation(tmp_path: Path) -> None:
    """Time capsule creation writes sealed entry to time_capsules.md."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()

    result = archive_manager.create_time_capsule(
        str(memory_dir), "希望三个月后我已经释然了"
    )

    assert "capsule_id" in result
    assert "sealed_date" in result
    assert "open_date" in result

    # Capsule file should exist and contain the entry
    capsule_file = memory_dir / "time_capsules.md"
    assert capsule_file.exists()

    text = capsule_file.read_text(encoding="utf-8")
    assert result["capsule_id"] in text
    assert "状态：sealed" in text
    assert "希望三个月后我已经释然了" in text


def test_delete_basic_functionality(tmp_path: Path) -> None:
    """delete_person() removes people file, diary mentions, and memory files."""
    people_dir, diary_dir, memory_dir = _setup_workspace(tmp_path)

    result = archive_manager.delete_person(
        str(people_dir), str(diary_dir), str(memory_dir), "小凯"
    )

    # People file should be deleted
    assert not (people_dir / "小凯.md").exists()
    assert any("小凯.md" in f for f in result["deleted_files"])

    # Diary should be cleaned
    diary_text = (diary_dir / "2025-01-15.md").read_text(encoding="utf-8")
    assert "小凯" not in diary_text

    # Memory file should be deleted
    assert not (memory_dir / "pattern_log.md").exists()
