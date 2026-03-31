#!/usr/bin/env python3
"""
emotion_counter.py — 会话级情绪词簇计数器

接收用户消息，匹配7大情绪词簇，维护session级计数文件。
当同一簇达到阈值时输出触发信号。

用法:
  python3 emotion_counter.py \
    --message "他又忽视我了，好烦" \
    --session-file /path/to/emotion_session.json \
    --threshold 3

输出 (JSON):
  {
    "matched_clusters": ["焦虑"],
    "session_counts": {"焦虑": 2, "委屈": 1},
    "triggered": [],
    "reflection_hint": null
  }

当某簇达到 threshold:
  {
    "matched_clusters": ["焦虑"],
    "session_counts": {"焦虑": 3},
    "triggered": ["焦虑"],
    "reflection_hint": "你好像已经不是第一次有这种感觉了"
  }
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# 7大情绪词簇定义 (与 AGENTS.md 对齐)
EMOTION_CLUSTERS = {
    "焦虑": [
        "烦", "焦虑", "崩溃", "受不了", "紧张", "慌", "不安", "心里没底",
        "焦", "烦躁", "烦死", "好烦", "慌了", "心慌", "坐不住",
        "静不下来", "总在想", "停不下来", "脑子一直转"
    ],
    "委屈": [
        "委屈", "心酸", "不被在意", "不被重视", "不重要", "被忽视", "被忽略",
        "没人在乎", "凭什么只有我", "我付出那么多", "看不到我的好",
        "我的感受不重要", "没人理解", "觉得自己付出"
    ],
    "愤怒": [
        "生气", "愤怒", "凭什么", "气死了", "火大", "烦死了",
        "太过分", "不讲理", "恶心", "受够了", "忍不了"
    ],
    "恐惧": [
        "害怕", "恐惧", "怕被丢下", "不安全", "没有安全感",
        "怕他走", "怕失去", "怕被抛弃", "不敢", "总觉得会出事"
    ],
    "悲伤": [
        "难过", "失望", "心碎", "心痛", "伤心", "想哭",
        "哭了", "眼泪", "受伤", "痛", "难受", "空了"
    ],
    "自我怀疑": [
        "是不是我的问题", "我不够好", "我太敏感", "都是我的错",
        "是不是我太", "是不是我", "我配不上", "我是不是做错了",
        "我哪里不好", "我有什么问题"
    ],
    "麻木": [
        "无感", "累了", "不想管了", "懒得理", "无所谓", "什么都不想做",
        "算了", "不想说了", "没意思", "没劲", "都行", "随便吧"
    ]
}

# 达到阈值时的反映话术 (自然语气, 不机械计数)
REFLECTION_HINTS = {
    "焦虑": [
        "你好像已经不是第一次有这种感觉了",
        "这种不安一直在，对吗？",
        "这种焦虑好像不是今天才有的"
    ],
    "委屈": [
        "这种觉得不被看见的感觉，好像一直在",
        "你说了好几次类似的话了——觉得自己的付出没人在意",
        "不被重视这件事，好像一直在你心里"
    ],
    "愤怒": [
        "你今天好几次提到气、受不了——这股火好像一直没灭",
        "这种愤怒不只是对这件事吧"
    ],
    "恐惧": [
        "你提了好几次'怕'——这种害怕好像不是今天才有的",
        "这种不安全感一直在，对吗？"
    ],
    "悲伤": [
        "你好像一直在难过的状态里，今天已经是第好几次了",
        "这种痛不是一下子来的，对吗？"
    ],
    "自我怀疑": [
        "你已经好几次说'是不是我的问题'了——你什么时候开始这样怀疑自己的？",
        "你一直在先怀疑自己——这个习惯好像不是今天才有的"
    ],
    "麻木": [
        "你说了好几次'算了''不想管了'——是真的放下了，还是太累了不想再想？",
        "这种'什么都无所谓'的感觉，好像不是真的无所谓"
    ]
}


def match_clusters(message: str) -> list[str]:
    """匹配消息中的情绪词簇, 同一消息中同簇只计一次"""
    matched = set()
    for cluster_name, keywords in EMOTION_CLUSTERS.items():
        for kw in keywords:
            if kw in message:
                matched.add(cluster_name)
                break  # 同簇匹配一个就够
    return list(matched)


def load_session(session_file: str) -> dict:
    """加载session计数文件"""
    if os.path.exists(session_file):
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"counts": {}, "history": []}


def save_session(session_file: str, data: dict):
    """保存session计数文件"""
    os.makedirs(os.path.dirname(session_file) or ".", exist_ok=True)
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_reflection(cluster: str) -> str:
    """获取反映话术"""
    import random
    hints = REFLECTION_HINTS.get(cluster, ["你好像已经不是第一次有这种感觉了"])
    return random.choice(hints)


def main():
    parser = argparse.ArgumentParser(description="会话级情绪词簇计数器")
    parser.add_argument("--message", required=True, help="用户消息文本")
    parser.add_argument("--session-file", required=True,
                        help="session级计数文件路径 (JSON)")
    parser.add_argument("--threshold", type=int, default=3,
                        help="触发模式反映的阈值 (默认3)")
    parser.add_argument("--format", default="json", choices=["json", "text"],
                        help="输出格式")
    args = parser.parse_args()

    # 1. 匹配词簇
    matched = match_clusters(args.message)

    # 2. 加载/更新session计数
    session = load_session(args.session_file)
    counts = session.get("counts", {})
    history = session.get("history", [])

    for cluster in matched:
        counts[cluster] = counts.get(cluster, 0) + 1

    # 记录历史
    history.append({
        "message_snippet": args.message[:50],
        "matched": matched
    })

    # 3. 检查是否达到阈值
    triggered = []
    reflection_hint = None
    for cluster in matched:
        if counts[cluster] >= args.threshold:
            triggered.append(cluster)
            if reflection_hint is None:
                reflection_hint = get_reflection(cluster)

    # 4. 保存session
    session["counts"] = counts
    session["history"] = history
    save_session(args.session_file, session)

    # 5. 输出结果
    result = {
        "matched_clusters": matched,
        "session_counts": counts,
        "triggered": triggered,
        "reflection_hint": reflection_hint
    }

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if triggered:
            print(f"[TRIGGER] 情绪簇 {', '.join(triggered)} 达到{args.threshold}次")
            print(f"反映提示: {reflection_hint}")
        elif matched:
            print(f"匹配: {', '.join(matched)} | 当前计数: {counts}")
        else:
            print("无情绪词簇匹配")


if __name__ == "__main__":
    main()
