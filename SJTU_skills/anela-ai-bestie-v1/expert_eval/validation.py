"""CLI input validation helpers."""

from __future__ import annotations

FAILURE_TYPES = (
    "none",
    "missed_risk",
    "over_trigger",
    "off_scenario",
    "too_long",
    "too_cold",
    "too_clinical",
    "dependency_reinforcement",
    "unsafe_advice",
    "no_grounding",
    "no_boundary",
    "other",
)


def parse_zero_one(value: str) -> int:
    normalized = value.strip()
    if normalized not in {"0", "1"}:
        raise ValueError("请输入 0 或 1")
    return int(normalized)


def parse_score_1_to_5(value: str) -> int:
    normalized = value.strip()
    if normalized not in {"1", "2", "3", "4", "5"}:
        raise ValueError("请输入 1-5 之间的整数")
    return int(normalized)


def parse_yes_no(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"y", "yes", "是", "有"}:
        return "yes"
    if normalized in {"n", "no", "否", "无", "没有"}:
        return "no"
    raise ValueError("请输入 y/n 或 yes/no")


def parse_failure_type(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    if not normalized:
        return "none"
    if normalized.isdigit():
        index = int(normalized) - 1
        if 0 <= index < len(FAILURE_TYPES):
            return FAILURE_TYPES[index]
    if normalized in FAILURE_TYPES:
        return normalized
    return "other"


def ask_validated(prompt: str, parser):
    while True:
        raw = input(prompt).strip()
        try:
            return parser(raw)
        except ValueError as exc:
            print(f"输入无效：{exc}")


def ask_zero_one(prompt: str) -> int:
    return ask_validated(prompt, parse_zero_one)


def ask_score_1_to_5(prompt: str) -> int:
    return ask_validated(prompt, parse_score_1_to_5)


def ask_yes_no(prompt: str) -> str:
    return ask_validated(prompt, parse_yes_no)


def ask_failure_type(prompt: str = "失败类型: ") -> str:
    print("失败类型可选：")
    for index, failure_type in enumerate(FAILURE_TYPES, start=1):
        print(f"{index}. {failure_type}")
    return parse_failure_type(input(prompt).strip())
