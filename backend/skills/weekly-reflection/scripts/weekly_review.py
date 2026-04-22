"""
weekly_review.py — 周情绪回顾数据统计 + Canvas HTML 生成

读取本周 diary/*.md + memory/ check-in 数据，统计情绪词频、关联人物、触发因素，
输出 JSON（供 agent 解析）或 HTML（供 Canvas 展示）。

设计参考：
- docs/product/product-experience-design.md F02 §2.1 卡片 A
- docs/product/product-experience-design.md F06 §5 Cron / §7.3 偏好

用法（由 AI agent 通过 exec 调用）：
    python3 weekly_review.py <diary_dir> [--format json|html] [--output <path>]
        [--people-dir <path>] [--memory-dir <path>] [--week current]

    --format json    输出 JSON 到 stdout（默认）
    --format html    生成 Canvas HTML 文件
    --memory-dir     memory/ 目录路径，读取 check-in 数据
    --week           指定哪一周（目前仅支持 'current'）

只用 Python 标准库（无 PIL / matplotlib 依赖）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 情绪语义分组
# ---------------------------------------------------------------------------

# 默认分组（硬编码 fallback），优先从 config/emotion_groups.json 加载
_DEFAULT_EMOTION_GROUPS: dict[str, list[str]] = {
    "焦虑族": ["焦虑", "紧张", "担心", "不安", "慌"],
    "悲伤族": ["难过", "伤心", "低落", "沮丧", "失落", "委屈"],
    "愤怒族": ["生气", "烦", "烦躁", "愤怒", "恼火", "不爽"],
    "开心族": ["开心", "高兴", "还不错", "愉快", "满足"],
    "疲惫族": ["累", "疲惫", "有点累", "倦", "心累"],
    "平静族": ["平静", "一般", "还行", "中性", "无感"],
}

# 扩展词簇（保持向后兼容，用于全文扫描的宽松匹配）
EMOTION_CLUSTERS = {
    "焦虑": ["焦虑", "紧张", "担心", "不安", "慌", "烦", "崩溃", "受不了", "心里没底"],
    "悲伤": [
        "难过", "伤心", "低落", "沮丧", "失落", "委屈",
        "心碎", "心痛", "想哭", "失望", "心酸",
    ],
    "愤怒": [
        "生气", "愤怒", "烦躁", "恼火", "不爽",
        "凭什么", "气死了", "火大", "烦死了",
    ],
    "开心": ["开心", "高兴", "还不错", "愉快", "满足", "快乐", "幸福"],
    "疲惫": ["累", "疲惫", "有点累", "倦", "心累", "好累"],
    "平静": ["平静", "一般", "还行", "中性", "无感", "还好"],
    "恐惧": ["害怕", "恐惧", "怕被丢下", "不安全", "没有安全感"],
    "自我怀疑": ["是不是我的问题", "我不够好", "我太敏感了", "都是我的错"],
    "麻木": ["无感", "累了", "不想管了", "懒得理", "无所谓", "什么都不想做"],
}


def _load_emotion_groups() -> dict[str, list[str]]:
    """从 config/emotion_groups.json 加载情绪分组，失败则用默认值。"""
    config_path = Path(__file__).resolve().parent.parent / "config" / "emotion_groups.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            groups = data.get("groups", {})
            if groups:
                return groups
        except (json.JSONDecodeError, KeyError):
            pass
    return _DEFAULT_EMOTION_GROUPS


EMOTION_GROUPS = _load_emotion_groups()

# 反向映射：词 → 族名（从 emotion_groups.json 的 6 族）
WORD_TO_GROUP: dict[str, str] = {}
for group_name, words in EMOTION_GROUPS.items():
    for w in words:
        WORD_TO_GROUP[w] = group_name

# 反向映射：词 → 簇名（从扩展词簇，用于 diary 全文扫描）
WORD_TO_CLUSTER: dict[str, str] = {}
for cluster_name, words in EMOTION_CLUSTERS.items():
    for w in words:
        WORD_TO_CLUSTER[w] = cluster_name

# 情绪色板（与 F02 §2.1 设计语言暖色系对齐）
CLUSTER_COLORS = {
    "焦虑": "#FFB74D",
    "悲伤": "#90CAF9",
    "愤怒": "#FF7F7F",
    "开心": "#A8E6CF",
    "疲惫": "#D7CCC8",
    "平静": "#C5E1A5",
    "恐惧": "#C5A3FF",
    "自我怀疑": "#FFCC80",
    "麻木": "#BDBDBD",
}

# 正面 / 负面分类
POSITIVE_CLUSTERS = {"开心", "平静"}
POSITIVE_GROUPS = {"开心族", "平静族"}
NEGATIVE_CLUSTERS = {"焦虑", "悲伤", "愤怒", "恐惧", "自我怀疑"}
NEUTRAL_CLUSTERS = {"疲惫", "麻木"}

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


# ---------------------------------------------------------------------------
# Date range helpers
# ---------------------------------------------------------------------------


def get_this_week_range() -> tuple[date, date]:
    """返回本周一和周日的日期。"""
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_last_week_range() -> tuple[date, date]:
    """返回上周一和周日的日期。"""
    monday, _ = get_this_week_range()
    last_sunday = monday - timedelta(days=1)
    last_monday = last_sunday - timedelta(days=6)
    return last_monday, last_sunday


def iso_week_label(d: date) -> str:
    """返回 YYYY-WNN 格式的周标签。"""
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


# ---------------------------------------------------------------------------
# Diary Parsing
# ---------------------------------------------------------------------------


def find_diary_files(
    diary_dir: str, start_date: date, end_date: date
) -> list[tuple[date, Path]]:
    """在 diary/ 目录下找到指定日期范围的 md 文件。"""
    diary_path = Path(diary_dir)
    files = []

    current = start_date
    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        nested = (
            diary_path
            / current.strftime("%Y")
            / current.strftime("%m")
            / f"{date_str}.md"
        )
        flat = diary_path / f"{date_str}.md"

        if nested.exists():
            files.append((current, nested))
        elif flat.exists():
            files.append((current, flat))

        current += timedelta(days=1)

    return files


def parse_diary_entry(filepath: Path) -> dict[str, Any]:
    """解析单个日记文件，提取情绪词、人物和触发因素。"""
    text = filepath.read_text(encoding="utf-8")
    result: dict[str, Any] = {
        "emotions": [],
        "people": [],
        "triggers": [],
        "summary": "",
    }

    current_section = None
    for line in text.split("\n"):
        stripped = line.strip()

        if re.match(r"^#+\s*情绪|^#+\s*心情|^#+\s*feeling", stripped, re.IGNORECASE):
            current_section = "emotion"
            continue
        if re.match(
            r"^#+\s*人物|^#+\s*关联|^#+\s*people|^#+\s*关系", stripped, re.IGNORECASE
        ):
            current_section = "people"
            continue
        if re.match(
            r"^#+\s*触发|^#+\s*trigger|^#+\s*原因|^#+\s*因为", stripped, re.IGNORECASE
        ):
            current_section = "trigger"
            continue
        if re.match(r"^#+\s*摘要|^#+\s*summary|^#+\s*记录", stripped, re.IGNORECASE):
            current_section = "summary"
            continue
        if re.match(r"^#+\s", stripped):
            current_section = None

        if not stripped or stripped.startswith("---"):
            continue

        # 提取情绪关键词（从全文扫描）
        for word in WORD_TO_CLUSTER:
            if word in stripped:
                result["emotions"].append(word)

        # 也从 **情绪**：XX 行直接提取
        emo_match = re.match(r"\*\*情绪\*\*[：:]\s*(.+)", stripped)
        if emo_match:
            emo_text = emo_match.group(1).strip()
            # 尝试匹配到情绪族
            if emo_text not in result["emotions"]:
                result["emotions"].append(emo_text)

        if current_section == "people":
            m = re.match(r"^[-*]\s*(.+)", stripped)
            if m:
                result["people"].append(m.group(1).strip())
        elif current_section == "trigger":
            m = re.match(r"^[-*]\s*(.+)", stripped)
            if m:
                result["triggers"].append(m.group(1).strip())
        elif current_section == "summary":
            if result["summary"]:
                result["summary"] += " "
            result["summary"] += stripped

        # 从 **提到的人**：[XX](...) 行提取人名
        people_match = re.match(r"\*\*提到的人\*\*[：:]\s*(.+)", stripped)
        if people_match:
            # 提取链接格式 [名字](...) 中的名字
            for m in re.finditer(r"\[([^\]]+)\]", people_match.group(1)):
                name = m.group(1).strip()
                if name not in result["people"]:
                    result["people"].append(name)

    return result


def cross_check_people(people_mentioned: list[str], people_dir: str) -> list[str]:
    """与 people/ 目录的已有档案交叉匹配。"""
    if not people_dir:
        return people_mentioned

    people_path = Path(people_dir)
    if not people_path.exists():
        return people_mentioned

    known = {p.stem for p in people_path.glob("*.md")}
    matched = []
    for name in people_mentioned:
        clean = name.strip()
        if clean in known or any(clean in k for k in known):
            matched.append(clean)
        else:
            matched.append(clean)
    return matched


# ---------------------------------------------------------------------------
# Memory / check-in Parsing
# ---------------------------------------------------------------------------


def parse_checkins_from_memory(
    memory_dir: str, start_date: date, end_date: date
) -> list[dict[str, Any]]:
    """从 memory/YYYY-MM-DD.md 中解析 ## check-in 块。

    返回列表，每项包含 date, time, emotion, source, note。
    一天可能有多条 check-in，取最后一条作为当天代表。
    """
    memory_path = Path(memory_dir)
    if not memory_path.exists():
        return []

    all_checkins: list[dict[str, Any]] = []

    current = start_date
    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        filepath = memory_path / f"{date_str}.md"

        if filepath.exists():
            text = filepath.read_text(encoding="utf-8")
            day_checkins = _extract_checkin_blocks(text, current)
            if day_checkins:
                # 取最后一条作为当天代表
                all_checkins.append(day_checkins[-1])

        current += timedelta(days=1)

    return all_checkins


def _extract_checkin_blocks(text: str, entry_date: date) -> list[dict[str, Any]]:
    """从单个 memory 文件中提取所有 ## check-in 块。"""
    blocks: list[dict[str, Any]] = []
    in_checkin = False
    current_block: dict[str, Any] = {}

    for line in text.split("\n"):
        stripped = line.strip()

        if stripped == "## check-in":
            if in_checkin and current_block:
                blocks.append(current_block)
            in_checkin = True
            current_block = {"date": entry_date.isoformat()}
            continue

        if stripped.startswith("## ") and stripped != "## check-in":
            if in_checkin and current_block:
                blocks.append(current_block)
            in_checkin = False
            current_block = {}
            continue

        if in_checkin:
            m = re.match(r"^-\s*(\w+)\s*:\s*(.*)", stripped)
            if m:
                key = m.group(1).strip()
                value = m.group(2).strip()
                if key == "time":
                    current_block["time"] = value
                elif key == "emotion":
                    current_block["emotion"] = value
                elif key == "source":
                    current_block["source"] = value
                elif key == "note":
                    current_block["note"] = value

    if in_checkin and current_block:
        blocks.append(current_block)

    return blocks


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def analyze_week(
    diary_files: list[tuple[date, Path]],
    people_dir: str | None = None,
    memory_dir: str | None = None,
) -> dict[str, Any]:
    """分析本周日记 + check-in 数据。"""
    monday, sunday = get_this_week_range()

    daily: dict[str, Any] = {}
    all_emotions: list[str] = []
    all_people: list[str] = []
    all_triggers: list[str] = []
    entry_dates: set[str] = set()

    # --- diary entries ---
    for entry_date, filepath in diary_files:
        entry = parse_diary_entry(filepath)
        weekday_idx = entry_date.weekday()
        day_key = WEEKDAY_NAMES[weekday_idx]

        day_clusters_seen: set[str] = set()
        day_emotions: list[str] = []
        for emo in entry["emotions"]:
            cluster = WORD_TO_CLUSTER.get(emo, emo)
            if cluster not in day_clusters_seen:
                day_clusters_seen.add(cluster)
                day_emotions.append(emo)

        daily[day_key] = {
            "date": entry_date.isoformat(),
            "emotions": day_emotions,
            "primary_emotion": day_emotions[0] if day_emotions else "无记录",
            "primary_cluster": WORD_TO_CLUSTER.get(day_emotions[0], "平静")
            if day_emotions
            else None,
            "people": entry["people"],
            "triggers": entry["triggers"],
            "summary": entry["summary"],
            "source": "diary",
        }

        entry_dates.add(entry_date.isoformat())
        all_emotions.extend(day_emotions)
        all_people.extend(entry["people"])
        all_triggers.extend(entry["triggers"])

    # --- check-in entries from memory/ ---
    emotion_summary: list[dict[str, Any]] = []
    checkin_emotions: list[str] = []

    if memory_dir:
        checkins = parse_checkins_from_memory(memory_dir, monday, sunday)
        for ci in checkins:
            ci_date = ci.get("date", "")
            ci_emotion = ci.get("emotion", "")
            weekday_idx = date.fromisoformat(ci_date).weekday() if ci_date else 0
            day_key = WEEKDAY_NAMES[weekday_idx]

            entry_dates.add(ci_date)
            if ci_emotion:
                checkin_emotions.append(ci_emotion)

            # 如果这天 diary 没有数据，用 check-in 补充 daily
            if day_key not in daily:
                daily[day_key] = {
                    "date": ci_date,
                    "emotions": [ci_emotion] if ci_emotion else [],
                    "primary_emotion": ci_emotion or "无记录",
                    "primary_cluster": WORD_TO_CLUSTER.get(ci_emotion, "平静")
                    if ci_emotion
                    else None,
                    "people": [],
                    "triggers": [],
                    "summary": ci.get("note", ""),
                    "source": "check-in",
                }

    # 构建 emotion_summary（diary + check-in 并列）
    for entry_date, filepath in diary_files:
        entry = parse_diary_entry(filepath)
        day_emotions = entry["emotions"]
        primary = day_emotions[0] if day_emotions else ""
        evt = entry["summary"] or (entry["triggers"][0] if entry["triggers"] else "")
        item: dict[str, Any] = {
            "date": entry_date.isoformat(),
            "emotion": primary,
            "source": "diary",
        }
        if evt:
            item["event"] = evt
        emotion_summary.append(item)

    if memory_dir:
        checkins = parse_checkins_from_memory(memory_dir, monday, sunday)
        for ci in checkins:
            item = {
                "date": ci.get("date", ""),
                "emotion": ci.get("emotion", ""),
                "source": "check-in",
            }
            if ci.get("note"):
                item["event"] = ci["note"]
            emotion_summary.append(item)

    emotion_summary.sort(key=lambda x: x.get("date", ""))

    # --- 情绪统计（按簇聚合）---
    combined_emotions = all_emotions + checkin_emotions
    cluster_counts: Counter[str] = Counter()
    for emo in combined_emotions:
        cluster = WORD_TO_CLUSTER.get(emo, emo)
        cluster_counts[cluster] += 1

    # 情绪族统计（用 emotion_groups.json 的 6 族）
    group_counts: Counter[str] = Counter()
    for emo in combined_emotions:
        group = WORD_TO_GROUP.get(emo)
        if group:
            group_counts[group] += 1

    # --- 人物统计 ---
    people_counts = Counter(all_people)
    if people_dir:
        people_counts = Counter(cross_check_people(all_people, people_dir))

    # --- 触发统计 ---
    trigger_counts = Counter(all_triggers)

    # --- 重复主题检测 ---
    repeated_themes: list[dict[str, Any]] = []

    # 情绪重复：语义分组后同一族 ≥3 次
    for group_name, count in group_counts.items():
        if count >= 3:
            repeated_themes.append({
                "type": "emotion",
                "word": group_name,
                "count": count,
            })

    # 人物重复：同一人出现 ≥3 天
    # 统计每个人出现在哪些天
    person_day_counts: Counter[str] = Counter()
    for _day_name, day_data in daily.items():
        for person in day_data.get("people", []):
            person_day_counts[person] += 1
    for person, day_count in person_day_counts.items():
        if day_count >= 3:
            repeated_themes.append({
                "type": "person",
                "name": person,
                "count": day_count,
                "context": "",
            })

    # 触发重复：≥2 次
    for trigger, count in trigger_counts.items():
        if count >= 2:
            repeated_themes.append({
                "type": "trigger",
                "word": trigger,
                "count": count,
            })

    # --- 找情绪最重的一天 ---
    worst_day = None
    worst_score = 0
    for day_name, day_data in daily.items():
        neg_count = sum(
            1
            for e in day_data.get("emotions", [])
            if WORD_TO_CLUSTER.get(e, "") in NEGATIVE_CLUSTERS
        )
        if neg_count > worst_score:
            worst_score = neg_count
            worst_day = day_name

    # --- 跨周重复检测 ---
    top_emotion = cluster_counts.most_common(1)[0] if cluster_counts else None
    top_person = people_counts.most_common(1)[0] if people_counts else None

    # --- 跨周模式检测 (F10 §8.4) ---
    cross_week_pattern = detect_cross_week_pattern(
        repeated_themes, people_counts, memory_dir, monday,
    )

    # --- 成长信号检测 ---
    growth_signals = detect_growth_signals(
        emotion_summary, group_counts, repeated_themes,
        entry_dates, memory_dir, monday, sunday,
    )

    # --- highlight ---
    total_entries = len(diary_files) + len(checkin_emotions)
    positive_days = sum(
        1 for d in daily.values()
        if d.get("primary_cluster") in POSITIVE_CLUSTERS
    )
    highlight = ""
    if total_entries > 0:
        parts = [f"本周 {total_entries} 条记录"]
        if positive_days > 0:
            parts.append(f"中 {positive_days} 天心情不错")
        if worst_day:
            parts.append(f"，{worst_day}是情绪最低的一天")
        highlight = "".join(parts)

    return {
        "status": "ok",
        "week": f"{monday.isoformat()} ~ {sunday.isoformat()}",
        "week_start": monday.isoformat(),
        "week_end": sunday.isoformat(),
        "entries": total_entries,
        "diary_count": len(diary_files),
        "emotion_summary": emotion_summary,
        "repeated_themes": repeated_themes,
        "growth_signals": growth_signals,
        "highlight": highlight,
        "daily": daily,
        "emotion_clusters": dict(cluster_counts.most_common()),
        "top_emotion": {"name": top_emotion[0], "count": top_emotion[1]}
        if top_emotion
        else None,
        "people_summary": dict(people_counts.most_common()),
        "top_person": {"name": top_person[0], "count": top_person[1]}
        if top_person
        else None,
        "trigger_summary": dict(trigger_counts.most_common()),
        "worst_day": worst_day,
        "person_mention_count": dict(people_counts),
        "cross_week_pattern": cross_week_pattern,
    }


