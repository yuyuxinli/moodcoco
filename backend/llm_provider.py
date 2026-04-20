"""共享 LLM 配置 — 为 Fast/Slow Agent 提供模型实例和 Markdown 加载。"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def load_prompt(relative_path: str) -> str:
    """读取相对项目根的 Markdown 文件。

    常用路径：
      - "ai-companion/SOUL.md"
      - "ai-companion/skills/diary/SKILL.md"
      - "backend/prompts/fast-instructions.md"
    """
    full_path = PROJECT_ROOT / relative_path
    if not full_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {full_path}")
    return full_path.read_text(encoding="utf-8")


def get_model_name() -> str:
    return os.environ.get("OPENAI_MODEL", "minimax/minimax-m2.5")


@lru_cache(maxsize=1)
def get_openai_provider():
    from pydantic_ai.providers.openai import OpenAIProvider

    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing OPENAI_API_KEY / OPENROUTER_API_KEY. "
            "Copy .env.example → .env and fill in the key."
        )
    return OpenAIProvider(
        base_url=os.environ.get("OPENAI_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=api_key,
    )


def create_agent_model():
    """创建 PydanticAI 使用的 OpenAI 兼容 model 实例。"""
    from pydantic_ai.models.openai import OpenAIChatModel

    return OpenAIChatModel(
        model_name=get_model_name(),
        provider=get_openai_provider(),
    )
