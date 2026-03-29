#!/usr/bin/env python3
"""
情绪模式追踪器 - emotion-journal skill 模块
分析历史记录，识别情绪触发模式和趋势
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict


class PatternTracker:
    """
    情绪模式追踪器

    分析多条历史记录，识别：
    - 高频情绪类型
    - 常见触发因素
    - 情绪强度趋势
    - 可能的循环模式
    """

    def __init__(self, records: List[Dict] = None):
        self.records = records or []

    def load_from_file(self, filepath: str) -> bool:
        """从文件加载历史记录"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.records = json.load(f)
            return True
        except Exception:
            return False

    def add_record(self, record: Dict):
        """添加一条记录"""
        self.records.append(record)

    def get_emotion_frequency(self) -> Dict[str, int]:
        """统计情绪出现频率"""
        freq = defaultdict(int)
        for r in self.records:
            emotion = r.get("emotion", "")
            if emotion:
                freq[emotion] += 1
        return dict(sorted(freq.items(), key=lambda x: x[1], reverse=True))

    def get_trigger_frequency(self) -> Dict[str, int]:
        """统计触发因素出现频率"""
        freq = defaultdict(int)
        for r in self.records:
            trigger = r.get("trigger", "")
            if trigger:
                freq[trigger] += 1
        return dict(sorted(freq.items(), key=lambda x: x[1], reverse=True))

    def get_average_intensity(self) -> Optional[float]:
        """计算平均情绪强度"""
        intensities = []
        for r in self.records:
            val = r.get("intensity")
            if val is not None:
                try:
                    intensities.append(float(val))
                except (ValueError, TypeError):
                    pass
        if not intensities:
            return None
        return sum(intensities) / len(intensities)

    def get_pattern_report(self) -> str:
        """生成模式报告"""
        if not self.records:
            return "暂无足够数据生成模式报告。建议先记录3-5条以上的情绪日记后再分析。"

        lines = ["📊 **情绪模式报告**\n"]

        # 情绪频率
        emotion_freq = self.get_emotion_frequency()
        if emotion_freq:
            top_emotions = list(emotion_freq.items())[:3]
            lines.append(f"**最常见的情绪**：")
            for e, count in top_emotions:
                lines.append(f"  - {e}（{count}次）")

        # 触发因素
        trigger_freq = self.get_trigger_frequency()
        if trigger_freq:
            top_triggers = list(trigger_freq.items())[:3]
            lines.append(f"\n**常见触发因素**：")
            for t, count in top_triggers:
                lines.append(f"  - {t}（{count}次）")

        # 平均强度
        avg_int = self.get_average_intensity()
        if avg_int is not None:
            lines.append(f"\n**平均情绪强度**：{avg_int:.1f}/10")
            if avg_int >= 7:
                lines.append("（整体情绪强度偏高，可能需要注意自我照顾）")

        # 记录数量
        lines.append(f"\n**总记录数**：{len(self.records)}条")

        return "\n".join(lines)


if __name__ == "__main__":
    # Demo
    tracker = PatternTracker([
        {"emotion": "愤怒", "intensity": "8", "trigger": "工作压力"},
        {"emotion": "焦虑", "intensity": "6", "trigger": "人际关系"},
        {"emotion": "愤怒", "intensity": "7", "trigger": "工作压力"},
        {"emotion": "疲惫", "intensity": "5", "trigger": "睡眠不足"},
    ])
    print(tracker.get_pattern_report())
