"""
pattern_engine.py — 跨关系模式匹配引擎

读取所有 people/*.md，提取退出信号和关系阶段，
跨文件匹配相似模式。

设计参考：docs/technical/technical-design.md §5.2
只用 Python 标准库（re, pathlib, datetime）。

用法（由 AI agent 在对话中通过 exec 调用）：
    python3 ai-companion/skills/diary/scripts/pattern_engine.py <people_dir> [current_event]

    无参数：输出所有跨关系模式
    有 current_event：输出当前事件与历史的匹配结果
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import TypedDict

# ---------------------------------------------------------------------------
# Type Definitions
# ---------------------------------------------------------------------------


class StageEntry(TypedDict):
    date: str
    stage: str
    user_words: str
    raw: str


class ExitSignal(TypedDict):
    date: str
    trigger: str
    reaction: str
    outcome: str
    raw: str


class PersonData(TypedDict):
    name: str
    file: str
    relationship_type: str
    current_status: str
    stages: list[StageEntry]
    exit_signals: list[ExitSignal]
    patterns: list[str]
    cross_matches: list[str]
    key_events: list[str]


class CrossPattern(TypedDict):
    dimension: str
    description: str
    people: list[str]
    details: list[str]


class HistoryMatch(TypedDict):
    person: str
    date: str
    trigger: str
    reaction: str
    matching_keywords: list[str]


# ---------------------------------------------------------------------------
# Markdown Parsing
# ---------------------------------------------------------------------------


def parse_people_file(filepath: str) -> PersonData | None:
    """解析单个 people/*.md 文件，提取结构化数据。"""
    path = Path(filepath)
    if not path.exists():
        return None

    text = path.read_text(encoding="utf-8")
    name = path.stem

    result: PersonData = {
        "name": name,
        "file": str(path),
        "relationship_type": "",
        "current_status": "",
        "stages": [],
        "exit_signals": [],
        "patterns": [],
        "cross_matches": [],
        "key_events": [],
    }

    # Parse header fields
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("关系类型："):
            result["relationship_type"] = line.split("：", 1)[1].strip()
        elif line.startswith("当前状态："):
            result["current_status"] = line.split("：", 1)[1].strip()

    # Parse sections
    current_section = ""
    for line in text.split("\n"):
        stripped = line.strip()

        # Detect section headers
        if stripped.startswith("## 关系阶段"):
            current_section = "stages"
            continue
        if stripped.startswith("## 退出信号"):
            current_section = "exit_signals"
            continue
        if stripped.startswith("## 我们之间的模式"):
            current_section = "patterns"
            continue
        if stripped.startswith("## 跨关系匹配"):
            current_section = "cross_matches"
            continue
        if stripped.startswith("## 关键事件"):
            current_section = "key_events"
            continue
        if stripped.startswith("## "):
            current_section = ""
            continue

        # Skip comments and empty lines
        if stripped.startswith("<!--") or stripped == "" or stripped.startswith("#"):
            continue

        # Parse list items in each section
        if stripped.startswith("- ") and current_section:
            entry = stripped[2:].strip()
            if current_section == "stages":
                result["stages"].append(_parse_stage_entry(entry))
            elif current_section == "exit_signals":
                result["exit_signals"].append(_parse_exit_signal(entry))
            elif current_section == "key_events":
                result["key_events"].append(entry)
            elif current_section == "patterns":
                result["patterns"].append(entry)
            elif current_section == "cross_matches":
                result["cross_matches"].append(entry)

    return result


def _parse_stage_entry(entry: str) -> StageEntry:
    """解析关系阶段条目：'2026-01: 热恋期，"他好体贴"'"""
    match = re.match(r"(\d{4}-\d{2}(?:-\d{2})?)\s*[:：]\s*(.+)", entry)
    if match:
        date_str = match.group(1)
        rest = match.group(2)
        # Extract quoted user words if present
        quote_match = re.search(r'[""「](.+?)[""」]', rest)
        stage = re.split(r"[,，]", rest)[0].strip()
        return {
            "date": date_str,
            "stage": stage,
            "user_words": quote_match.group(1) if quote_match else "",
            "raw": entry,
        }
    return {"date": "", "stage": entry, "user_words": "", "raw": entry}


def _parse_exit_signal(entry: str) -> ExitSignal:
    """解析退出信号条目：
    '2026-03: 触发事件 "对方聊未来" → 用户反应 "我觉得不舒服" → 结果 "冷静了"'
    """
    result: ExitSignal = {
        "date": "",
        "trigger": "",
        "reaction": "",
        "outcome": "",
        "raw": entry,
    }

    date_match = re.match(r"(\d{4}-\d{2}(?:-\d{2})?)\s*[:：]\s*", entry)
    if date_match:
        result["date"] = date_match.group(1)
        entry = entry[date_match.end() :]

    # Extract trigger, reaction, outcome from arrow-separated format
    parts = re.split(r"\s*→\s*", entry)
    for part in parts:
        part = part.strip()
        if part.startswith("触发事件"):
            quote = re.search(r'[""「](.+?)[""」]', part)
            result["trigger"] = (
                quote.group(1) if quote else part.replace("触发事件", "").strip()
            )
        elif part.startswith("用户反应"):
            quote = re.search(r'[""「](.+?)[""」]', part)
            result["reaction"] = (
                quote.group(1) if quote else part.replace("用户反应", "").strip()
            )
        elif part.startswith("结果"):
            quote = re.search(r'[""「](.+?)[""」]', part)
            result["outcome"] = (
                quote.group(1) if quote else part.replace("结果", "").strip()
            )

    return result


# ---------------------------------------------------------------------------
# Cross-Relationship Pattern Matching
# ---------------------------------------------------------------------------

MATCH_DIMENSIONS: list[str] = ["timing", "trigger", "reaction", "outcome"]


def parse_people_files(people_dir: str) -> list[PersonData]:
    """解析 people/ 目录下所有 .md 文件，返回结构化数据列表。

    这是 parse_people_file() 的批量包装，供外部调用使用。
    """
    result: list[PersonData] = []
    path = Path(people_dir)
    if not path.exists():
        return result
    for f in sorted(path.glob("*.md")):
        data = parse_people_file(str(f))
        if data is not None:
            result.append(data)
    return result


def update_cross_patterns(people_dir: str, patterns: list[CrossPattern]) -> None:
    """将发现的跨关系模式写回 people/*.md 的"跨关系匹配"段。

    对每个涉及的 people file，更新其 ## 跨关系匹配 段落。
    """
    path = Path(people_dir)
    if not path.exists():
        return

    # Group patterns by person
    person_patterns: dict[str, list[CrossPattern]] = {}
    for p in patterns:
        for name in p.get("people", []):
            if name not in person_patterns:
                person_patterns[name] = []
            person_patterns[name].append(p)

    for name, pats in person_patterns.items():
        filepath = path / f"{name}.md"
        if not filepath.exists():
            continue

        text = filepath.read_text(encoding="utf-8")
        lines = text.split("\n")
        new_lines: list[str] = []
        in_cross_section = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## 跨关系匹配"):
                in_cross_section = True
                new_lines.append(line)
                new_lines.append(
                    "<!-- 由 pattern_engine.py 自动写入，diary skill 不手动编辑此段 -->"
                )
                for pat in pats:
                    other_people = [n for n in pat["people"] if n != name]
                    others = "、".join(other_people)
                    new_lines.append(f"- 与 {others} 的相似模式：{pat['description']}")
                continue
            if in_cross_section:
                if stripped.startswith("## "):
                    # New section starts — end of cross section
                    in_cross_section = False
                    new_lines.append("")
                    new_lines.append(line)
                # Skip old cross-match content (list items, comments, empty lines)
                continue
            new_lines.append(line)

        filepath.write_text("\n".join(new_lines), encoding="utf-8")


def find_cross_patterns(people_data: list[PersonData]) -> list[CrossPattern]:
    """跨文件匹配相似模式。

    匹配维度：
    - timing: 多段关系在相似时间节点出现退出信号
    - trigger: 多段关系被相似事件触发
    - reaction: 用户在不同关系中做出相似反应

    至少 2 段关系有相似模式才报告。
    """
    patterns: list[CrossPattern] = []

    # Filter to people with exit signals
    with_signals = [p for p in people_data if p.get("exit_signals")]
    if len(with_signals) < 2:
        return patterns

    # --- Timing patterns ---
    # Extract month-in-relationship for each exit signal
    timing_groups: dict[int, list[tuple[str, ExitSignal]]] = {}
    for person in with_signals:
        stages = person.get("stages", [])
        if not stages:
            continue
        first_stage_date: str = stages[0].get("date", "")
        if not first_stage_date:
            continue

        for signal in person["exit_signals"]:
            if not signal.get("date"):
                continue
            months = _months_between(first_stage_date, signal["date"])
            if months is not None:
                bucket: int = months  # exact month
                if bucket not in timing_groups:
                    timing_groups[bucket] = []
                timing_groups[bucket].append((person["name"], signal))

    for month, entries in timing_groups.items():
        # 按去重后的关系数计，避免同一人多条信号被算成"跨关系"
        unique_people = list({e[0] for e in entries})
        if len(unique_people) >= 2:
            # 每个人只取最近一条信号
            seen: set[str] = set()
            deduped: list[tuple[str, ExitSignal]] = []
            for name, sig in entries:
                if name not in seen:
                    seen.add(name)
                    deduped.append((name, sig))
            patterns.append(
                {
                    "dimension": "timing",
                    "description": f"第 {month} 个月出现退出信号",
                    "people": unique_people,
                    "details": [
                        f'{name}: "{sig["reaction"]}"' for name, sig in deduped
                    ],
                }
            )

    # --- Trigger patterns ---
    # Group exit signals by trigger keywords
    trigger_keywords: dict[str, list[tuple[str, ExitSignal]]] = {}
    for person in with_signals:
        for signal in person["exit_signals"]:
            trigger_text: str = signal.get("trigger", "").lower()
            if not trigger_text:
                continue
            # Simple keyword extraction
            for keyword in _extract_keywords(trigger_text):
                if keyword not in trigger_keywords:
                    trigger_keywords[keyword] = []
                trigger_keywords[keyword].append((person["name"], signal))

    for keyword, entries in trigger_keywords.items():
        unique_people = list({e[0] for e in entries})
        if len(unique_people) >= 2:
            patterns.append(
                {
                    "dimension": "trigger",
                    "description": f"被「{keyword}」相关事件触发退出",
                    "people": unique_people,
                    "details": [f'{name}: "{sig["trigger"]}"' for name, sig in entries],
                }
            )

    # --- Reaction patterns ---
    reaction_keywords: dict[str, list[tuple[str, ExitSignal]]] = {}
    for person in with_signals:
        for signal in person["exit_signals"]:
            reaction_text: str = signal.get("reaction", "").lower()
            if not reaction_text:
                continue
            for keyword in _extract_keywords(reaction_text):
                if keyword not in reaction_keywords:
                    reaction_keywords[keyword] = []
                reaction_keywords[keyword].append((person["name"], signal))

    for keyword, entries in reaction_keywords.items():
        unique_people = list({e[0] for e in entries})
        if len(unique_people) >= 2:
            patterns.append(
                {
                    "dimension": "reaction",
                    "description": f"相似反应：「{keyword}」",
                    "people": unique_people,
                    "details": [
                        f'{name}: "{sig["reaction"]}"' for name, sig in entries
                    ],
                }
            )

    # --- Outcome patterns ---
    outcome_keywords: dict[str, list[tuple[str, ExitSignal]]] = {}
    for person in with_signals:
        for signal in person["exit_signals"]:
            outcome_text: str = signal.get("outcome", "").lower()
            if not outcome_text:
                continue
            for keyword in _extract_outcome_keywords(outcome_text):
                if keyword not in outcome_keywords:
                    outcome_keywords[keyword] = []
                outcome_keywords[keyword].append((person["name"], signal))

    for keyword, entries in outcome_keywords.items():
        unique_people = list({e[0] for e in entries})
        if len(unique_people) >= 2:
            patterns.append(
                {
                    "dimension": "outcome",
                    "description": f"相似结果：「{keyword}」",
                    "people": unique_people,
                    "details": [f'{name}: "{sig["outcome"]}"' for name, sig in entries],
                }
            )

    return patterns


def match_current_to_history(
    current_event: str,
    people_data: list[PersonData],
) -> list[HistoryMatch]:
    """当前事件与历史退出信号的匹配。

    返回匹配到的历史事件列表，供 AI 在对话中引用。
    """
    matches: list[HistoryMatch] = []
    current_keywords = set(_extract_keywords(current_event.lower()))

    for person in people_data:
        for signal in person.get("exit_signals", []):
            trigger_kws = set(_extract_keywords(signal.get("trigger", "").lower()))
            reaction_kws = set(_extract_keywords(signal.get("reaction", "").lower()))
            all_signal_keywords = trigger_kws | reaction_kws

            overlap = current_keywords & all_signal_keywords
            if overlap:
                matches.append(
                    {
                        "person": person["name"],
                        "date": signal.get("date", ""),
                        "trigger": signal.get("trigger", ""),
                        "reaction": signal.get("reaction", ""),
                        "matching_keywords": list(overlap),
                    }
                )

    return matches


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _months_between(start_date: str, end_date: str) -> int | None:
    """计算两个日期之间的月数（粗略）。"""
    try:
        start_fmt = "%Y-%m-%d" if len(start_date) > 7 else "%Y-%m"
        start = datetime.strptime(start_date, start_fmt)
        end_fmt = "%Y-%m-%d" if len(end_date) > 7 else "%Y-%m"
        end = datetime.strptime(end_date, end_fmt)
        return (end.year - start.year) * 12 + (end.month - start.month)
    except (ValueError, TypeError):
        return None


# Chinese relationship-related keywords for matching
# 对齐 diary SKILL.md 的退出信号检测关键词 + 扩展覆盖
_KEYWORD_PATTERNS: list[str] = [
    # 分手意图（diary SKILL.md 定义）
    "分手",
    "不想继续",
    "结束",
    "我们结束吧",
    # 退缩冲动（diary SKILL.md 定义）
    "想跑",
    "退缩",
    "不对",
    "不是对的人",
    "退后一步",
    # 持续不满（diary SKILL.md 定义）
    "差一点",
    "不满足",
    "缺了什么",
    "觉得差",
    # 热情衰减感知（diary SKILL.md 定义）
    "没那么喜欢",
    "热情",
    "追我",
    "不行了",
    "变了",
    "冷淡",
    # 关系事件触发
    "未来",
    "承诺",
    "结婚",
    "搬家",
    "见家长",
    "同居",
    # 情绪状态
    "不舒服",
    "不安",
    "焦虑",
    "害怕",
    "安全感",
    "恐惧",
    "逃避",
    "窒息",
    "压力",
    "透不过气",
    # 沟通问题
    "冷战",
    "吵架",
    "已读不回",
    "不回消息",
    "忽视",
    "不在乎",
    "不理我",
    "敷衍",
    # 关系动态
    "控制",
    "自由",
    "空间",
    "依赖",
    "粘人",
    "独立",
    "付出",
    "不对等",
    "单方面",
    # 自我怀疑
    "我的问题",
    "太敏感",
    "太作",
    "不够好",
    "配不上",
]


def _extract_keywords(text: str) -> list[str]:
    """从文本中提取关系相关关键词。"""
    found: list[str] = []
    for kw in _KEYWORD_PATTERNS:
        if kw in text:
            found.append(kw)
    return found


# Outcome-specific keywords for cross-relationship result matching
_OUTCOME_KEYWORDS: list[str] = [
    "分手",
    "冷战",
    "和好",
    "复合",
    "断联",
    "删除",
    "结束",
    "挽回",
    "道歉",
    "原谅",
    "冷淡",
    "疏远",
]


def _extract_outcome_keywords(text: str) -> list[str]:
    """从结果文本中提取结局相关关键词。"""
    found: list[str] = []
    for kw in _OUTCOME_KEYWORDS:
        if kw in text:
            found.append(kw)
    return found


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: pattern_engine.py <people_dir> [current_event]")
        sys.exit(1)

    people_dir = Path(sys.argv[1])
    current_event: str | None = sys.argv[2] if len(sys.argv) > 2 else None

    # Parse all people files
    people_data = parse_people_files(str(people_dir))

    if current_event:
        # Match current event to history
        matches = match_current_to_history(current_event, people_data)
        print(json.dumps(matches, ensure_ascii=False, indent=2))
    else:
        # Find all cross-relationship patterns
        patterns = find_cross_patterns(people_data)
        print(json.dumps(patterns, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
