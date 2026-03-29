#!/usr/bin/env python3
"""
emotion-journal 基础测试
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from journal import EmotionJournal
from crisis_detector import CrisisDetector
from pattern_tracker import PatternTracker


def test_crisis_detector():
    print("=== 测试 CrisisDetector ===")
    detector = CrisisDetector()
    cases = [
        ("今天心情不错", False, None),
        ("工作压力好大", False, None),
        ("活着没意思", True, "suicide"),
        ("想伤害自己", True, "self_harm"),
        ("坚持不住了", True, "breakdown"),
        ("彻底崩溃了", True, "breakdown"),
        ("活着太累了", True, "suicide"),
    ]
    passed = 0
    for text, exp_crisis, exp_type in cases:
        r = detector.detect(text)
        ok = r["has_crisis"] == exp_crisis
        if ok and exp_type:
            ok = r["type"] == exp_type
        print(f"{'✅' if ok else '❌'} {text!r} -> crisis={r['has_crisis']}, type={r['type']}")
        if ok:
            passed += 1
    print(f"\n通过: {passed}/{len(cases)}\n")
    return passed == len(cases)


def test_journal_flow():
    print("=== 测试 EmotionJournal 流程 ===")
    journal = EmotionJournal()
    inputs = [
        "今天在公司和领导吵架了",
        "很生气",
        "8",
        "觉得他不公平",
        "我忍住了没说话",
        "可能是因为上次顶撞过他",
    ]
    phase_sequence = []
    for inp in inputs:
        r = journal.process_input(inp)
        phase_sequence.append(r["phase"])
        print(f"  输入: {inp[:30]!r} -> phase={r['phase']}, step={r['step']}")

    print(f"\n流程序列: {' -> '.join(phase_sequence)}")
    # 最后应该是 summary
    ok = phase_sequence[-1] == "summary"
    print(f"{'✅' if ok else '❌'} 流程完成状态: {'正确' if ok else '错误'}\n")
    return ok


def test_crisis_interrupts_journal():
    print("=== 测试危机中断日志流程 ===")
    journal = EmotionJournal()
    # 开始记录
    journal.process_input("今天加班到很晚")
    # 突然出现危机信号
    r = journal.process_input("活着没意思")
    ok = r["phase"] == "crisis" and r["crisis_result"]["type"] == "suicide"
    print(f"{'✅' if ok else '❌'} 危机信号中断流程: phase={r['phase']}, crisis={r['crisis_result']['type']}\n")
    return ok


def test_pattern_tracker():
    print("=== 测试 PatternTracker ===")
    tracker = PatternTracker([
        {"emotion": "愤怒", "intensity": "8", "trigger": "工作压力"},
        {"emotion": "焦虑", "intensity": "6", "trigger": "人际关系"},
        {"emotion": "愤怒", "intensity": "7", "trigger": "工作压力"},
    ])
    report = tracker.get_pattern_report()
    ok = "愤怒" in report and "工作压力" in report
    print(f"{'✅' if ok else '❌'} 模式报告生成: {'正确' if ok else '错误'}")
    print(f"  报告片段: {report[:80]}...\n")
    return ok


def test_file_structure():
    print("=== 测试文件结构 ===")
    base = os.path.dirname(os.path.dirname(__file__))
    required = ["SKILL.md", "skill.json", "scripts/journal.py",
                "scripts/crisis_detector.py", "scripts/pattern_tracker.py",
                "references/journey_prompts.json", "references/crisis_keywords.json"]
    passed = 0
    for f in required:
        path = os.path.join(base, f)
        exists = os.path.exists(path)
        print(f"{'✅' if exists else '❌'} {f}")
        if exists:
            passed += 1
    print(f"\n通过: {passed}/{len(required)}\n")
    return passed == len(required)


def main():
    results = [
        ("文件结构", test_file_structure()),
        ("危机检测", test_crisis_detector()),
        ("日记流程", test_journal_flow()),
        ("危机中断", test_crisis_interrupts_journal()),
        ("模式追踪", test_pattern_tracker()),
    ]
    print("=" * 50)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")
    all_ok = all(r[1] for r in results)
    print(f"\n总体: {'✅ 全部通过' if all_ok else '❌ 存在问题'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
