"""growth_tracker.py functional tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Make script importable
_SCRIPTS_DIR = str(
    Path(__file__).resolve().parent.parent
    / "backend"
    / "skills"
    / "diary"
    / "scripts"
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import growth_tracker  # noqa: E402


def _write_diary(tmp_path: Path, filename: str, content: str) -> None:
    """Helper to write a diary file with correct format."""
    diary_dir = tmp_path / "diary"
    diary_dir.mkdir(exist_ok=True)
    (diary_dir / filename).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# extract_growth_nodes — IM detection
# ---------------------------------------------------------------------------


def test_extract_growth_nodes_action(tmp_path: Path) -> None:
    """Diary with action IM marker -> detects action node."""
    _write_diary(
        tmp_path,
        "2025-03-15.md",
        """\
# 2025-03-15

## 22:30 和小凯聊天

他又提到未来的事。

> "第一次没有立刻发消息追问他"

**情绪**：平静
**强度**：3
""",
    )

    nodes = growth_tracker.extract_growth_nodes(str(tmp_path / "diary"))
    assert len(nodes) >= 1

    action_nodes = [n for n in nodes if n["im_type"] == "action"]
    assert len(action_nodes) >= 1
    assert action_nodes[0]["date"] == "2025-03-15"


def test_extract_growth_nodes_reflection(tmp_path: Path) -> None:
    """Diary with reflection IM marker -> detects reflection node."""
    _write_diary(
        tmp_path,
        "2025-03-20.md",
        """\
# 2025-03-20

## 21:00 睡前思考

今天想了想为什么每次都是这样。

> "我发现每次他不回消息我就会焦虑"

**情绪**：困惑
**强度**：5
""",
    )

    nodes = growth_tracker.extract_growth_nodes(str(tmp_path / "diary"))
    assert len(nodes) >= 1

    reflection_nodes = [n for n in nodes if n["im_type"] == "reflection"]
    assert len(reflection_nodes) >= 1


def test_extract_growth_nodes_empty_dir(tmp_path: Path) -> None:
    """Empty diary dir -> empty result."""
    diary_dir = tmp_path / "diary"
    diary_dir.mkdir()

    nodes = growth_tracker.extract_growth_nodes(str(diary_dir))
    assert nodes == []


def test_extract_growth_nodes_nonexistent_dir(tmp_path: Path) -> None:
    """Non-existent diary dir -> empty result."""
    nodes = growth_tracker.extract_growth_nodes(str(tmp_path / "no_such_dir"))
    assert nodes == []


# ---------------------------------------------------------------------------
# find_contrast_pairs
# ---------------------------------------------------------------------------


def test_find_contrast_pairs_reflection_growth(tmp_path: Path) -> None:
    """Early dismissal + later reflection -> returns contrast pair."""
    # Write an early dismissal diary entry
    _write_diary(
        tmp_path,
        "2025-01-10.md",
        """\
# 2025-01-10

## 23:00 晚上的事

算了，不管了，想那么多干嘛。

> "算了不想了"

**情绪**：烦躁
**强度**：6
""",
    )

    # Write a later reflection diary entry
    diary_dir = tmp_path / "diary"
    (diary_dir / "2025-03-20.md").write_text(
        """\
# 2025-03-20

## 21:00 反思

我想搞清楚为什么每次都这样。

> "我发现我每次都在逃避"

**情绪**：困惑
**强度**：4
""",
        encoding="utf-8",
    )

    nodes = growth_tracker.extract_growth_nodes(str(diary_dir))
    pairs = growth_tracker.find_contrast_pairs(nodes, str(diary_dir))

    # Should find at least one contrast pair
    reflection_pairs = [p for p in pairs if p["type"] == "reflection_growth"]
    assert len(reflection_pairs) >= 1
    assert reflection_pairs[0]["before"] is not None
    assert reflection_pairs[0]["after"] is not None
    assert reflection_pairs[0]["before"]["date"] < reflection_pairs[0]["after"]["date"]


def test_find_contrast_pairs_action_growth(tmp_path: Path) -> None:
    """Action node -> creates action_growth pair with before=None."""
    _write_diary(
        tmp_path,
        "2025-03-15.md",
        """\
# 2025-03-15

## 22:00 进步

这次我没有像以前那样追问。

> "我主动选择了不发消息"

**情绪**：平静
**强度**：3
""",
    )

    diary_dir = tmp_path / "diary"
    nodes = growth_tracker.extract_growth_nodes(str(diary_dir))
    pairs = growth_tracker.find_contrast_pairs(nodes, str(diary_dir))

    action_pairs = [p for p in pairs if p["type"] == "action_growth"]
    assert len(action_pairs) >= 1
    assert action_pairs[0]["before"] is None
    assert action_pairs[0]["after"] is not None


# ---------------------------------------------------------------------------
# format_for_conversation
# ---------------------------------------------------------------------------


def test_format_for_conversation_reflection() -> None:
    """Reflection growth pair -> formatted narrative text."""
    pair: growth_tracker.ContrastPair = {
        "type": "reflection_growth",
        "before": {"date": "2025-01-10", "text": "算了不想了", "quote": "算了不想了"},
        "after": {"date": "2025-03-20", "text": "我发现我在逃避", "quote": "我发现我在逃避"},
        "narrative": "test narrative",
    }
    text = growth_tracker.format_for_conversation(pair)
    assert "2025-01-10" in text
    assert "2025-03-20" in text
    assert "不同" in text


def test_format_for_conversation_action() -> None:
    """Action growth pair -> formatted text mentioning the action evidence."""
    pair: growth_tracker.ContrastPair = {
        "type": "action_growth",
        "before": None,
        "after": {"date": "2025-03-15", "text": "这次没有追问", "quote": ""},
        "narrative": "test",
    }
    text = growth_tracker.format_for_conversation(pair)
    assert "这次没有追问" in text
    assert "不一样" in text
