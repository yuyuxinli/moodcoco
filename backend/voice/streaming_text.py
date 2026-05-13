"""Utilities for turning streamed LLM tokens into speakable sentence chunks."""
from __future__ import annotations

_BOUNDARY_CHARS = set("。！？!?；;\n")


class SentenceChunker:
    def __init__(self, *, max_chars: int = 36) -> None:
        self._max_chars = max_chars
        self._buffer = ""

    def push(self, text: str) -> list[str]:
        self._buffer += text
        out: list[str] = []

        while self._buffer:
            boundary = self._find_boundary(self._buffer)
            if boundary is not None:
                segment = self._buffer[: boundary + 1].strip()
                self._buffer = self._buffer[boundary + 1 :]
                if segment:
                    out.append(segment)
                continue

            if len(self._buffer) >= self._max_chars:
                segment = self._buffer.strip()
                self._buffer = ""
                if segment:
                    out.append(segment)
            break

        return out

    def flush(self) -> list[str]:
        segment = self._buffer.strip()
        self._buffer = ""
        return [segment] if segment else []

    @staticmethod
    def _find_boundary(text: str) -> int | None:
        for idx, char in enumerate(text):
            if char in _BOUNDARY_CHARS:
                return idx
        return None