# ---------------------------------------------------------------------------
# Cross-Week Pattern Detection (F10 §8.4)
# ---------------------------------------------------------------------------


def detect_cross_week_pattern(
    repeated_themes: list[dict[str, Any]],
    people_counts: Counter,
    memory_dir: str | None,
    monday: date,
) -> dict[str, Any]:
    """检测跨周重复主题模式。

    比较本周 repeated_themes 与上周缓存的 repeated_themes，
    按主题文本精确匹配优先，回退到触发词重叠 >= 50%。

    Returns:
        F10 §8.4 规范的 cross_week_pattern 字段。
    """
    no_match: dict[str, Any] = {"detected": False, "themes": []}

    if not repeated_themes:
        return no_match

    # 读取上周缓存
    last_monday, _last_sunday = get_last_week_range()
    previous_week_label = iso_week_label(last_monday)
    previous_week_cache = _load_weekly_cache(memory_dir, previous_week_label)

    if not previous_week_cache:
        return no_match

    previous_themes = previous_week_cache.get("repeated_themes", [])
    if not previous_themes:
        return no_match

    # 构建上周主题索引：按 type 分类，记录 word/name + count
    prev_by_key: dict[str, dict[str, Any]] = {}
    for pt in previous_themes:
        key = _theme_key(pt)
        if key:
            prev_by_key[key] = pt

    # 跨周匹配
    matched_themes: list[dict[str, Any]] = []

    for current_theme in repeated_themes:
        current_key = _theme_key(current_theme)
        if not current_key:
            continue

        prev_theme = prev_by_key.get(current_key)

        # 精确匹配失败 → 回退到触发词重叠 >= 50%
        if prev_theme is None:
            prev_theme = _fuzzy_match_theme(current_theme, previous_themes)

        if prev_theme is not None:
            theme_desc = _theme_description(current_theme)
            current_count = current_theme.get("count", 1)
            prev_count = prev_theme.get("count", 1)

            # 计算连续出现的周数（检查更早的缓存）
            span_weeks = _count_span_weeks(
                current_theme, memory_dir, monday, max_lookback=4,
            )

            # 收集相关人物
            related_persons = _collect_related_persons(
                current_theme, people_counts,
            )

            matched_themes.append({
                "theme": theme_desc,
                "current_week_count": current_count,
                "previous_week_count": prev_count,
                "span_weeks": span_weeks,
                "related_persons": related_persons,
            })

    if not matched_themes:
        return no_match

    return {
        "detected": True,
        "themes": matched_themes,
    }


