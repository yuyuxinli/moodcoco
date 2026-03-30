"""
growth_tracker.py — 成长叙事追踪

扫描 diary/*.md，检测 Innovative Moments（INT/IMA 框架 EMNLP 2025）：
- Action: 用户做了不同于旧模式的行为
- Reflection: 从行动转向反思
- Protest: 挑战旧信念
- Re-conceptualization: 重新定义自己
- New experience: 用户经历了与旧模式不同的体验

用法（由 AI agent 通过 exec 调用）：
    python3 scripts/growth_tracker.py --diary-dir diary/ --people-dir people/ --user-file USER.md
    python3 scripts/growth_tracker.py --diary-dir diary/ --people-dir people/ --user-file USER.md --since 2026-03-01 --im-types reflection,protest

输出 JSON：{"status": "ok|no_growth_detected|insufficient_data", "innovative_moments": [...], "summary": "...", "error": null}
只用 Python 标准库。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import TypedDict

# ---------------------------------------------------------------------------
# Type Definitions
# ---------------------------------------------------------------------------


class IMMarkerConfig(TypedDict, total=False):
    description: str
    positive: list[str]
    contrast_with: list[str]


class DiaryEntry(TypedDict):
    date: str
    time: str
    title: str
    content: str
    user_quotes: list[str]
    emotion: str
    intensity: int
    file: str


class GrowthNode(TypedDict):
    date: str
    im_type: str
    im_description: str
    evidence: str
    quote: str
    context: str


class ContrastEndpoint(TypedDict):
    date: str
    text: str
    quote: str


class ContrastPair(TypedDict):
    type: str
    before: ContrastEndpoint | None
    after: ContrastEndpoint
    narrative: str


class _DismissalEntry(TypedDict):
    date: str
    evidence: str
    quote: str
    context: str


class TrackerSummary(TypedDict):
    total_nodes: int
    by_type: dict[str, int]
    total_pairs: int


class TrackerOutput(TypedDict):
    growth_nodes: list[GrowthNode]
    contrast_pairs: list[ContrastPair]
    summary: TrackerSummary


# ---------------------------------------------------------------------------
# Innovative Moment Markers
# ---------------------------------------------------------------------------

# 每种 IM 类型的检测关键词/模式
IM_MARKERS: dict[str, IMMarkerConfig] = {
    "action": {
        "description": "用户做了不同于旧模式的行为",
        "positive": [
            "第一次",
            "没有立刻",
            "忍住了",
            "选择了",
            "决定先",
            "这次我",
            "我试着",
            "我主动",
            "没有像以前",
            "我没有追问",
            "我没有发消息",
            "我先冷静了",
        ],
    },
    "reflection": {
        "description": "从行动转向反思",
        "positive": [
            "我想搞清楚",
            "我在想为什么",
            "我发现",
            "我注意到",
            "我觉得可能是",
            "也许是因为",
            "我开始意识到",
            "想了想",
            "反思",
            "回头看",
        ],
        "contrast_with": [
            "算了",
            "不管了",
            "管他呢",
            "分就分",
            "不想了",
        ],
    },
    "protest": {
        "description": "挑战旧信念",
        "positive": [
            "也许不是我的问题",
            "不一定是我",
            "我不觉得",
            "凭什么",
            "我不应该",
            "这不是我的错",
            "我有权",
            "我值得",
            "我不需要",
        ],
    },
    "reconceptualization": {
        "description": "重新定义自己",
        "positive": [
            "也许我只是还没学会",
            "我在成长",
            "我变了",
            "以前的我",
            "现在的我",
            "我跟以前不一样了",
            "我学到了",
            "这让我知道",
            "我理解了",
        ],
    },
    "performing_change": {
        "description": "用户在新场景中展现新模式",
        "positive": [
            "我想跟你说说",
            "我主动聊了",
            "这次我没有逃避",
            "我跟他说了",
            "我表达了",
            "我坦白了",
            "我没有回避",
            "我直接面对了",
            "我开口了",
        ],
    },
}


# ---------------------------------------------------------------------------
# Diary Parsing
# ---------------------------------------------------------------------------


def parse_diary_entries(diary_dir: str) -> list[DiaryEntry]:
    """解析 diary/ 目录下所有日记条目。

    返回按日期排序的条目列表，每个条目包含：
    - date: 日期字符串
    - time: 时间字符串
    - title: 标题
    - content: 完整内容
    - user_quotes: 用户原话列表
    - emotion: 情绪词
    - intensity: 强度
    """
    entries: list[DiaryEntry] = []
    diary_path = Path(diary_dir)

    if not diary_path.exists():
        return entries

    for md_file in sorted(diary_path.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", md_file.name)
        if not date_match:
            continue
        date = date_match.group(1)

        # Split into individual entries (## HH:MM sections)
        sections = re.split(r"^## (\d{2}:\d{2})\s+(.+)$", text, flags=re.MULTILINE)

        # sections: [preamble, time1, title1, content1, time2, title2, content2, ...]
        i = 1
        while i + 2 < len(sections):
            time_str = sections[i]
            title = sections[i + 1]
            content = sections[i + 2].strip()

            # Extract user quotes
            quotes = re.findall(r'[>]\s*[""「](.+?)[""」]', content)
            if not quotes:
                quotes = re.findall(r'>\s*"(.+?)"', content)

            # Extract emotion
            emotion_match = re.search(r"\*\*情绪\*\*[：:]\s*(.+)", content)
            emotion = emotion_match.group(1).strip() if emotion_match else ""

            # Extract intensity
            intensity_match = re.search(r"\*\*强度\*\*[：:]\s*(\d+)", content)
            intensity = int(intensity_match.group(1)) if intensity_match else 0

            entries.append(
                {
                    "date": date,
                    "time": time_str,
                    "title": title,
                    "content": content,
                    "user_quotes": quotes,
                    "emotion": emotion,
                    "intensity": intensity,
                    "file": str(md_file),
                }
            )

            i += 3

    return entries


# ---------------------------------------------------------------------------
# Growth Node Detection
# ---------------------------------------------------------------------------


def extract_growth_nodes(diary_dir: str) -> list[GrowthNode]:
    """扫描所有日记条目，检测 Innovative Moments。

    返回成长节点列表，每个节点包含：
    - date: 日期
    - im_type: IM 类型 (action/reflection/protest/reconceptualization)
    - evidence: 触发检测的文本
    - quote: 用户原话（如有）
    - context: 所在条目的标题和情绪
    """
    entries = parse_diary_entries(diary_dir)
    nodes: list[GrowthNode] = []

    for entry in entries:
        # Combine all searchable text
        searchable = entry["content"].lower()
        for quote in entry["user_quotes"]:
            searchable += " " + quote.lower()

        for im_type, config in IM_MARKERS.items():
            for marker in config.get("positive", []):
                if marker in searchable:
                    # Find the matching quote or content line
                    evidence = _find_evidence(entry, marker)
                    nodes.append(
                        {
                            "date": entry["date"],
                            "im_type": im_type,
                            "im_description": config.get("description", ""),
                            "evidence": evidence,
                            "quote": entry["user_quotes"][0]
                            if entry["user_quotes"]
                            else "",
                            "context": f"{entry['title']} ({entry['emotion']})"
                            if entry["emotion"]
                            else entry["title"],
                        }
                    )
                    break  # One IM per type per entry

    return nodes


def _find_evidence(entry: DiaryEntry, marker: str) -> str:
    """找到包含 marker 的那行文本作为证据。"""
    # Check user quotes first
    for quote in entry["user_quotes"]:
        if marker in quote.lower():
            return quote

    # Check content lines
    for line in entry["content"].split("\n"):
        if marker in line.lower():
            return line.strip()

    return marker


# ---------------------------------------------------------------------------
# Contrast Pairs
# ---------------------------------------------------------------------------


def find_contrast_pairs(
    growth_nodes: list[GrowthNode], diary_dir: str
) -> list[ContrastPair]:
    """找到可对比的成长节点对。

    对比类型：
    1. 同一话题在不同时间的不同表述（reflection 的 contrast_with）
    2. 早期的非 IM 表达 vs 后期的 IM 表达

    返回对比对列表，每对包含 before 和 after 节点。
    """
    pairs: list[ContrastPair] = []
    entries = parse_diary_entries(diary_dir)

    # Find reflection contrasts: early "算了/不管了" vs later "我想搞清楚"
    early_dismissals: list[_DismissalEntry] = []
    for entry in entries:
        searchable = entry["content"].lower()
        for quote in entry["user_quotes"]:
            searchable += " " + quote.lower()

        for marker in IM_MARKERS["reflection"].get("contrast_with", []):
            if marker in searchable:
                evidence = _find_evidence(entry, marker)
                early_dismissals.append(
                    {
                        "date": entry["date"],
                        "evidence": evidence,
                        "quote": entry["user_quotes"][0]
                        if entry["user_quotes"]
                        else "",
                        "context": entry["title"],
                    }
                )
                break

    # Pair early dismissals with later reflection nodes
    reflection_nodes = [n for n in growth_nodes if n["im_type"] == "reflection"]

    for dismissal in early_dismissals:
        for reflection in reflection_nodes:
            if reflection["date"] > dismissal["date"]:
                pairs.append(
                    {
                        "type": "reflection_growth",
                        "before": {
                            "date": dismissal["date"],
                            "text": dismissal["evidence"],
                            "quote": dismissal["quote"],
                        },
                        "after": {
                            "date": reflection["date"],
                            "text": reflection["evidence"],
                            "quote": reflection["quote"],
                        },
                        "narrative": (
                            f"{dismissal['date']} 你说\u201c{dismissal['evidence']}\u201d。"
                            f"{reflection['date']} 你说\u201c{reflection['evidence']}\u201d。"
                            f"你觉得这两个你，有什么不同？"
                        ),
                    }
                )
                break  # One pair per dismissal

    # Pair early non-action with later action nodes
    action_nodes = [n for n in growth_nodes if n["im_type"] == "action"]
    if action_nodes:
        # The first action node is itself a contrast with the previous default behavior
        for action in action_nodes:
            pairs.append(
                {
                    "type": "action_growth",
                    "before": None,  # Implicit: the old pattern
                    "after": {
                        "date": action["date"],
                        "text": action["evidence"],
                        "quote": action["quote"],
                    },
                    "narrative": (
                        f"你注意到了吗？{action['evidence']}\n这本身就已经不一样了。"
                    ),
                }
            )

    return pairs


# ---------------------------------------------------------------------------
# Conversation Formatting
# ---------------------------------------------------------------------------


def format_for_conversation(contrast_pair: ContrastPair) -> str:
    """将一个对比对格式化为可可可以在对话中直接使用的成长叙事文本。

    根据对比类型生成不同风格的叙事：
    - reflection_growth: 用两段原话展示从回避到反思的变化
    - action_growth: 强调用户做了不同于以往的行为
    """
    pair_type = contrast_pair.get("type", "")

    if pair_type == "reflection_growth":
        before = contrast_pair.get("before")
        after = contrast_pair.get("after")
        if before is not None and after is not None:
            before_text = before.get("quote") or before.get("text", "")
            after_text = after.get("quote") or after.get("text", "")
            return (
                f"{before['date']} 你说\u201c{before_text}\u201d。\n"
                f"{after['date']} 你说\u201c{after_text}\u201d。\n"
                f"你觉得这两个你，有什么不同？"
            )
    if pair_type == "action_growth":
        after = contrast_pair.get("after")
        if after is not None:
            evidence = after.get("text", "")
            return f"你注意到了吗？{evidence}\n这本身就已经不一样了。"
    # Fallback: use the pre-built narrative if available
    return contrast_pair.get("narrative", "")


# ---------------------------------------------------------------------------
# Spec-compliant output
# ---------------------------------------------------------------------------


class SpecInnovativeMoment(TypedDict):
    type: str
    date: str
    quote: str
    contrast_quote: str
    contrast_date: str
    person_context: str
    significance: str


def _build_spec_output(
    nodes: list[GrowthNode],
    pairs: list[ContrastPair],
    im_types_filter: list[str] | None,
) -> dict[str, object]:
    """Build spec-compliant JSON output per product-experience-design.md §5.5.

    Output schema:
    {
      "status": "ok" | "no_growth_detected" | "insufficient_data",
      "innovative_moments": [...],
      "summary": "...",
      "error": null
    }
    """
    if not nodes:
        return {
            "status": "insufficient_data" if not nodes else "no_growth_detected",
            "innovative_moments": [],
            "summary": "",
            "error": "No diary entries found" if not nodes else None,
        }

    # Filter by IM types if specified
    filtered_nodes = nodes
    if im_types_filter:
        filtered_nodes = [n for n in nodes if n["im_type"] in im_types_filter]

    if not filtered_nodes:
        return {
            "status": "no_growth_detected",
            "innovative_moments": [],
            "summary": "",
            "error": None,
        }

    # Build spec-compliant innovative_moments
    innovative_moments: list[SpecInnovativeMoment] = []
    for node in filtered_nodes:
        # Find matching contrast pair for this node
        contrast_quote = ""
        contrast_date = ""
        significance = node.get("im_description", "")
        for pair in pairs:
            after = pair.get("after")
            if after and after.get("date") == node["date"]:
                before = pair.get("before")
                if before:
                    contrast_quote = before.get("quote") or before.get("text", "")
                    contrast_date = before.get("date", "")
                significance = pair.get("narrative", significance)
                break

        # Extract person context from node context
        person_context = ""
        context = node.get("context", "")
        if "(" in context:
            person_context = context.split("(")[0].strip()

        innovative_moments.append({
            "type": node["im_type"],
            "date": node["date"],
            "quote": node.get("quote", ""),
            "contrast_quote": contrast_quote,
            "contrast_date": contrast_date,
            "person_context": person_context,
            "significance": significance,
        })

    by_type: dict[str, int] = {}
    for im_type in IM_MARKERS:
        count = sum(1 for n in filtered_nodes if n["im_type"] == im_type)
        if count > 0:
            by_type[im_type] = count

    type_summary = "、".join(f"{k} {v}个" for k, v in by_type.items())
    summary = f"发现{len(innovative_moments)}个成长节点，{type_summary}"

    return {
        "status": "ok",
        "innovative_moments": innovative_moments,
        "summary": summary,
        "error": None,
    }


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build argparse parser matching spec interface contract."""
    parser = argparse.ArgumentParser(
        description="成长节点追踪",
    )
    parser.add_argument(
        "--diary-dir",
        required=True,
        help="diary/ 目录路径",
    )
    parser.add_argument(
        "--people-dir",
        default=None,
        help="people/ 目录路径",
    )
    parser.add_argument(
        "--user-file",
        default=None,
        help="USER.md 路径",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="起始日期，格式 YYYY-MM-DD（默认 30 天前）",
    )
    parser.add_argument(
        "--im-types",
        default=None,
        help="要检测的 Innovative Moment 类型，逗号分隔",
    )
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    diary_dir: str = args.diary_dir

    if not Path(diary_dir).exists():
        output = {
            "status": "insufficient_data",
            "innovative_moments": [],
            "summary": "",
            "error": f"Diary directory not found: {diary_dir}",
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        sys.exit(0)

    # Parse IM types filter
    im_types_filter: list[str] | None = None
    if args.im_types:
        im_types_filter = [t.strip() for t in args.im_types.split(",")]

    nodes = extract_growth_nodes(diary_dir)

    # Filter by --since date
    if args.since:
        nodes = [n for n in nodes if n["date"] >= args.since]
    else:
        # Default: 30 days ago
        since_default = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        nodes = [n for n in nodes if n["date"] >= since_default]

    pairs = find_contrast_pairs(nodes, diary_dir)

    # Build spec-compliant output
    output = _build_spec_output(nodes, pairs, im_types_filter)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
