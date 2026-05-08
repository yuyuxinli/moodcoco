"""Voice-only streaming LLM responder.

This path avoids pydantic-ai tool calls because voice needs token/sentence
streaming while the text UI keeps the existing tool model.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from backend.llm_provider import load_prompt
from backend.voice.streaming_text import SentenceChunker


def _load_prompt_or_empty(relative_path: str) -> str:
    try:
        return load_prompt(relative_path)
    except FileNotFoundError:
        return ""


def build_voice_system_prompt() -> str:
    return "\n\n".join(
        part
        for part in [
            _load_prompt_or_empty("backend/prompts/SOUL.md"),
            _load_prompt_or_empty("backend/prompts/IDENTITY.md"),
            _load_prompt_or_empty("backend/prompts/AGENTS.md"),
            "## 实时语音模式\n"
            "只输出可直接说给用户听的中文短句。"
            "不要输出 JSON。不要调用工具。"
            "优先一句承接情绪，再问一个具体问题。"
            "每句尽量 10 到 30 个中文字符。",
        ]
        if part.strip()
    )


class VoiceStreamingResponder:
    def __init__(self, *, client: Any, model: str, system_prompt: str | None = None) -> None:
        self._client = client
        self._model = model
        self._system_prompt = system_prompt or build_voice_system_prompt()

    async def stream_reply(
        self,
        *,
        user_text: str,
        memory_text: str,
        slow_guidance: str,
        dynamic_inject: list[str],
        skill_bundle: list[str],
        retrieval_block: str,
    ) -> AsyncGenerator[str, None]:
        messages = [
            {"role": "system", "content": self._system_prompt},
            {
                "role": "system",
                "content": self._format_context(
                    memory_text=memory_text,
                    slow_guidance=slow_guidance,
                    dynamic_inject=dynamic_inject,
                    skill_bundle=skill_bundle,
                    retrieval_block=retrieval_block,
                ),
            },
            {"role": "user", "content": user_text},
        ]
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
            temperature=0.7,
        )
        chunker = SentenceChunker(max_chars=36)
        async for event in stream:
            if not getattr(event, "choices", None):
                continue
            token = getattr(event.choices[0].delta, "content", None)
            if not token:
                continue
            for sentence in chunker.push(token):
                yield sentence
        for sentence in chunker.flush():
            yield sentence

    @staticmethod
    def _format_context(
        *,
        memory_text: str,
        slow_guidance: str,
        dynamic_inject: list[str],
        skill_bundle: list[str],
        retrieval_block: str,
    ) -> str:
        parts: list[str] = []
        if memory_text.strip():
            parts.append("## MEMORY\n" + memory_text.strip())
        if slow_guidance.strip():
            parts.append("## 上一轮慢思考指导\n" + slow_guidance.strip())
        if dynamic_inject:
            parts.append("## Slow 动态注入\n" + "\n".join(dynamic_inject))
        if skill_bundle:
            parts.append("## Skill 片段\n" + "\n\n---\n\n".join(skill_bundle))
        if retrieval_block.strip():
            parts.append("## 检索补充\n" + retrieval_block.strip())
        return "\n\n".join(parts) or "无额外上下文。"
