#!/usr/bin/env python3
"""
S1 Median Runner: 跑 3 次 run_s1_v10，取各维度中位数。

消除单次跑的概率性行为对评分的影响。
每次独立运行（新 session、新用户），收集三维度分数后取中位数。

用法：
  python run_s1_median.py

输出：
  - 3 个 JSON 文件（S1_raw_v10_run1.json, run2, run3）
  - stdout 输出各维度中位数和最终结果
"""

import asyncio
import json
import os
import statistics
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from run_s1_v10 import run_s1


async def run_single(run_id: int) -> dict:
    """运行一次 S1 测试，返回 result dict。"""
    print(f"\n{'='*60}")
    print(f"  RUN {run_id}/3 开始")
    print(f"{'='*60}\n")

    result = await run_s1()

    out_path = os.path.join(SCRIPT_DIR, f"S1_raw_v10_run{run_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n  [Run {run_id}] 结果已保存到: {out_path}")
    print(f"  [Run {run_id}] 通过检查: {result['passed_checks']}/{result['total_checks']}")

    return result


def compute_functional_score(result: dict) -> float:
    """从 functional_checks 计算功能验证分数（排除 not_applicable）。"""
    checks = result.get("functional_checks", {})
    na_keys = {"xiaobo_relation_type_correct"}
    active_checks = {k: v for k, v in checks.items() if k not in na_keys}

    if not active_checks:
        return 0.0

    passed = sum(1 for v in active_checks.values() if v)
    total = len(active_checks)
    return int(passed / total * 10)


def median_of(values: list[float]) -> float:
    """计算中位数。"""
    return statistics.median(values)


async def main():
    print(f"S1 Median Runner - {datetime.now(timezone.utc).isoformat()}")
    print(f"将运行 3 次 run_s1_v10，取各维度中位数\n")

    results = []
    for i in range(1, 4):
        result = await run_single(i)
        results.append(result)

        if i < 3:
            print(f"\n  等待 5 秒后开始下一轮...\n")
            await asyncio.sleep(5)

    # ── 收集分数 ──────────────────────────────────────────────────────────────
    functional_scores = []
    for r in results:
        score = compute_functional_score(r)
        functional_scores.append(score)

    # ── 输出结果 ──────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  S1 MEDIAN RESULTS")
    print(f"{'='*60}")

    print(f"\n  功能验证（deterministic）分数:")
    for i, s in enumerate(functional_scores, 1):
        print(f"    Run {i}: {s}")
    func_median = median_of(functional_scores)
    print(f"    中位数: {func_median}")

    print(f"\n  数据正确性 & 对话质量:")
    print(f"    这两个维度由 C agent (LLM) 评估，需要把 3 个 run 的")
    print(f"    S1_raw_v10_run*.json 一起送给 C agent 评分。")
    print(f"    C agent 应对每个 run 分别打分，然后取中位数。")

    print(f"\n  各 Run 的功能检查详情:")
    for i, r in enumerate(results, 1):
        print(f"\n    Run {i}:")
        for k, v in r["functional_checks"].items():
            na = " [NOT_APPLICABLE]" if k == "xiaobo_relation_type_correct" else ""
            flag = "PASS" if v else "FAIL"
            print(f"      [{flag}] {k}{na}")
        print(f"      通过: {r['passed_checks']}/{r['total_checks']}")
        if r.get("errors"):
            print(f"      错误: {r['errors']}")

    # ── 汇总 JSON ──────────────────────────────────────────────────────────────
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runs": 3,
        "functional_scores": functional_scores,
        "functional_median": func_median,
        "note": "数据正确性和对话质量由 C agent 分别评分后取中位数",
        "raw_files": [f"S1_raw_v10_run{i}.json" for i in range(1, 4)],
    }

    summary_path = os.path.join(SCRIPT_DIR, "S1_median_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n  汇总已保存到: {summary_path}")

    print(f"\n{'='*60}")
    print(f"  FINAL: 功能验证中位数 = {func_median}")
    threshold = 8.0
    status = "PASS" if func_median >= threshold else "FAIL"
    print(f"  阈值 {threshold} → {status}")
    print(f"{'='*60}")

    return summary


if __name__ == "__main__":
    asyncio.run(main())
