from __future__ import annotations

from backend.voice.streaming_text import SentenceChunker


def test_sentence_chunker_flushes_on_chinese_punctuation() -> None:
    chunker = SentenceChunker(max_chars=40)

    assert chunker.push("我知道") == []
    assert chunker.push("这很难。") == ["我知道这很难。"]
    assert chunker.flush() == []


def test_sentence_chunker_flushes_when_buffer_is_long() -> None:
    chunker = SentenceChunker(max_chars=7)

    assert chunker.push("你现在心里很堵") == ["你现在心里很堵"]


def test_sentence_chunker_keeps_short_tail_until_flush() -> None:
    chunker = SentenceChunker(max_chars=40)

    assert chunker.push("我们先慢一点") == []
    assert chunker.flush() == ["我们先慢一点"]