def _theme_key(theme: dict[str, Any]) -> str | None:
    """生成主题的匹配键。"""
    t = theme.get("type", "")
    if t == "emotion":
        return f"emotion:{theme.get('word', '')}"
    if t == "person":
        return f"person:{theme.get('name', '')}"
    if t == "trigger":
        return f"trigger:{theme.get('word', '')}"
    return None


def _theme_description(theme: dict[str, Any]) -> str:
    """生成人类可读的主题描述。"""
    t = theme.get("type", "")
    if t == "emotion":
        return theme.get("word", "未知情绪")
    if t == "person":
        return f"关于{theme.get('name', '某人')}的反复提及"
    if t == "trigger":
        return theme.get("word", "未知触发")
    return str(theme)


def _fuzzy_match_theme(
    current: dict[str, Any],
    previous_themes: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """模糊匹配：同类型 + 关键词重叠 >= 50%。"""
    current_type = current.get("type", "")
    current_words = set(_tokenize_theme(current))

    if not current_words:
        return None

    best_match = None
    best_overlap = 0.0

    for pt in previous_themes:
        if pt.get("type", "") != current_type:
            continue

        prev_words = set(_tokenize_theme(pt))
        if not prev_words:
            continue

        # 使用较短集合的长度做分母（containment ratio），
        # 这样 "不回消息" 是 "不回消息怀疑自己" 的子集时能匹配成功。
        overlap = len(current_words & prev_words) / min(
            len(current_words), len(prev_words),
        )
        if overlap >= 0.5 and overlap > best_overlap:
            best_overlap = overlap
            best_match = pt

    return best_match


def _tokenize_theme(theme: dict[str, Any]) -> list[str]:
    """将主题的关键文本拆分为词集。

    对中文文本使用 2-gram 切分以支持模糊匹配；
    对空格分隔的文本（英文 / 混合）按空格切分。
    """
    text = theme.get("word", "") or theme.get("name", "") or ""
    context = theme.get("context", "")
    combined = f"{text} {context}".strip()
    if not combined:
        return []

    parts = combined.split()
    # 如果 split 只产出一个 token 且含有 CJK 字符，使用 2-gram 切分
    if len(parts) == 1 and any("\u4e00" <= ch <= "\u9fff" for ch in parts[0]):
        word = parts[0]
        tokens = [word[i:i+2] for i in range(len(word) - 1)]
        tokens.append(word)  # 保留完整词作为 token
        return tokens

    # 多个空格分隔的 token → 直接用，但对每个中文 token 也做 2-gram
    tokens: list[str] = []
    for part in parts:
        if len(part) > 2 and any("\u4e00" <= ch <= "\u9fff" for ch in part):
            tokens.extend(part[i:i+2] for i in range(len(part) - 1))
            tokens.append(part)
        else:
            tokens.append(part)
    return tokens


def _count_span_weeks(
    theme: dict[str, Any],
    memory_dir: str | None,
    monday: date,
    max_lookback: int = 4,
) -> int:
    """计算主题连续出现的周数（包含本周）。"""
    span = 1  # 本周已确认出现
    current_key = _theme_key(theme)
    if not current_key:
        return span

    for weeks_ago in range(1, max_lookback + 1):
        past_monday = monday - timedelta(weeks=weeks_ago)
        past_label = iso_week_label(past_monday)
        cache = _load_weekly_cache(memory_dir, past_label)
        if not cache:
            break

        past_themes = cache.get("repeated_themes", [])
        found = False
        for pt in past_themes:
            if _theme_key(pt) == current_key:
                found = True
                break
            # 也尝试模糊匹配
            if _fuzzy_match_theme(theme, [pt]) is not None:
                found = True
                break

        if found:
            span += 1
        else:
            break

    return span


def _collect_related_persons(
    theme: dict[str, Any],
    people_counts: Counter,
) -> list[str]:
    """收集与主题相关的人物列表。"""
    t = theme.get("type", "")
    if t == "person":
        name = theme.get("name", "")
        return [name] if name else []

    # 对于情绪/触发类型的重复主题，返回本周出现最多的人物
    if people_counts:
        return [name for name, _ in people_counts.most_common(3)]
    return []


# ---------------------------------------------------------------------------
# Growth Signals Detection
# ---------------------------------------------------------------------------


def detect_growth_signals(
    emotion_summary: list[dict[str, Any]],
    this_week_groups: Counter[str],
    repeated_themes: list[dict[str, Any]],
    entry_dates: set[str],
    memory_dir: str | None,
    monday: date,
    sunday: date,
) -> list[dict[str, Any]]:
    """检测成长信号（轻量级，仅比较相邻两周）。"""
    signals: list[dict[str, Any]] = []

    # --- consistency: 连续 ≥5 天有 diary 或 check-in 记录 ---
    streak = _longest_streak(entry_dates, monday, sunday)
    if streak >= 5:
        signals.append({
            "type": "consistency",
            "description": f"连续 {streak} 天有记录",
            "streak_days": streak,
        })

    # --- 需要上周缓存的信号 ---
    last_monday, _last_sunday = get_last_week_range()
    last_week_label = iso_week_label(last_monday)
    last_cache = _load_weekly_cache(memory_dir, last_week_label)

    if last_cache:
        last_groups = _extract_group_counts_from_cache(last_cache)

        # emotion_shift: 上周某族 ≥3 次，本周同族 ≤1 次（或反之）
        all_groups = set(last_groups.keys()) | set(this_week_groups.keys())
        for g in all_groups:
            last_count = last_groups.get(g, 0)
            this_count = this_week_groups.get(g, 0)
            if last_count >= 3 and this_count <= 1:
                signals.append({
                    "type": "emotion_shift",
                    "description": f"上周{g}出现 {last_count} 次，本周只有 {this_count} 次",
                    "from": g,
                    "from_count": last_count,
                    "to_count": this_count,
                    "direction": "decrease",
                })
            elif this_count >= 3 and last_count <= 1:
                signals.append({
                    "type": "emotion_shift",
                    "description": f"上周{g}出现 {last_count} 次，本周 {this_count} 次",
                    "from": g,
                    "from_count": last_count,
                    "to_count": this_count,
                    "direction": "increase",
                })

        # topic_fade: 上周某人物 ≥3 次，本周 0 次
        last_themes = last_cache.get("repeated_themes", [])
        last_people = {
            t["name"]: t["count"]
            for t in last_themes
            if t.get("type") == "person"
        }
        this_people = {
            t["name"]: t["count"]
            for t in repeated_themes
            if t.get("type") == "person"
        }
        for person, last_count in last_people.items():
            if last_count >= 3 and person not in this_people:
                signals.append({
                    "type": "topic_fade",
                    "description": f"上周{person}出现 {last_count} 次，本周没提到",
                    "subject": person,
                    "last_week_count": last_count,
                    "this_week_count": 0,
                })

    # --- new_positive: 本周出现 ≥2 次新的正面情绪词 ---
    positive_emotions_this_week: Counter[str] = Counter()
    for item in emotion_summary:
        emo = item.get("emotion", "")
        group = WORD_TO_GROUP.get(emo)
        if group in POSITIVE_GROUPS:
            positive_emotions_this_week[emo] += 1

    # 检查过去 30 天的历史（通过缓存近 4 周判断）
    historical_positive = set()
    if memory_dir:
        for weeks_ago in range(1, 5):
            d = monday - timedelta(weeks=weeks_ago)
            label = iso_week_label(d)
            cache = _load_weekly_cache(memory_dir, label)
            if cache:
                for item in cache.get("emotion_summary", []):
                    emo = item.get("emotion", "")
                    group = WORD_TO_GROUP.get(emo)
                    if group in POSITIVE_GROUPS:
                        historical_positive.add(emo)

    for emo, count in positive_emotions_this_week.items():
        if count >= 2 and emo not in historical_positive:
            signals.append({
                "type": "new_positive",
                "description": f"本周新出现的正面情绪'{emo}'（{count}次）",
                "emotion": emo,
                "count": count,
            })

    return signals


def _longest_streak(entry_dates: set[str], monday: date, sunday: date) -> int:
    """计算本周内最长连续记录天数。"""
    max_streak = 0
    current_streak = 0
    current = monday
    while current <= sunday:
        if current.isoformat() in entry_dates:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0
        current += timedelta(days=1)
    return max_streak


# ---------------------------------------------------------------------------
# Weekly Cache
# ---------------------------------------------------------------------------


def _cache_dir(memory_dir: str | None) -> Path | None:
    """返回 weekly_cache 目录路径。"""
    if not memory_dir:
        return None
    return Path(memory_dir) / "weekly_cache"


def _load_weekly_cache(memory_dir: str | None, week_label: str) -> dict[str, Any] | None:
    """读取指定周的缓存。"""
    cache_root = _cache_dir(memory_dir)
    if not cache_root:
        return None
    cache_file = cache_root / f"{week_label}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def write_weekly_cache(
    memory_dir: str | None,
    week_label: str,
    analysis: dict[str, Any],
) -> None:
    """写入本周缓存（完整 JSON 输出），保留最近 8 周，超过的自动清理。

    F10 §8.4: 每次执行后将本周完整输出写入 weekly_cache/YYYY-WNN.json 供下周使用。
    """
    cache_root = _cache_dir(memory_dir)
    if not cache_root:
        return

    cache_root.mkdir(parents=True, exist_ok=True)

    # 保存完整分析结果以供下周 cross_week_pattern 比较
    cache_data = {
        "week": week_label,
        "emotion_summary": analysis.get("emotion_summary", []),
        "repeated_themes": analysis.get("repeated_themes", []),
        "person_mention_count": analysis.get("person_mention_count", {}),
        "emotion_clusters": analysis.get("emotion_clusters", {}),
        "growth_signals": analysis.get("growth_signals", []),
    }

    cache_file = cache_root / f"{week_label}.json"
    cache_file.write_text(
        json.dumps(cache_data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    # 清理超过 8 周的缓存
    _cleanup_old_caches(cache_root, keep=8)


def _cleanup_old_caches(cache_root: Path, keep: int = 8) -> None:
    """保留最近 N 周的缓存，删除更早的。"""
    import contextlib

    cache_files = sorted(cache_root.glob("*.json"), reverse=True)
    for old_file in cache_files[keep:]:
        with contextlib.suppress(OSError):
            old_file.unlink()


def _extract_group_counts_from_cache(cache: dict[str, Any]) -> dict[str, int]:
    """从缓存的 emotion_summary 中提取情绪族计数。"""
    counts: Counter[str] = Counter()
    for item in cache.get("emotion_summary", []):
        emo = item.get("emotion", "")
        group = WORD_TO_GROUP.get(emo)
        if group:
            counts[group] += 1
    return dict(counts)


# ---------------------------------------------------------------------------
# Canvas HTML Generation（F02 §2.1 卡片 A: 周情绪地图）
# ---------------------------------------------------------------------------

CANVAS_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>你这周的心情地图</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: -apple-system, "PingFang SC", "Hiragino Sans GB", sans-serif;
    background: #FFF8F0;
    color: #5D4E37;
    padding: 32px 24px;
    min-height: 100vh;
  }

  .card {
    max-width: 480px;
    margin: 0 auto;
    background: #FFFFFF;
    border-radius: 20px;
    box-shadow: 0 4px 24px rgba(255, 180, 150, 0.15);
    padding: 32px 28px;
    position: relative;
    overflow: hidden;
  }

  .card::before {
    content: '';
    position: absolute;
    top: -60px;
    right: -60px;
    width: 160px;
    height: 160px;
    background: radial-gradient(circle, rgba(255, 212, 162, 0.3) 0%, transparent 70%);
    border-radius: 50%;
  }

  .card-title {
    font-size: 20px;
    font-weight: 600;
    margin-bottom: 24px;
    position: relative;
    z-index: 1;
  }

  .day-row {
    display: flex;
    align-items: center;
    margin-bottom: 12px;
    position: relative;
    z-index: 1;
  }

  .day-label {
    width: 40px;
    font-size: 13px;
    color: #8B7355;
    flex-shrink: 0;
  }

  .emotion-bar {
    height: 28px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    padding: 0 12px;
    font-size: 13px;
    color: #5D4E37;
    transition: width 0.6s ease;
    min-width: 60px;
    cursor: default;
    position: relative;
  }

  .emotion-bar:hover {
    filter: brightness(0.95);
  }

  .emotion-bar .bar-text {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .day-row.no-record .emotion-bar {
    background: #F0EDE8;
    color: #B0A898;
  }

  .divider {
    border: none;
    border-top: 1px solid rgba(200, 180, 160, 0.2);
    margin: 20px 0;
  }

  .summary-section {
    position: relative;
    z-index: 1;
  }

  .summary-item {
    font-size: 14px;
    color: #8B7355;
    margin-bottom: 8px;
    line-height: 1.6;
  }

  .summary-item strong {
    color: #5D4E37;
  }

  .cta-btn {
    display: block;
    width: 100%;
    margin-top: 24px;
    padding: 14px;
    background: linear-gradient(135deg, #FFD4A2 0%, #FFB74D 100%);
    border: none;
    border-radius: 14px;
    font-size: 15px;
    color: #5D4E37;
    font-weight: 500;
    cursor: pointer;
    text-align: center;
    text-decoration: none;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }

  .cta-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(255, 183, 77, 0.3);
  }

  .cta-btn:active {
    transform: translateY(0);
  }

  .empty-state {
    text-align: center;
    padding: 48px 24px;
    color: #B0A898;
    font-size: 15px;
    line-height: 1.8;
  }
</style>
</head>
<body>
<div class="card">
  <div class="card-title">你这周的心情地图</div>

  <!-- WEEKLY_BARS -->

  <hr class="divider">

  <div class="summary-section">
    <!-- SUMMARY_ITEMS -->
  </div>

  <a class="cta-btn" href="openclaw://agent?message=我想聊聊这周的心情地图里的内容">
    想聊聊这周的感觉 →
  </a>
</div>

<script>
  // Deep Link: 点击 CTA 按钮回到 agent 对话
  document.querySelector('.cta-btn').addEventListener('click', function(e) {
    e.preventDefault();
    window.location.href = this.getAttribute('href');
  });
</script>
</body>
</html>"""


def _bar_width(emotion_count: int) -> int:
    """根据当天情绪数量计算色块宽度百分比。"""
    base = 20
    per_emotion = 15
    return min(base + emotion_count * per_emotion, 95)


def _get_bar_color(cluster_name: str) -> str:
    """获取情绪簇对应的色块颜色。"""
    return CLUSTER_COLORS.get(cluster_name, "#E0D8CF")


def generate_html(analysis: dict[str, Any], output_path: str | None = None) -> str:
    """生成周情绪地图 Canvas HTML。"""

    daily = analysis.get("daily", {})

    bars_html = []
    for day_name in WEEKDAY_NAMES:
        day_data = daily.get(day_name)

        if not day_data or day_data.get("primary_emotion") == "无记录":
            bars_html.append(f"""  <div class="day-row no-record">
    <span class="day-label">{day_name}</span>
    <div class="emotion-bar" style="width: 20%;">
      <span class="bar-text">—</span>
    </div>
  </div>""")
        else:
            cluster = day_data.get("primary_cluster", "平静")
            color = _get_bar_color(cluster)
            emotion_text = day_data["primary_emotion"]

            people = day_data.get("people", [])
            triggers = day_data.get("triggers", [])
            extra = ""
            if people:
                extra += f"（{people[0]}）"
            elif triggers:
                extra += f"（{triggers[0]}）"

            width = _bar_width(len(day_data.get("emotions", [])))

            bars_html.append(f"""  <div class="day-row">
    <span class="day-label">{day_name}</span>
    <div class="emotion-bar" style="width: {width}%; background: {color};" title="{", ".join(day_data.get("emotions", []))}">
      <span class="bar-text">{emotion_text}{extra}</span>
    </div>
  </div>""")

    summary_items = []
    top_emo = analysis.get("top_emotion")
    if top_emo:
        summary_items.append(
            f'<div class="summary-item">这周出现最多的感觉：<strong>{top_emo["name"]}</strong>（{top_emo["count"]}次）</div>'
        )

    top_person = analysis.get("top_person")
    if top_person:
        summary_items.append(
            f'<div class="summary-item">最常想到的人：<strong>{top_person["name"]}</strong></div>'
        )

    worst = analysis.get("worst_day")
    if worst:
        summary_items.append(f'<div class="summary-item">{worst}是情绪最重的一天</div>')

    html = CANVAS_HTML_TEMPLATE.replace(
        "  <!-- WEEKLY_BARS -->", "\n".join(bars_html)
    ).replace("    <!-- SUMMARY_ITEMS -->", "\n    ".join(summary_items))

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")

    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="周情绪回顾数据统计 + Canvas HTML 生成"
    )
    parser.add_argument("diary_dir", help="diary/ 目录路径")
    parser.add_argument(
        "--format",
        choices=["json", "html"],
        default="json",
        help="输出格式：json（stdout）或 html（文件）",
    )
    parser.add_argument(
        "--output", default=None, help="HTML 输出路径（仅 --format html 时有效）"
    )
    parser.add_argument(
        "--people-dir", default=None, help="people/ 目录路径，用于人物交叉匹配"
    )
    parser.add_argument(
        "--memory-dir", default=None, help="memory/ 目录路径，读取 check-in 数据"
    )
    parser.add_argument(
        "--week", default="current", help="指定哪一周（目前仅支持 'current'）"
    )
    args = parser.parse_args()

    diary_path = Path(args.diary_dir)
    if not diary_path.exists():
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": f"Diary directory not found: {args.diary_dir}",
                }
            )
        )
        sys.exit(1)

    if args.memory_dir and not Path(args.memory_dir).exists():
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": f"Memory directory not found: {args.memory_dir}",
                }
            )
        )
        sys.exit(1)

    monday, sunday = get_this_week_range()
    diary_files = find_diary_files(args.diary_dir, monday, sunday)

    if not diary_files and not args.memory_dir:
        result = {
            "status": "no_data",
            "week": f"{monday.isoformat()} ~ {sunday.isoformat()}",
            "entries": 0,
            "emotion_summary": [],
            "repeated_themes": [],
            "growth_signals": [],
            "highlight": "",
        }
        if args.format == "html":
            result["html_generated"] = False
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)

    analysis = analyze_week(
        diary_files,
        people_dir=args.people_dir,
        memory_dir=args.memory_dir,
    )

    # 写入 weekly_cache (F10 §8.4: 完整输出供下周 cross_week_pattern 比较)
    this_week_label = iso_week_label(monday)
    write_weekly_cache(args.memory_dir, this_week_label, analysis)

    if args.format == "html":
        output_path = (
            args.output or f"/tmp/moodcoco/weekly_review_{monday.isoformat()}.html"
        )
        generate_html(analysis, output_path=output_path)
        analysis["output_path"] = output_path
        analysis["html_generated"] = True
        print(json.dumps(analysis, ensure_ascii=False, default=str))
    else:
        print(json.dumps(analysis, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
