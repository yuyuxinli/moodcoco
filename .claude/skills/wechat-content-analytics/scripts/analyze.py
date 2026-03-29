#!/usr/bin/env python3
"""WeChat Public Account Article Analytics

Parses WeChat backend XLS exports, calculates KPIs, scores articles,
diagnoses bottlenecks, and outputs a JSON report.

Usage:
    python analyze.py file1.xls [file2.xls ...] [--output report.json]
"""

import sys
import json
import argparse
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("Error: pandas required. Install: pip install pandas", file=sys.stderr)
    sys.exit(1)

try:
    import xlrd  # noqa: F401
except ImportError:
    print("Error: xlrd required. Install: pip install xlrd", file=sys.stderr)
    sys.exit(1)


def parse_xls(filepath: str) -> dict:
    """Parse a single WeChat backend XLS export into structured data."""
    df = pd.read_excel(filepath, header=None)
    col_b = df.iloc[:, 1]
    col_c = df.iloc[:, 2]
    col_d = df.iloc[:, 3] if df.shape[1] > 3 else pd.Series([None] * len(df))

    title = str(col_b.iloc[0]).strip() if pd.notna(col_b.iloc[0]) else Path(filepath).stem

    # Build key-value pairs from column B-C
    kv = {}
    for i in range(len(df)):
        key = str(col_b.iloc[i]).strip() if pd.notna(col_b.iloc[i]) else ""
        val = col_c.iloc[i]
        if key and pd.notna(val) and key not in ("数据指标", "数值", "nan"):
            kv[key] = val

    # Extract overview metrics
    def get_num(k, default=0):
        v = kv.get(k, default)
        if isinstance(v, str):
            v = v.replace("%", "").replace(",", "")
            try:
                return float(v)
            except ValueError:
                return default
        try:
            return float(v)
        except (ValueError, TypeError):
            return default

    overview = {
        "reads": int(get_num("阅读(人)")),
        "dwell_seconds": int(get_num("平均停留时长(秒)")),
        "completion_rate": None,
        "follows": int(get_num("阅读后关注（人）")),
        "shares": int(get_num("分享(人)")),
        "watching": int(get_num("在看(人)")),
        "likes": int(get_num("点赞(人)")),
        "bookmarks": int(get_num("收藏(人)")),
        "tips": int(get_num("赞赏(分)")),
        "comments": int(get_num("评论（条）")),
    }

    # Completion rate may or may not exist
    cr = kv.get("完读率")
    if cr is not None:
        cr_val = get_num("完读率")
        overview["completion_rate"] = cr_val if cr_val <= 1 else cr_val / 100

    conversion = {
        "delivered": int(get_num("送达人数")),
        "push_reads": int(get_num("公众号消息阅读人数")),
        "first_shares": int(get_num("首次分享人数")),
        "total_shares": int(get_num("总分享人数")),
        "share_reads": int(get_num("分享产生的阅读人数")),
    }

    # Parse daily channel data
    daily = []
    in_trend = False
    for i in range(len(df)):
        b = str(col_b.iloc[i]).strip() if pd.notna(col_b.iloc[i]) else ""
        if "数据趋势明细" in b:
            in_trend = True
            continue
        if in_trend and b == "日期":
            continue  # header row
        if in_trend and b and b[0:2] == "20":  # date like 2026-xx-xx
            channel = str(col_c.iloc[i]).strip() if pd.notna(col_c.iloc[i]) else ""
            reads = int(float(col_d.iloc[i])) if pd.notna(col_d.iloc[i]) else 0
            daily.append({"date": b, "channel": channel, "reads": reads})
        elif in_trend and ("性别" in b or "分布" in b):
            in_trend = False

    # Determine publish date from first "全部" entry
    publish_date = None
    for d in daily:
        if d["channel"] == "全部":
            publish_date = d["date"]
            break

    # Parse demographics
    demographics = {"gender": {}, "age": {}, "region": {}}
    section = None
    for i in range(len(df)):
        b = str(col_b.iloc[i]).strip() if pd.notna(col_b.iloc[i]) else ""
        c = str(col_c.iloc[i]).strip() if pd.notna(col_c.iloc[i]) else ""
        if "性别分布" in b:
            section = "gender"
            continue
        elif "年龄分布" in b:
            section = "age"
            continue
        elif "地域分布" in b:
            section = "region"
            continue
        if section and b in ("性别", "年龄", "省份/直辖市", "占比"):
            continue
        if section and b and c and "%" in c:
            pct = float(c.replace("%", ""))
            demographics[section][b] = pct
        elif section and b and not c:
            section = None

    return {
        "title": title,
        "publish_date": publish_date,
        "filepath": str(filepath),
        "overview": overview,
        "conversion": conversion,
        "daily": daily,
        "demographics": demographics,
    }


