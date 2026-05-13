"""L2 Safety: keyword/regex filter for Speaker output.

Applied before TTS output. Blocks dangerous content and provides safe replacement.
L1 (prompt constraints) is in system prompt. L3 (async review) is in slow.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class FilterResult:
    blocked: bool
    reason: str = ""
    safe_replacement: str = ""


BLOCK_PATTERNS: list[tuple[str, str]] = [
    (r"割腕|割手|跳楼|上吊|吞药|自残的方法|怎么死", "自残/自杀方法引导"),
    (r"你可能患有|你有抑郁症|你有焦虑症|诊断为|你患了|你得了.{0,4}症", "临床诊断"),
    (r"去死|该死|不如死", "极端有害表达"),
]


def keyword_filter(text: str) -> FilterResult:
    for pattern, reason in BLOCK_PATTERNS:
        if re.search(pattern, text, re.DOTALL):
            return FilterResult(
                blocked=True,
                reason=reason,
                safe_replacement="我在这里陪着你，你现在安全的。",
            )
    return FilterResult(blocked=False)
