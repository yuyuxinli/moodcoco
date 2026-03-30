"""
weekly_review.py — 周情绪回顾数据统计 + Canvas HTML 生成

读取本周 diary/*.md，统计情绪词频、关联人物、触发因素，
输出 JSON（供 agent 解析）或 HTML（供 Canvas 展示）。

设计参考：
- docs/product/product-experience-design.md F02 §2.1 卡片 A
- docs/technical/implementation-plan.md §Step 7

用法（由 AI agent 通过 exec 调用）：
    python3 weekly_review.py <diary_dir> [--format json|html] [--output <path>] [--people-dir <path>]

    --format json  输出 JSON 到 stdout（默认）
    --format html  生成 Canvas HTML 文件

只用 Python 标准库（无 PIL / matplotlib 依赖）。
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# 情绪语义分组（与 SKILL.md / AGENTS.md 情绪词簇对齐）
# ---------------------------------------------------------------------------

EMOTION_CLUSTERS = {
    "焦虑": ["焦虑", "紧张", "担心", "不安", "慌", "烦", "崩溃", "受不了", "心里没底"],
    "悲伤": ["难过", "伤心", "低落", "沮丧", "失落", "委屈", "心碎", "心痛", "想哭", "失望", "心酸"],
    "愤怒": ["生气", "愤怒", "烦躁", "恼火", "不爽", "凭什么", "气死了", "火大", "烦死了"],
    "开心": ["开心", "高兴", "还不错", "愉快", "满足", "快乐", "幸福"],
    "疲惫": ["累", "疲惫", "有点累", "倦", "心累", "好累"],
    "平静": ["平静", "一般", "还行", "中性", "无感", "还好"],
    "恐惧": ["害怕", "恐惧", "怕被丢下", "不安全", "没有安全感"],
    "自我怀疑": ["是不是我的问题", "我不够好", "我太敏感了", "都是我的错"],
    "麻木": ["无感", "累了", "不想管了", "懒得理", "无所谓", "什么都不想做"],
}

# 反向映射：词 → 簇名
WORD_TO_CLUSTER = {}
for cluster_name, words in EMOTION_CLUSTERS.items():
    for w in words:
        WORD_TO_CLUSTER[w] = cluster_name

# 情绪色板（与 F02 §2.1 设计语言暖色系对齐）
CLUSTER_COLORS = {
    "焦虑": "#FFB74D",   # 杏黄
    "悲伤": "#90CAF9",   # 淡蓝
    "愤怒": "#FF7F7F",   # 珊瑚
    "开心": "#A8E6CF",   # 薄荷
    "疲惫": "#D7CCC8",   # 暖灰
    "平静": "#C5E1A5",   # 淡绿
    "恐惧": "#C5A3FF",   # 薰衣草
    "自我怀疑": "#FFCC80",  # 浅橙
    "麻木": "#BDBDBD",   # 灰
}

# 正面 / 负面分类（决定色块冷暖）
POSITIVE_CLUSTERS = {"开心", "平静"}
NEGATIVE_CLUSTERS = {"焦虑", "悲伤", "愤怒", "恐惧", "自我怀疑"}
NEUTRAL_CLUSTERS = {"疲惫", "麻木"}

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


# ---------------------------------------------------------------------------
# Diary Parsing
# ---------------------------------------------------------------------------

def get_this_week_range() -> tuple:
    """返回本周一和周日的日期。"""
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def find_diary_files(diary_dir: str, start_date, end_date) -> list:
    """在 diary/ 目录下找到指定日期范围的 md 文件。

    支持两种目录结构：
    - diary/YYYY/MM/YYYY-MM-DD.md
    - diary/YYYY-MM-DD.md
    """
    diary_path = Path(diary_dir)
    files = []

    current = start_date
    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        # 尝试嵌套路径
        nested = diary_path / current.strftime("%Y") / current.strftime("%m") / f"{date_str}.md"
        flat = diary_path / f"{date_str}.md"

        if nested.exists():
            files.append((current, nested))
        elif flat.exists():
            files.append((current, flat))

        current += timedelta(days=1)

    return files


def parse_diary_entry(filepath: Path) -> dict:
    """解析单个日记文件，提取情绪词、人物和触发因素。"""
    text = filepath.read_text(encoding="utf-8")
    result = {
        "emotions": [],
        "people": [],
        "triggers": [],
        "summary": "",
    }

    current_section = None
    for line in text.split("\n"):
        stripped = line.strip()

        # 检测 section headers
        if re.match(r"^#+\s*情绪|^#+\s*心情|^#+\s*feeling", stripped, re.IGNORECASE):
            current_section = "emotion"
            continue
        elif re.match(r"^#+\s*人物|^#+\s*关联|^#+\s*people|^#+\s*关系", stripped, re.IGNORECASE):
            current_section = "people"
            continue
        elif re.match(r"^#+\s*触发|^#+\s*trigger|^#+\s*原因|^#+\s*因为", stripped, re.IGNORECASE):
            current_section = "trigger"
            continue
        elif re.match(r"^#+\s*摘要|^#+\s*summary|^#+\s*记录", stripped, re.IGNORECASE):
            current_section = "summary"
            continue
        elif re.match(r"^#+\s", stripped):
            current_section = None

        if not stripped or stripped.startswith("---"):
            continue

        # 提取情绪关键词（从全文扫描）
        for word, cluster in WORD_TO_CLUSTER.items():
            if word in stripped:
                result["emotions"].append(word)

        # 按 section 提取结构化数据
        if current_section == "people":
            # 提取列表项中的人名
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

    return result


def cross_check_people(people_mentioned: list, people_dir: str) -> list:
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
# Analysis
# ---------------------------------------------------------------------------

def analyze_week(diary_files: list, people_dir: str = None) -> dict:
    """分析本周日记数据。"""
    monday, sunday = get_this_week_range()

    daily = {}
    all_emotions = []
    all_people = []
    all_triggers = []

    for date, filepath in diary_files:
        entry = parse_diary_entry(filepath)
        weekday_idx = date.weekday()
        day_key = WEEKDAY_NAMES[weekday_idx]

        # 去重同日同簇情绪
        day_clusters_seen = set()
        day_emotions = []
        for emo in entry["emotions"]:
            cluster = WORD_TO_CLUSTER.get(emo, emo)
            if cluster not in day_clusters_seen:
                day_clusters_seen.add(cluster)
                day_emotions.append(emo)

        daily[day_key] = {
            "date": date.isoformat(),
            "emotions": day_emotions,
            "primary_emotion": day_emotions[0] if day_emotions else "无记录",
            "primary_cluster": WORD_TO_CLUSTER.get(day_emotions[0], "平静") if day_emotions else None,
            "people": entry["people"],
            "triggers": entry["triggers"],
            "summary": entry["summary"],
        }

        all_emotions.extend(day_emotions)
        all_people.extend(entry["people"])
        all_triggers.extend(entry["triggers"])

    # 情绪统计（按簇聚合）
    cluster_counts = Counter()
    for emo in all_emotions:
        cluster = WORD_TO_CLUSTER.get(emo, emo)
        cluster_counts[cluster] += 1

    # 人物统计
    people_counts = Counter(all_people)
    if people_dir:
        people_counts = Counter(cross_check_people(all_people, people_dir))

    # 触发统计
    trigger_counts = Counter(all_triggers)

    # 找情绪最重的一天
    worst_day = None
    worst_score = 0
    for day_name, day_data in daily.items():
        neg_count = sum(1 for e in day_data["emotions"]
                        if WORD_TO_CLUSTER.get(e, "") in NEGATIVE_CLUSTERS)
        if neg_count > worst_score:
            worst_score = neg_count
            worst_day = day_name

    # 跨周重复检测（cross_week_pattern 标记）
    top_emotion = cluster_counts.most_common(1)[0] if cluster_counts else None
    top_person = people_counts.most_common(1)[0] if people_counts else None

    return {
        "week_start": monday.isoformat(),
        "week_end": sunday.isoformat(),
        "diary_count": len(diary_files),
        "daily": daily,
        "emotion_summary": dict(cluster_counts.most_common()),
        "top_emotion": {"name": top_emotion[0], "count": top_emotion[1]} if top_emotion else None,
        "people_summary": dict(people_counts.most_common()),
        "top_person": {"name": top_person[0], "count": top_person[1]} if top_person else None,
        "trigger_summary": dict(trigger_counts.most_common()),
        "worst_day": worst_day,
        "cross_week_pattern": {
            "detected": False,
            "details": None,
        },
    }


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


def generate_html(analysis: dict, output_path: str = None) -> str:
    """生成周情绪地图 Canvas HTML。"""

    daily = analysis.get("daily", {})

    # 生成每天的色块行
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

            # 如果有人物和触发，附在后面
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
    <div class="emotion-bar" style="width: {width}%; background: {color};" title="{', '.join(day_data.get('emotions', []))}">
      <span class="bar-text">{emotion_text}{extra}</span>
    </div>
  </div>""")

    # 生成摘要
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
        summary_items.append(
            f'<div class="summary-item">{worst}是情绪最重的一天</div>'
        )

    # 组装 HTML
    html = CANVAS_HTML_TEMPLATE.replace(
        "  <!-- WEEKLY_BARS -->",
        "\n".join(bars_html)
    ).replace(
        "    <!-- SUMMARY_ITEMS -->",
        "\n    ".join(summary_items)
    )

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")

    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="周情绪回顾数据统计 + Canvas HTML 生成")
    parser.add_argument("diary_dir", help="diary/ 目录路径")
    parser.add_argument("--format", choices=["json", "html"], default="json",
                        help="输出格式：json（stdout）或 html（文件）")
    parser.add_argument("--output", default=None,
                        help="HTML 输出路径（仅 --format html 时有效）")
    parser.add_argument("--people-dir", default=None,
                        help="people/ 目录路径，用于人物交叉匹配")
    args = parser.parse_args()

    diary_path = Path(args.diary_dir)
    if not diary_path.exists():
        print(json.dumps({"status": "error", "error": f"Diary directory not found: {args.diary_dir}"}))
        sys.exit(1)

    monday, sunday = get_this_week_range()
    diary_files = find_diary_files(args.diary_dir, monday, sunday)

    if not diary_files:
        result = {
            "status": "ok",
            "diary_count": 0,
            "week_start": monday.isoformat(),
            "week_end": sunday.isoformat(),
            "message": "本周暂无日记记录",
        }
        if args.format == "html":
            result["html_generated"] = False
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)

    analysis = analyze_week(diary_files, people_dir=args.people_dir)

    if args.format == "html":
        output_path = args.output or f"/tmp/moodcoco/weekly_review_{monday.isoformat()}.html"
        generate_html(analysis, output_path=output_path)
        result = {
            "status": "ok",
            "output_path": output_path,
            "html_generated": True,
        }
        result.update(analysis)
        print(json.dumps(result, ensure_ascii=False, default=str))
    else:
        analysis["status"] = "ok"
        print(json.dumps(analysis, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