def calculate_kpis(article: dict) -> dict:
    """Calculate derived KPIs from raw metrics."""
    o = article["overview"]
    c = article["conversion"]
    reads = o["reads"] or 1  # avoid division by zero

    kpis = {}

    # Engagement rate
    interactions = o["likes"] + o["watching"] + o["bookmarks"] + o["comments"]
    kpis["engagement_rate"] = round(interactions / reads * 100, 2)

    # Share rate
    kpis["share_rate"] = round(o["shares"] / reads * 100, 2)

    # Follow conversion rate
    kpis["follow_rate"] = round(o["follows"] / reads * 100, 2)

    # Viral coefficient
    kpis["viral_coefficient"] = round(c["share_reads"] / reads * 100, 1) if reads else 0

    # Push open rate
    kpis["push_open_rate"] = round(c["push_reads"] / c["delivered"] * 100, 1) if c["delivered"] else None

    # Share efficiency
    kpis["share_efficiency"] = round(c["share_reads"] / o["shares"], 1) if o["shares"] else 0

    # Completion rate (pass through)
    kpis["completion_rate"] = round(o["completion_rate"] * 100, 1) if o["completion_rate"] is not None else None

    # Channel mix
    daily = article["daily"]
    total_by_channel = {}
    for d in daily:
        if d["channel"] != "全部":
            total_by_channel[d["channel"]] = total_by_channel.get(d["channel"], 0) + d["reads"]
    total_channel_reads = sum(total_by_channel.values()) or 1
    kpis["channel_mix"] = {k: round(v / total_channel_reads * 100, 1) for k, v in
                           sorted(total_by_channel.items(), key=lambda x: -x[1])}

    # Recommendation traffic percentage
    kpis["recommendation_pct"] = kpis["channel_mix"].get("推荐", 0)

    return kpis


def score_dimension(value, thresholds):
    """Score a value 0-4 based on threshold list [t1, t2, t3, t4]."""
    if value is None:
        return None
    for i, t in enumerate(thresholds):
        if value < t:
            return i
    return 4


def score_article(kpis: dict) -> dict:
    """Score an article across 5 dimensions."""
    dimensions = {
        "传播力": {
            "weight": 0.30,
            "metric": "share_rate",
            "thresholds": [1, 3, 5, 10],
            "unit": "%",
        },
        "互动力": {
            "weight": 0.25,
            "metric": "engagement_rate",
            "thresholds": [1, 3, 5, 8],
            "unit": "%",
        },
        "触达力": {
            "weight": 0.20,
            "metric": "push_open_rate",
            "thresholds": [2, 5, 10, 20],
            "unit": "%",
        },
        "深度": {
            "weight": 0.15,
            "metric": "completion_rate",
            "thresholds": [20, 35, 50, 65],
            "unit": "%",
        },
        "增长力": {
            "weight": 0.10,
            "metric": "follow_rate",
            "thresholds": [0.5, 1, 2, 5],
            "unit": "%",
        },
    }

    scores = {}
    weighted_total = 0
    total_weight = 0

    for name, dim in dimensions.items():
        value = kpis.get(dim["metric"])
        s = score_dimension(value, dim["thresholds"])
        scores[name] = {
            "score": s,
            "value": value,
            "weight": dim["weight"],
            "unit": dim["unit"],
        }
        if s is not None:
            weighted_total += s * dim["weight"]
            total_weight += dim["weight"]

    overall = round(weighted_total / total_weight * 4 / 4, 2) if total_weight else 0
    # Normalize to 0-4 scale
    overall = round(weighted_total / total_weight, 2) if total_weight else 0

    if overall >= 3.5:
        rating = "Exceptional"
        rating_cn = "卓越"
    elif overall >= 2.5:
        rating = "Strong"
        rating_cn = "优秀"
    elif overall >= 1.5:
        rating = "Average"
        rating_cn = "一般"
    else:
        rating = "Weak"
        rating_cn = "不足"

    return {
        "dimensions": scores,
        "overall": overall,
        "rating": rating,
        "rating_cn": rating_cn,
    }


