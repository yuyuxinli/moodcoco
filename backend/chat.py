"""CLI REPL — 验证快慢思考双层架构。

用法：
  python -m backend.chat
  python -m backend.chat --reset-memory
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime

from backend.coordinator import reset_guidance_for_demo, run_turn
from backend.slow import reset_memory_file_for_demo


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="moodcoco 快慢思考 CLI")
    parser.add_argument(
        "--reset-memory",
        action="store_true",
        help="启动前把 ai-companion/MEMORY.md 重置为初始骨架",
    )
    parser.add_argument(
        "--session-id",
        default="demo-" + datetime.now().strftime("%H%M%S"),
        help="会话 ID（默认 demo-HHMMSS）",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    if args.reset_memory:
        reset_memory_file_for_demo()
        print("[info] MEMORY.md 已重置")

    # 每次 REPL 启动都清空上轮遗留的 SLOW_GUIDANCE.md
    reset_guidance_for_demo()

    print("=" * 60)
    print(" moodcoco Fast/Slow Thinking MVP")
    print(f" session_id={args.session_id}")
    print(" 输入 /exit 或 /quit 退出。")
    print("=" * 60)

    while True:
        try:
            user_msg = input("\n你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            return
        if user_msg in {"/exit", "/quit", "exit", "quit", ""}:
            if not user_msg:
                continue
            print("再见。")
            return
        try:
            await run_turn(user_msg, session_id=args.session_id)
        except Exception as exc:  # noqa: BLE001 — CLI 需要打印所有异常，不 crash 掉 REPL
            print(f"[error] {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    asyncio.run(_main())
