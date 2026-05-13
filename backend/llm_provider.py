"""共享 LLM 配置 — 为 Fast/Slow Agent 提供模型实例和 Markdown 加载。"""

from __future__ import annotations

import os
import logging
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
logging.getLogger("dotenv.main").setLevel(logging.ERROR)
load_dotenv(PROJECT_ROOT / ".env")


def load_prompt(relative_path: str) -> str:
    """读取相对项目根的 Markdown 文件。

    常用路径：
      - "backend/prompts/SOUL.md"
      - "backend/skills/diary/SKILL.md"
      - "backend/prompts/fast-instructions.md"
    """
    full_path = PROJECT_ROOT / relative_path
    if not full_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {full_path}")
    return full_path.read_text(encoding="utf-8")


def get_model_name() -> str:
    return os.environ.get("OPENAI_MODEL", "minimax/minimax-m2.7")


def get_slow_model_name() -> str:
    return get_model_name()


def get_fast_model_name() -> str:
    return (
        os.environ.get("OPENAI_FAST_MODEL")
        or os.environ.get("DOUBAO_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "minimax/minimax-m2.7"
    )


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


def _fast_model_settings() -> dict | None:
    base_url = os.environ.get("OPENAI_BASE_URL", "https://openrouter.ai/api/v1").lower()
    explicit_effort = os.environ.get("OPENAI_FAST_REASONING_EFFORT")
    if explicit_effort:
        return {"extra_body": {"reasoning_effort": explicit_effort}}
    if "openrouter.ai" in base_url:
        return {"extra_body": {"reasoning_effort": "none"}}
    return None


def _create_openai_model(model_name: str, *, settings: dict | None = None):
    from pydantic_ai.models.openai import OpenAIChatModel

    return OpenAIChatModel(
        model_name=model_name,
        provider=get_openai_provider(),
        settings=settings,
    )


def create_fast_model():
    """创建 Fast Agent 使用的 OpenAI 兼容 model 实例。"""
    return _create_openai_model(get_fast_model_name(), settings=_fast_model_settings())


def create_slow_model():
    """创建 Slow Agent 使用的 OpenAI 兼容 model 实例。"""
    return _create_openai_model(get_slow_model_name())


def create_voice_streaming_client():
    from openai import AsyncOpenAI

    return AsyncOpenAI(
        base_url=os.environ.get("DOUBAO_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=os.environ.get("DOUBAO_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENROUTER_API_KEY"),
    )


def get_voice_streaming_model_name() -> str:
    return (
        os.environ.get("OPENAI_FAST_MODEL")
        or os.environ.get("DOUBAO_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "doubao-seed-2-0-lite-260215"
    )


def create_agent_model():
    """创建默认 PydanticAI model 实例；保留给非语音链路使用。"""
    return create_slow_model()