def diagnose(kpis: dict) -> dict:
    """Run diagnostic decision tree."""
    bottlenecks = []
    strengths = []

    share_rate = kpis.get("share_rate", 0)
    engagement_rate = kpis.get("engagement_rate", 0)
    completion_rate = kpis.get("completion_rate")
    follow_rate = kpis.get("follow_rate", 0)
    share_efficiency = kpis.get("share_efficiency", 0)
    recommendation_pct = kpis.get("recommendation_pct", 0)

    # Strengths
    if engagement_rate >= 5:
        strengths.append("互动率优秀 ({}%)，内容引发共鸣".format(engagement_rate))
    if share_rate >= 3:
        strengths.append("分享率达标 ({}%)，内容有社交传播力".format(share_rate))
    if follow_rate >= 2:
        strengths.append("关注转化率高 ({}%)，账号定位与内容匹配".format(follow_rate))
    if share_efficiency >= 20:
        strengths.append("分享效率极高 ({} 人/次)，读者社交圈质量高".format(share_efficiency))
    if completion_rate is not None and completion_rate >= 50:
        strengths.append("完读率达标 ({}%)，内容节奏好".format(completion_rate))

    # Bottlenecks (priority order)
    if share_rate < 3:
        bottlenecks.append({
            "dimension": "传播力",
            "symptom": "分享率 {}% < 3%".format(share_rate),
            "cause": "内容缺乏社交货币 — 读者读完觉得好但不觉得需要转发",
            "actions": [
                "加入可截图分享的金句/框架/清单",
                "让分享者获得社交收益（显得聪明/有品味/有爱心）",
                "文末加入明确的分享引导 CTA",
            ],
        })

    if engagement_rate < 3:
        bottlenecks.append({
            "dimension": "互动力",
            "symptom": "互动率 {}% < 3%".format(engagement_rate),
            "cause": "内容被消费但未引发情绪共鸣",
            "actions": [
                "精准命名读者的感受（'说出了我的心声'效应）",
                "设计明确的情绪峰值（一篇文章至少一个'泪点'或'哈哈'时刻）",
                "在看/点赞按钮前放置情绪触发段落",
            ],
        })

    if completion_rate is not None and completion_rate < 35:
        bottlenecks.append({
            "dimension": "深度",
            "symptom": "完读率 {}% < 35%".format(completion_rate),
            "cause": "内容留不住人 — 开头钩子弱或中间冗长",
            "actions": [
                "前3句制造信息缺口/悬念/共鸣",
                "每300字设置一个小转折或新信息",
                "总字数控制在1500-2500",
            ],
        })

    if follow_rate < 1:
        bottlenecks.append({
            "dimension": "增长力",
            "symptom": "关注转化率 {}% < 1%".format(follow_rate),
            "cause": "文章好但与账号持续价值脱节 — 读者不觉得需要长期关注",
            "actions": [
                "文末强化账号价值主张（'我们每周分享 XX'）",
                "预告下期具体内容，制造期待",
                "在文中自然植入账号人格/风格特征",
            ],
        })

    if recommendation_pct < 5:
        bottlenecks.append({
            "dimension": "推荐流量",
            "symptom": "推荐流量占比 {}% < 5%".format(recommendation_pct),
            "cause": "内容未进入微信推荐流量池",
            "actions": [
                "提升完读率和互动率（算法核心信号）",
                "使用微信搜一搜热门话题关键词",
                "保持稳定更新频率（算法偏好活跃账号）",
            ],
        })

    # If no bottlenecks found
    if not bottlenecks:
        bottlenecks.append({
            "dimension": "无明显瓶颈",
            "symptom": "各项指标均达标",
            "cause": "内容表现良好",
            "actions": ["复制此类内容模式", "尝试提升发布频率扩大影响"],
        })

    return {
        "strengths": strengths,
        "bottlenecks": bottlenecks,
        "primary_bottleneck": bottlenecks[0]["dimension"] if bottlenecks else None,
    }


def generate_trend(articles: list) -> dict:
    """Generate cross-article trend analysis if 2+ articles."""
    if len(articles) < 2:
        return {"available": False}

    sorted_articles = sorted(articles, key=lambda a: a["publish_date"] or "")
    metrics_over_time = []
    for a in sorted_articles:
        metrics_over_time.append({
            "title": a["title"],
            "date": a["publish_date"],
            "reads": a["overview"]["reads"],
            "shares": a["overview"]["shares"],
            "follows": a["overview"]["follows"],
            "engagement_rate": a["kpis"]["engagement_rate"],
            "share_rate": a["kpis"]["share_rate"],
            "follow_rate": a["kpis"]["follow_rate"],
            "viral_coefficient": a["kpis"]["viral_coefficient"],
            "share_efficiency": a["kpis"]["share_efficiency"],
        })

    # Detect trends
    trends = {}
    for metric in ["reads", "shares", "engagement_rate", "share_rate", "follow_rate"]:
        values = [m[metric] for m in metrics_over_time]
        if len(values) >= 2:
            if all(values[i] >= values[i + 1] for i in range(len(values) - 1)):
                trends[metric] = "declining"
            elif all(values[i] <= values[i + 1] for i in range(len(values) - 1)):
                trends[metric] = "improving"
            else:
                trends[metric] = "fluctuating"

    return {
        "available": True,
        "metrics_over_time": metrics_over_time,
        "trends": trends,
    }


def main():
    parser = argparse.ArgumentParser(description="WeChat Content Analytics")
    parser.add_argument("files", nargs="+", help="XLS files from WeChat backend")
    parser.add_argument("--output", "-o", default=None, help="Output JSON path (default: stdout)")
    args = parser.parse_args()

    articles = []
    for f in args.files:
        try:
            article = parse_xls(f)
            article["kpis"] = calculate_kpis(article)
            article["score"] = score_article(article["kpis"])
            article["diagnosis"] = diagnose(article["kpis"])
            articles.append(article)
        except Exception as e:
            print(f"Error parsing {f}: {e}", file=sys.stderr)
            continue

    # Sort by publish date
    articles.sort(key=lambda a: a["publish_date"] or "")

    # Generate cross-article trend
    trend = generate_trend(articles)

    report = {
        "article_count": len(articles),
        "articles": articles,
        "trend": trend,
    }

    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report saved to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
