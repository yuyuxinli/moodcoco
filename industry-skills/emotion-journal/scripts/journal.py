#!/usr/bin/env python3
"""
情绪日记核心逻辑 - emotion-journal skill 核心模块
引导用户完成结构化情绪记录，不做诊断，只做自我观察支持
"""

import json
from pathlib import Path
from typing import Optional
try:
    from .crisis_detector import CrisisDetector
except ImportError:
    from crisis_detector import CrisisDetector


class EmotionJournal:
    """
    情绪日记引导器

    流程：
    1. 先做危机检测（任何时候发现危机信号立即转介）
    2. 引导用户逐步完成日记结构
    3. 生成结构化摘要
    4. 给出一个小的后续行动建议
    """

    def __init__(self):
        self.crisis = CrisisDetector()
        self.prompts = self._load_prompts()
        self._reset_session()

    def _load_prompts(self) -> dict:
        refs_path = Path(__file__).parent.parent / "references" / "journey_prompts.json"
        with open(refs_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _reset_session(self):
        self.current_step = 0
        self.record = {
            "event": None,
            "emotion": None,
            "intensity": None,
            "thought": None,
            "action": None,
            "trigger": None,
        }
        self.step_history = []

    def check_crisis(self, text: str) -> Optional[dict]:
        """检测危机信号，返回结果或None"""
        return self.crisis.detect(text)

    def get_next_prompt(self) -> str:
        """获取下一步的引导问题"""
        steps = self.prompts.get("journal_steps", [])
        if self.current_step >= len(steps):
            return None
        step = steps[self.current_step]
        return f"[{step['step']}/{len(steps)}] {step['question']}"

    def process_input(self, text: str) -> dict:
        """
        处理用户输入，返回引导结果

        Returns:
            dict: {
                "phase": "crisis" | "prompt" | "summary" | "done",
                "content": str,
                "crisis_result": dict | None,
                "step": int,
                "record": dict
            }
        """
        # 1. 危机检测
        crisis_result = self.crisis.detect(text)
        if crisis_result["has_crisis"]:
            return {
                "phase": "crisis",
                "content": crisis_result["response"],
                "crisis_result": crisis_result,
                "step": self.current_step,
                "record": self.record,
            }

        # 2. 正常记录流程
        steps = self.prompts.get("journal_steps", [])
        if self.current_step >= len(steps):
            return self._generate_summary()

        field = steps[self.current_step]["field"]
        self.record[field] = text
        self.step_history.append({"step": self.current_step, "field": field, "input": text})
        self.current_step += 1

        if self.current_step >= len(steps):
            return self._generate_summary()

        return {
            "phase": "prompt",
            "content": self.get_next_prompt(),
            "crisis_result": None,
            "step": self.current_step,
            "record": self.record,
        }

    def _generate_summary(self) -> dict:
        """生成结构化摘要"""
        r = self.record
        emotion_label = r.get("emotion", "未知")
        intensity = r.get("intensity", "?")
        trigger = r.get("trigger", "未指明")

        summary = self._build_summary_text(r)
        next_step = self._suggest_next_step(r)

        return {
            "phase": "summary",
            "content": f"{summary}\n\n📌 **下一步的小建议**：\n{next_step}",
            "crisis_result": None,
            "step": self.current_step,
            "record": self.record,
        }

    def _build_summary_text(self, r: dict) -> str:
        """构建摘要文本"""
        parts = ["📝 **情绪日记摘要**\n"]
        parts.append(f"**事件**：{r.get('event', '未记录')}")
        parts.append(f"**情绪**：{r.get('emotion', '未记录')}")
        parts.append(f"**强度**：{r.get('intensity', '?')}/10")
        parts.append(f"**当时的想法**：{r.get('thought', '未记录')}")
        parts.append(f"**你的应对**：{r.get('action', '未记录')}")
        parts.append(f"**可能的触发因素**：{r.get('trigger', '未指明')}")
        return "\n".join(parts)

    def _suggest_next_step(self, r: dict) -> str:
        """给出一个小而实际的下一步建议"""
        emotion = r.get("emotion", "")
        intensity = r.get("intensity", 5)
        action = r.get("action", "")

        suggestions = []

        # 基于强度的建议
        try:
            intensity_num = int(intensity) if str(intensity).isdigit() else 5
        except:
            intensity_num = 5

        if intensity_num >= 7:
            suggestions.append("先让自己喘口气，不需要马上去分析原因")
            suggestions.append("如果可能，离开让你感到强烈的环境")
        else:
            suggestions.append("把这件事先放在日记里，它已经被记录下来了")
            if not action or action.strip() == "":
                suggestions.append("下次遇到类似情况，可以试着做点小事照顾自己：喝杯水、深呼吸、站起来走动")
            else:
                suggestions.append(f"你做的「{action}」是有效的尝试，这本身就是一种自我照顾")

        # 基于情绪类别的建议
        neg_emotions = ["悲伤", "沮丧", "失望", "绝望", "孤独", "疲惫"]
        if any(e in emotion for e in neg_emotions):
            suggestions.append("如果愿意，可以找信任的人简单说一说，不一定要讲清楚，只是说出来")

        angry_emotions = ["愤怒", "生气", "恼火"]
        if any(e in emotion for e in angry_emotions):
            suggestions.append("愤怒常常在提醒我们有某种需求没被满足：如果有机会，可以想一想，是什么没被尊重？")

        return "；".join(suggestions[:2])  # 最多给2条

    def get_disclaimer(self) -> str:
        return (
            "⚠️ **免责声明**：本工具仅提供一般性情绪自我观察支持，不提供诊断、心理咨询、"
            "精神科评估或医疗建议。如果你正在经历严重困扰、情况持续恶化或无法应对日常功能，"
            "请寻求持证心理健康专业人士、医生或当地紧急支持资源的帮助。"
        )

    def get_welcome(self) -> str:
        return (
            "🪪 **情绪日记**\n\n"
            "我们来把这次的情绪记录下来。不用一次说得很完整，一点一点来就好。\n\n"
            f"{self.get_next_prompt()}\n\n"
            f"{self.get_disclaimer()}"
        )


if __name__ == "__main__":
    # 交互式演示
    journal = EmotionJournal()
    print(journal.get_welcome())
    print("\n--- 模拟输入 ---\n")
    test_inputs = [
        "今天在公司和领导吵了一架",
        "很生气，觉得自己被针对了",
        "8",
        "我觉得他不公平，故意给我穿小鞋",
        "当时忍住了，没说话",
        "我觉得是因为我上次顶撞过他，他记仇了",
    ]
    for inp in test_inputs:
        print(f"\n用户: {inp}")
        result = journal.process_input(inp)
        print(f"阶段: {result['phase']}")
        print(f"内容: {result['content'][:200] if len(result['content']) > 200 else result['content']}")
        if result['phase'] == 'summary':
            break
