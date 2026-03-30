"""pattern_engine.py functional tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Make script importable
_SCRIPTS_DIR = str(
    Path(__file__).resolve().parent.parent
    / "ai-companion"
    / "skills"
    / "diary"
    / "scripts"
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import pattern_engine  # noqa: E402


# ---------------------------------------------------------------------------
# parse_people_file
# ---------------------------------------------------------------------------


def test_parse_people_file_positive(tmp_path: Path) -> None:
    """Well-formed people/*.md -> correct PersonData fields."""
    md = tmp_path / "小凯.md"
    md.write_text(
        """\
# 小凯

关系类型：恋人
当前状态：活跃

## 关系阶段
- 2025-01: 热恋期，"他好体贴"
- 2025-06: 磨合期，"开始吵架了"

## 退出信号
- 2025-08: 触发事件 "对方聊未来" → 用户反应 "我觉得不舒服" → 结果 "冷战了一周"

## 我们之间的模式
- 每次吵架都是我先道歉

## 跨关系匹配
- 与小李的相似模式：退缩

## 关键事件
- 第一次一起旅行
""",
        encoding="utf-8",
    )

    data = pattern_engine.parse_people_file(str(md))
    assert data is not None
    assert data["name"] == "小凯"
    assert data["relationship_type"] == "恋人"
    assert data["current_status"] == "活跃"
    assert len(data["stages"]) == 2
    assert data["stages"][0]["stage"] == "热恋期"
    assert data["stages"][0]["user_words"] == "他好体贴"
    assert len(data["exit_signals"]) == 1
    assert data["exit_signals"][0]["trigger"] == "对方聊未来"
    assert data["exit_signals"][0]["reaction"] == "我觉得不舒服"
    assert data["exit_signals"][0]["outcome"] == "冷战了一周"
    assert len(data["patterns"]) == 1
    assert len(data["cross_matches"]) == 1
    assert len(data["key_events"]) == 1


def test_parse_people_file_nonexistent() -> None:
    """Non-existent file -> returns None."""
    result = pattern_engine.parse_people_file("/nonexistent/path.md")
    assert result is None


def test_parse_people_file_malformed(tmp_path: Path) -> None:
    """Malformed input (no sections, random text) -> returns PersonData with empty lists."""
    md = tmp_path / "乱码.md"
    md.write_text("这只是一段普通文字\n没有任何结构\n", encoding="utf-8")

    data = pattern_engine.parse_people_file(str(md))
    assert data is not None
    assert data["name"] == "乱码"
    assert data["stages"] == []
    assert data["exit_signals"] == []
    assert data["patterns"] == []


# ---------------------------------------------------------------------------
# find_cross_patterns
# ---------------------------------------------------------------------------


def _make_person(
    name: str,
    trigger: str = "未来",
    reaction: str = "不舒服",
    outcome: str = "冷战",
    stage_date: str = "2025-01",
    signal_date: str = "2025-03",
) -> pattern_engine.PersonData:
    """Helper to build a PersonData dict with one exit signal."""
    return {
        "name": name,
        "file": f"people/{name}.md",
        "relationship_type": "恋人",
        "current_status": "活跃",
        "stages": [{"date": stage_date, "stage": "热恋期", "user_words": "", "raw": ""}],
        "exit_signals": [
            {
                "date": signal_date,
                "trigger": trigger,
                "reaction": reaction,
                "outcome": outcome,
                "raw": "",
            }
        ],
        "patterns": [],
        "cross_matches": [],
        "key_events": [],
    }


def test_cross_patterns_two_people_matching_trigger() -> None:
    """2 people with matching trigger keyword -> returns CrossPattern."""
    people = [
        _make_person("小凯", trigger="聊未来", reaction="不舒服", outcome="冷战"),
        _make_person("小李", trigger="谈未来规划", reaction="焦虑", outcome="冷战了"),
    ]
    patterns = pattern_engine.find_cross_patterns(people)
    assert len(patterns) > 0

    # At least one pattern should involve both people
    people_in_patterns = set()
    for p in patterns:
        for name in p["people"]:
            people_in_patterns.add(name)
    assert "小凯" in people_in_patterns
    assert "小李" in people_in_patterns


def test_cross_patterns_less_than_two_people() -> None:
    """<2 people with signals -> returns empty list."""
    people = [_make_person("小凯")]
    patterns = pattern_engine.find_cross_patterns(people)
    assert patterns == []


def test_cross_patterns_no_signals() -> None:
    """People without exit signals -> returns empty list."""
    person_no_signals: pattern_engine.PersonData = {
        "name": "小凯",
        "file": "people/小凯.md",
        "relationship_type": "恋人",
        "current_status": "活跃",
        "stages": [],
        "exit_signals": [],
        "patterns": [],
        "cross_matches": [],
        "key_events": [],
    }
    patterns = pattern_engine.find_cross_patterns([person_no_signals, person_no_signals])
    assert patterns == []


# ---------------------------------------------------------------------------
# match_current_to_history
# ---------------------------------------------------------------------------


def test_match_current_to_history() -> None:
    """Current event with matching keyword -> returns history match."""
    people = [_make_person("小凯", trigger="聊未来", reaction="不舒服")]
    matches = pattern_engine.match_current_to_history("他又聊未来了", people)
    assert len(matches) >= 1
    assert matches[0]["person"] == "小凯"
    assert "未来" in matches[0]["matching_keywords"]


def test_match_current_to_history_no_match() -> None:
    """Current event with no matching keywords -> returns empty."""
    people = [_make_person("小凯", trigger="聊未来", reaction="不舒服")]
    matches = pattern_engine.match_current_to_history("今天天气不错", people)
    assert matches == []
