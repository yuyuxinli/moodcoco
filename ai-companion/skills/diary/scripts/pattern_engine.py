"""
pattern_engine.py — 跨关系模式匹配引擎

读取所有 people/*.md，提取退出信号和关系阶段，
跨文件匹配相似模式。

设计参考：docs/technical-design.md §5.2
只用 Python 标准库（re, pathlib, datetime）。

用法（由 AI agent 在对话中通过 exec 调用）：
    python3 ai-companion/skills/diary/scripts/pattern_engine.py <people_dir> [current_event]

    无参数：输出所有跨关系模式
    有 current_event：输出当前事件与历史的匹配结果
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Markdown Parsing
# ---------------------------------------------------------------------------

def parse_people_file(filepath: str) -> dict:
    """解析单个 people/*.md 文件，提取结构化数据。"""
    path = Path(filepath)
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    name = path.stem

    result = {
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
        elif stripped.startswith("## 退出信号"):
            current_section = "exit_signals"
            continue
        elif stripped.startswith("## 我们之间的模式"):
            current_section = "patterns"
            continue
        elif stripped.startswith("## 跨关系匹配"):
            current_section = "cross_matches"
            continue
        elif stripped.startswith("## 关键事件"):
            current_section = "key_events"
            continue
        elif stripped.startswith("## "):
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


def _parse_stage_entry(entry: str) -> dict:
    """解析关系阶段条目：'2026-01: 热恋期，"他好体贴"'"""
    match = re.match(r"(\d{4}-\d{2}(?:-\d{2})?)\s*[:：]\s*(.+)", entry)
    if match:
        date_str = match.group(1)
        rest = match.group(2)
        # Extract quoted user words if present
        quote_match = re.search(r'[""「](.+?)[""」]', rest)
        stage = re.split(r'[,，]', rest)[0].strip()
        return {
            "date": date_str,
            "stage": stage,
            "user_words": quote_match.group(1) if quote_match else "",
            "raw": entry,
        }
    return {"date": "", "stage": entry, "user_words": "", "raw": entry}


def _parse_exit_signal(entry: str) -> dict:
    """解析退出信号条目：
    '2026-03: 触发事件 "对方聊未来" → 用户反应 "我觉得不舒服" → 结果 "冷静了"'
    """
    result = {"date": "", "trigger": "", "reaction": "", "outcome": "", "raw": entry}

    date_match = re.match(r"(\d{4}-\d{2}(?:-\d{2})?)\s*[:：]\s*", entry)
    if date_match:
        result["date"] = date_match.group(1)
        entry = entry[date_match.end():]

    # Extract trigger, reaction, outcome from arrow-separated format
    parts = re.split(r"\s*→\s*", entry)
    for part in parts:
        part = part.strip()
        if part.startswith("触发事件"):
            quote = re.search(r'[""「](.+?)[""」]', part)
            result["trigger"] = quote.group(1) if quote else part.replace("触发事件", "").strip()
        elif part.startswith("用户反应"):
            quote = re.search(r'[""「](.+?)[""」]', part)
            result["reaction"] = quote.group(1) if quote else part.replace("用户反应", "").strip()
        elif part.startswith("结果"):
            quote = re.search(r'[""「](.+?)[""」]', part)
            result["outcome"] = quote.group(1) if quote else part.replace("结果", "").strip()

    return result


# ---------------------------------------------------------------------------
# Cross-Relationship Pattern Matching
# ---------------------------------------------------------------------------

MATCH_DIMENSIONS = ["timing", "trigger", "reaction"]


def find_cross_patterns(people_data: list) -> list:
    """跨文件匹配相似模式。

    匹配维度：
    - timing: 多段关系在相似时间节点出现退出信号
    - trigger: 多段关系被相似事件触发
    - reaction: 用户在不同关系中做出相似反应

    至少 2 段关系有相似模式才报告。
    """
    patterns = []

    # Filter to people with exit signals
    with_signals = [p for p in people_data if p.get("exit_signals")]
    if len(with_signals) < 2:
        return patterns

    # --- Timing patterns ---
    # Extract month-in-relationship for each exit signal
    timing_groups = {}  # month -> [(name, signal)]
    for person in with_signals:
        stages = person.get("stages", [])
        if not stages:
            continue
        first_stage_date = stages[0].get("date", "")
        if not first_stage_date:
            continue

        for signal in person["exit_signals"]:
            if not signal.get("date"):
                continue
            months = _months_between(first_stage_date, signal["date"])
            if months is not None:
                bucket = months  # exact month
                if bucket not in timing_groups:
                    timing_groups[bucket] = []
                timing_groups[bucket].append((person["name"], signal))

    for month, entries in timing_groups.items():
        if len(entries) >= 2:
            names = [e[0] for e in entries]
            patterns.append({
                "dimension": "timing",
                "description": f"第 {month} 个月出现退出信号",
                "people": names,
                "details": [
                    f"{name}: \"{sig['reaction']}\"" for name, sig in entries
                ],
            })

    # --- Trigger patterns ---
    # Group exit signals by trigger keywords
    trigger_keywords = {}
    for person in with_signals:
        for signal in person["exit_signals"]:
            trigger = signal.get("trigger", "").lower()
            if not trigger:
                continue
            # Simple keyword extraction
            for keyword in _extract_keywords(trigger):
                if keyword not in trigger_keywords:
                    trigger_keywords[keyword] = []
                trigger_keywords[keyword].append((person["name"], signal))

    for keyword, entries in trigger_keywords.items():
        unique_people = list(set(e[0] for e in entries))
        if len(unique_people) >= 2:
            patterns.append({
                "dimension": "trigger",
                "description": f"被「{keyword}」相关事件触发退出",
                "people": unique_people,
                "details": [
                    f"{name}: \"{sig['trigger']}\"" for name, sig in entries
                ],
            })

    # --- Reaction patterns ---
    reaction_keywords = {}
    for person in with_signals:
        for signal in person["exit_signals"]:
            reaction = signal.get("reaction", "").lower()
            if not reaction:
                continue
            for keyword in _extract_keywords(reaction):
                if keyword not in reaction_keywords:
                    reaction_keywords[keyword] = []
                reaction_keywords[keyword].append((person["name"], signal))

    for keyword, entries in reaction_keywords.items():
        unique_people = list(set(e[0] for e in entries))
        if len(unique_people) >= 2:
            patterns.append({
                "dimension": "reaction",
                "description": f"相似反应：「{keyword}」",
                "people": unique_people,
                "details": [
                    f"{name}: \"{sig['reaction']}\"" for name, sig in entries
                ],
            })

    return patterns


def match_current_to_history(current_event: str, people_data: list) -> list:
    """当前事件与历史退出信号的匹配。

    返回匹配到的历史事件列表，供 AI 在对话中引用。
    """
    matches = []
    current_keywords = set(_extract_keywords(current_event.lower()))

    for person in people_data:
        for signal in person.get("exit_signals", []):
            trigger_keywords = set(_extract_keywords(signal.get("trigger", "").lower()))
            reaction_keywords = set(_extract_keywords(signal.get("reaction", "").lower()))
            all_signal_keywords = trigger_keywords | reaction_keywords

            overlap = current_keywords & all_signal_keywords
            if overlap:
                matches.append({
                    "person": person["name"],
                    "date": signal.get("date", ""),
                    "trigger": signal.get("trigger", ""),
                    "reaction": signal.get("reaction", ""),
                    "matching_keywords": list(overlap),
                })

    return matches


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _months_between(start_date: str, end_date: str) -> int | None:
    """计算两个日期之间的月数（粗略）。"""
    try:
        fmt = "%Y-%m-%d" if len(start_date) > 7 else "%Y-%m"
        start = datetime.strptime(start_date, fmt)
        fmt = "%Y-%m-%d" if len(end_date) > 7 else "%Y-%m"
        end = datetime.strptime(end_date, fmt)
        return (end.year - start.year) * 12 + (end.month - start.month)
    except (ValueError, TypeError):
        return None


# Chinese relationship-related keywords for matching
_KEYWORD_PATTERNS = [
    "分手", "不想继续", "想跑", "退缩", "不舒服", "不满足", "差一点",
    "冷淡", "不在乎", "没那么喜欢", "热情", "未来", "承诺", "结婚",
    "安全感", "不安", "焦虑", "害怕", "逃避", "冷战", "吵架",
    "已读不回", "不回消息", "忽视", "控制", "自由", "空间",
]


def _extract_keywords(text: str) -> list:
    """从文本中提取关系相关关键词。"""
    found = []
    for kw in _KEYWORD_PATTERNS:
        if kw in text:
            found.append(kw)
    return found


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: pattern_engine.py <people_dir> [current_event]")
        sys.exit(1)

    people_dir = Path(sys.argv[1])
    current_event = sys.argv[2] if len(sys.argv) > 2 else None

    # Parse all people files
    people_data = []
    if people_dir.exists():
        for f in sorted(people_dir.glob("*.md")):
            data = parse_people_file(str(f))
            if data:
                people_data.append(data)

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
