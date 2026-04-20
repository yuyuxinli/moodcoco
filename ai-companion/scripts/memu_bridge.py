#!/usr/bin/env python3
"""memU 桥接脚本 — OpenClaw Skill 与 memU 记忆引擎的 CLI 接口。

提供 4 个操作：
  memorize   — 存储对话记忆（传入对话文本文件路径）
  retrieve   — 检索与查询相关的记忆
  list_categories — 列出用户的所有 memory category
  get_summary     — 获取指定 category 的摘要

使用方式（在 OpenClaw Skill 中通过 shell 调用）：
  python scripts/memu_bridge.py memorize --input conversation.txt --user-id coco_user
  python scripts/memu_bridge.py retrieve --query "妈妈 考研" --user-id coco_user
  python scripts/memu_bridge.py list_categories --user-id coco_user
  python scripts/memu_bridge.py get_summary --category "people/妈妈" --user-id coco_user

环境变量：
  MEMU_LLM_BASE_URL    — LLM API base URL（默认 OpenRouter）
  MEMU_LLM_API_KEY     — LLM API key
  MEMU_LLM_MODEL       — LLM 模型名（默认 minimax/minimax-m2.7）
  MEMU_DB_DSN           — PostgreSQL DSN（可选，默认 inmemory）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

# Add the ai-companion directory to path so memu package is importable
_AI_COMPANION_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_AI_COMPANION_DIR))

from memu.app.service import MemoryService  # noqa: E402

logger = logging.getLogger("memu_bridge")


def _build_service(user_id: str | None = None) -> MemoryService:
    """Build a MemoryService instance with environment-driven configuration."""
    base_url = os.environ.get("MEMU_LLM_BASE_URL", "https://openrouter.ai/api/v1")
    api_key = os.environ.get("MEMU_LLM_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))
    chat_model = os.environ.get("MEMU_LLM_MODEL", "minimax/minimax-m2.7")
    db_dsn = os.environ.get("MEMU_DB_DSN", "")

    llm_profiles: dict[str, Any] = {
        "default": {
            "provider": "openai",
            "base_url": base_url,
            "api_key": api_key,
            "chat_model": chat_model,
            "client_backend": "sdk",
            "embed_model": "text-embedding-3-small",
        },
    }

    database_config: dict[str, Any]
    if db_dsn:
        database_config = {
            "metadata_store": {"provider": "postgres", "dsn": db_dsn},
            "vector_index": {"provider": "none"},
        }
    else:
        database_config = {
            "metadata_store": {"provider": "inmemory"},
            "vector_index": {"provider": "bruteforce"},
        }

    # Use the default three-dimensional categories from settings.py
    # (self/核心信念, self/行为模式, self/价值观, self/情绪触发点, self/有效方法)
    # Dynamic categories (people/*, events/*) are created automatically during memorize.

    retrieve_config: dict[str, Any] = {
        "method": "llm",  # No vector service yet, use LLM ranking
        "route_intention": True,
        "category": {"enabled": True, "top_k": 10},
        "item": {"enabled": True, "top_k": 10},
        "resource": {"enabled": False},
        "sufficiency_check": False,
    }

    service = MemoryService(
        llm_profiles=llm_profiles,
        database_config=database_config,
        retrieve_config=retrieve_config,
        blob_config={"provider": "local", "resources_dir": str(_AI_COMPANION_DIR / "data" / "resources")},
    )
    return service


def _write_temp_file(content: str) -> str:
    """Write content to a temp file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".txt", prefix="memu_conv_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


async def cmd_memorize(args: argparse.Namespace) -> dict[str, Any]:
    """Store conversation memory via memU memorize pipeline."""
    service = _build_service(args.user_id)

    # Read conversation text
    if args.input == "-":
        text = sys.stdin.read()
    else:
        text = Path(args.input).read_text(encoding="utf-8")

    if not text.strip():
        return {"status": "skip", "reason": "empty input"}

    # Write to temp file (memU expects a resource URL / file path)
    temp_path = _write_temp_file(text)
    try:
        user_data = {"user_id": args.user_id} if args.user_id else None
        result = await service.memorize(
            resource_url=temp_path,
            modality="conversation",
            user=user_data,
        )
        return {"status": "ok", "items_count": len(result.get("items", [])), "categories": [
            c.get("name", "") for c in result.get("categories", [])
        ]}
    finally:
        os.unlink(temp_path)


async def cmd_retrieve(args: argparse.Namespace) -> dict[str, Any]:
    """Retrieve relevant memories for a query."""
    service = _build_service(args.user_id)

    queries: list[dict[str, Any]] = []
    if args.context:
        for ctx_line in args.context:
            queries.append({"role": "user", "content": ctx_line})
    queries.append({"role": "user", "content": args.query})

    result = await service.retrieve(queries)
    return {"status": "ok", "result": result}


async def cmd_list_categories(args: argparse.Namespace) -> dict[str, Any]:
    """List all memory categories for the user."""
    service = _build_service(args.user_id)
    result = await service.list_memory_categories()
    return {"status": "ok", "categories": result}


async def cmd_get_summary(args: argparse.Namespace) -> dict[str, Any]:
    """Get the summary of a specific category."""
    service = _build_service(args.user_id)
    result = await service.list_memory_categories()

    categories = result.get("categories", [])
    target = args.category.strip().lower()

    for cat in categories:
        if cat.get("name", "").strip().lower() == target:
            return {
                "status": "ok",
                "category": cat.get("name"),
                "summary": cat.get("summary", ""),
                "item_count": cat.get("item_count", 0),
            }

    return {"status": "not_found", "category": args.category}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="memU bridge script for OpenClaw Skills",
        prog="memu_bridge",
    )
    parser.add_argument("--user-id", default="coco_user", help="User identifier")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # memorize
    p_memo = subparsers.add_parser("memorize", help="Store conversation memory")
    p_memo.add_argument("--input", "-i", required=True, help="Path to conversation text file, or - for stdin")

    # retrieve
    p_ret = subparsers.add_parser("retrieve", help="Retrieve relevant memories")
    p_ret.add_argument("--query", "-q", required=True, help="Query string")
    p_ret.add_argument("--context", "-c", nargs="*", help="Context messages (preceding conversation)")

    # list_categories
    subparsers.add_parser("list_categories", help="List all memory categories")

    # get_summary
    p_sum = subparsers.add_parser("get_summary", help="Get category summary")
    p_sum.add_argument("--category", required=True, help="Category name (e.g. people/妈妈)")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    cmd_map = {
        "memorize": cmd_memorize,
        "retrieve": cmd_retrieve,
        "list_categories": cmd_list_categories,
        "get_summary": cmd_get_summary,
    }

    handler = cmd_map[args.command]
    result = asyncio.run(handler(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
