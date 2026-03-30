#!/usr/bin/env python3
"""
危机检测器 - 检测用户输入中的危机信号并触发专业转介
emotion-journal skill 模块
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CrisisDetector:
    crisis_data: dict[str, Any]

    def __init__(self) -> None:
        self.crisis_data = self._load_crisis_data()

    def _load_crisis_data(self) -> dict[str, Any]:
        """加载危机关键词数据"""
        refs_path = Path(__file__).parent.parent / "references" / "crisis_keywords.json"
        with refs_path.open(encoding="utf-8") as f:
            result: dict[str, Any] = json.load(f)
            return result

    def detect(self, text: str) -> dict[str, Any]:
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
        text_lower: str = text.lower()
        crisis_signals: dict[str, Any] = self.crisis_data.get("crisis_signals", {})

        results: dict[str, Any] = {
            "has_crisis": False,
            "level": None,
            "type": None,
            "matched_keywords": [],
            "response": None,
        }

        # 优先级：自杀 > 自伤 > 崩溃
        suicide_kw: list[str] = crisis_signals.get("suicide", [])
        matched: list[str] = [kw for kw in suicide_kw if kw in text_lower]
        if matched:
            results.update(
                {
                    "has_crisis": True,
                    "level": "high",
                    "type": "suicide",
                    "matched_keywords": matched,
                }
            )
        else:
            self_harm_kw: list[str] = crisis_signals.get("self_harm", [])
            matched = [kw for kw in self_harm_kw if kw in text_lower]
            if matched:
                results.update(
                    {
                        "has_crisis": True,
                        "level": "high",
                        "type": "self_harm",
                        "matched_keywords": matched,
                    }
                )
            else:
                breakdown_kw: list[str] = crisis_signals.get("severe_breakdown", [])
                matched = [kw for kw in breakdown_kw if kw in text_lower]
                if matched:
                    results.update(
                        {
                            "has_crisis": True,
                            "level": "medium",
                            "type": "breakdown",
                            "matched_keywords": matched,
                        }
                    )

        if results["has_crisis"]:
            results["response"] = self._generate_response(results["type"])

        return results

    def _generate_response(self, crisis_type: str | None) -> str:
        """生成危机响应话术"""
        templates: dict[str, Any] = self.crisis_data.get("response_templates", {})
        resources: dict[str, Any] = self.crisis_data.get("professional_resources", {})
        hotline: str = resources.get("national_hotline", "400-161-9995")

        parts: list[str] = [
            templates.get("immediate", ""),
            templates.get("hotline", "").replace("400-161-9995", f"**{hotline}**"),
            templates.get("local", ""),
            templates.get("emergency", ""),
            templates.get("closing", ""),
        ]
        return "\n\n".join([p for p in parts if p])

    def should_escalate(self, text: str) -> bool:
        """判断是否需要升级转介"""
        result: bool = self.detect(text).get("has_crisis", False)
        return result


if __name__ == "__main__":
    detector = CrisisDetector()
    test_cases: list[str] = [
        "我今天心情不好",
        "工作压力好大",
        "活着没意思",
        "想伤害自己",
        "坚持不住了",
    ]
    print("=== CrisisDetector Tests ===\n")
    for text in test_cases:
        r: dict[str, Any] = detector.detect(text)
        print(f"Input: {text}")
        print(f"  has_crisis={r['has_crisis']}, level={r['level']}, type={r['type']}")
        if r["response"]:
            print(f"  response: {r['response'][:60]}...")
        print()
