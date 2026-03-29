#!/usr/bin/env python3
"""
危机检测器 - 检测用户输入中的危机信号并触发专业转介
emotion-journal skill 模块
"""

import json
import re
from pathlib import Path


class CrisisDetector:
    def __init__(self):
        self.crisis_data = self._load_crisis_data()

    def _load_crisis_data(self) -> dict:
        """加载危机关键词数据"""
        refs_path = Path(__file__).parent.parent / "references" / "crisis_keywords.json"
        with open(refs_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def detect(self, text: str) -> dict:
        """
        检测文本中的危机信号

        Returns:
            dict: {
                "has_crisis": bool,
                "level": "high" | "medium" | None,
                "type": "suicide" | "self_harm" | "breakdown" | None,
                "matched_keywords": list,
                "response": str
            }
        """
        text_lower = text.lower()
        crisis_signals = self.crisis_data.get("crisis_signals", {})

        results = {
            "has_crisis": False,
            "level": None,
            "type": None,
            "matched_keywords": [],
            "response": None
        }

        # 优先级：自杀 > 自伤 > 崩溃
        suicide_kw = crisis_signals.get("suicide", [])
        matched = [kw for kw in suicide_kw if kw in text_lower]
        if matched:
            results.update({"has_crisis": True, "level": "high", "type": "suicide", "matched_keywords": matched})
        else:
            self_harm_kw = crisis_signals.get("self_harm", [])
            matched = [kw for kw in self_harm_kw if kw in text_lower]
            if matched:
                results.update({"has_crisis": True, "level": "high", "type": "self_harm", "matched_keywords": matched})
            else:
                breakdown_kw = crisis_signals.get("severe_breakdown", [])
                matched = [kw for kw in breakdown_kw if kw in text_lower]
                if matched:
                    results.update({"has_crisis": True, "level": "medium", "type": "breakdown", "matched_keywords": matched})

        if results["has_crisis"]:
            results["response"] = self._generate_response(results["type"])

        return results

    def _generate_response(self, crisis_type: str) -> str:
        """生成危机响应话术"""
        templates = self.crisis_data.get("response_templates", {})
        resources = self.crisis_data.get("professional_resources", {})
        hotline = resources.get("national_hotline", "400-161-9995")

        parts = [
            templates.get("immediate", ""),
            templates.get("hotline", "").replace("400-161-9995", f"**{hotline}**"),
            templates.get("local", ""),
            templates.get("emergency", ""),
            templates.get("closing", ""),
        ]
        return "\n\n".join([p for p in parts if p])

    def should_escalate(self, text: str) -> bool:
        """判断是否需要升级转介"""
        return self.detect(text).get("has_crisis", False)


if __name__ == "__main__":
    detector = CrisisDetector()
    test_cases = [
        "我今天心情不好",
        "工作压力好大",
        "活着没意思",
        "想伤害自己",
        "坚持不住了",
    ]
    print("=== CrisisDetector Tests ===\n")
    for text in test_cases:
        r = detector.detect(text)
        print(f"Input: {text}")
        print(f"  has_crisis={r['has_crisis']}, level={r['level']}, type={r['type']}")
        if r['response']:
            print(f"  response: {r['response'][:60]}...")
        print()
