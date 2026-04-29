#!/usr/bin/env bash
set -e
echo "=== nuke ==="
pkill -9 -f "run_agent_worker" 2>/dev/null || true
pkill -9 -f "voice_entrypoint" 2>/dev/null || true
pkill -9 -f "moodcoco-coco" 2>/dev/null || true
pkill -9 -f "persona_agent" 2>/dev/null || true
pkill -9 -f "livekit-server" 2>/dev/null || true
sleep 3

echo "=== logs reset ==="
> /tmp/moodcoco-livekit.log
> /tmp/moodcoco-agent.log
> /tmp/moodcoco-persona.log
rm -f /tmp/persona-yuyu.stop
rm -f /tmp/round1_b_done.txt /tmp/round1_b_report.md /tmp/round2_b_done.txt /tmp/round2_b_report.md

echo "=== livekit-server ==="
livekit-server --dev --bind 0.0.0.0 > /tmp/moodcoco-livekit.log 2>&1 &
sleep 3

echo "=== agent worker (single instance) ==="
export FILLER_GRACE_AFTER_SLOW_S=0.0
uv run --group voice python -c "import os; from dotenv import load_dotenv; load_dotenv('/Users/jianghongwei/Documents/moodcoco/.env'); from backend.voice.entrypoint import voice_entrypoint; from livekit.agents import cli, WorkerOptions; print(f\"[wrapper] LIVEKIT_URL={os.environ.get('LIVEKIT_URL')}\"); print('[wrapper] agent_name=moodcoco-coco'); cli.run_app(WorkerOptions(entrypoint_fnc=voice_entrypoint, agent_name='moodcoco-coco'))" start > /tmp/moodcoco-agent.log 2>&1 &
# wait for registration
for i in {1..30}; do
  grep -q "registered worker" /tmp/moodcoco-agent.log && break
  sleep 1
done

echo "=== explicit dispatch ==="
uv run --group voice python - <<'PY' >> /tmp/moodcoco-agent.log 2>&1 || true
import asyncio
import os

from dotenv import load_dotenv
from livekit import api

load_dotenv("/Users/jianghongwei/Documents/moodcoco/.env")


async def main():
    lkapi = api.LiveKitAPI(
        url=os.environ["LIVEKIT_URL"].replace("ws://", "http://").replace("wss://", "https://"),
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )
    try:
        dispatch = await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name="moodcoco-coco",
                room="moodcoco-voice",
                metadata="",
            )
        )
        print(
            f"dispatched: id={dispatch.id} agent_name={dispatch.agent_name!r} room={dispatch.room!r}"
        )
    finally:
        await lkapi.aclose()


asyncio.run(main())
PY
sleep 2

echo "=== persona ==="
cd /Users/jianghongwei/Documents/moodcoco
uv run --group voice python tools/voice_e2e/persona_agent.py > /tmp/moodcoco-persona.log 2>&1 &
echo "persona PID=$!"

echo "=== let it run 90s ==="
sleep 90
echo "=== done; capture logs ==="
