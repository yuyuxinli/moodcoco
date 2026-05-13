#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage: bash .evolve/run_e2e.sh

Runs one real voice e2e pass:
  1. loads repo .env
  2. starts local LiveKit only when LIVEKIT_URL is local
  3. starts the Coco LiveKit agent worker
  4. dispatches the worker into a unique room
  5. starts the persona participant for 150s

Logs:
  /tmp/moodcoco-livekit.log
  /tmp/moodcoco-agent.log
  /tmp/moodcoco-persona.log
  /tmp/moodcoco-e2e-room.txt
EOF
  exit 0
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
ROOM_NAME="${ROOM_NAME:-moodcoco-voice-$(date +%s)}"
PERSONA_IDENTITY="${PERSONA_IDENTITY:-persona-yuyu-${ROOM_NAME##*-}}"

export ROOM_NAME
export PERSONA_IDENTITY

echo "$ROOM_NAME" > /tmp/moodcoco-e2e-room.txt

load_env_exports() {
  python - "$ENV_FILE" <<'PY'
import os
import shlex
import sys

from dotenv import load_dotenv

env_file = sys.argv[1]
load_dotenv(env_file, override=False)

prefixes = (
    "LIVEKIT_",
    "MINIMAX_",
    "XFYUN_",
    "OPENAI_",
    "OPENROUTER_",
    "DOUBAO_",
    "PERSONA_",
    "MOODCOCO_",
    "FILLER_",
)
for key, value in sorted(os.environ.items()):
    if key.startswith(prefixes):
        print(f"export {key}={shlex.quote(value)}")
PY
}

eval "$(load_env_exports)"

for required in LIVEKIT_URL LIVEKIT_API_KEY LIVEKIT_API_SECRET MINIMAX_API_KEY XFYUN_APP_ID XFYUN_API_KEY XFYUN_API_SECRET OPENAI_API_KEY; do
  if [[ -z "${!required:-}" ]]; then
    echo "missing required env: $required" >&2
    exit 1
  fi
done

echo "=== nuke old moodcoco voice processes ==="
pkill -9 -f "run_agent_worker" 2>/dev/null || true
pkill -9 -f "voice_entrypoint" 2>/dev/null || true
pkill -9 -f "moodcoco-coco" 2>/dev/null || true
pkill -9 -f "persona_agent" 2>/dev/null || true
if [[ "${LIVEKIT_URL:-}" == ws://localhost* || "${LIVEKIT_URL:-}" == ws://127.0.0.1* ]]; then
  pkill -9 -f "livekit-server" 2>/dev/null || true
fi
sleep 3

echo "=== logs reset ==="
> /tmp/moodcoco-livekit.log
> /tmp/moodcoco-agent.log
> /tmp/moodcoco-persona.log
rm -f "/tmp/${PERSONA_IDENTITY}.stop"
rm -f /tmp/round1_b_done.txt /tmp/round1_b_report.md /tmp/round2_b_done.txt /tmp/round2_b_report.md

if [[ "${LIVEKIT_URL:-}" == ws://localhost* || "${LIVEKIT_URL:-}" == ws://127.0.0.1* ]]; then
  echo "=== livekit-server ==="
  if ! command -v livekit-server >/dev/null 2>&1; then
    echo "livekit-server not found, but LIVEKIT_URL is local: $LIVEKIT_URL" >&2
    exit 1
  fi
  livekit-server --dev --bind 0.0.0.0 > /tmp/moodcoco-livekit.log 2>&1 &
  sleep 3
else
  echo "=== remote livekit: ${LIVEKIT_URL} ==="
fi

echo "=== agent worker (single instance) ==="
export FILLER_GRACE_AFTER_SLOW_S="${FILLER_GRACE_AFTER_SLOW_S:-0.0}"
cd "$ROOT_DIR"
uv run --group voice python -c "import os; from dotenv import load_dotenv; load_dotenv('$ENV_FILE', override=False); from backend.voice.entrypoint import voice_entrypoint; from livekit.agents import cli, WorkerOptions; print(f'[wrapper] LIVEKIT_URL={os.environ.get(\"LIVEKIT_URL\")}'); print('[wrapper] agent_name=moodcoco-coco'); cli.run_app(WorkerOptions(entrypoint_fnc=voice_entrypoint, agent_name='moodcoco-coco'))" start > /tmp/moodcoco-agent.log 2>&1 &

for _ in {1..45}; do
  grep -q "registered worker" /tmp/moodcoco-agent.log && break
  sleep 1
done
grep -q "registered worker" /tmp/moodcoco-agent.log

echo "=== explicit dispatch room=$ROOM_NAME ==="
uv run --group voice python - <<'PY' >> /tmp/moodcoco-agent.log 2>&1
import asyncio
import os

from dotenv import load_dotenv
from livekit import api

load_dotenv(os.path.join(os.getcwd(), ".env"), override=False)


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
                room=os.environ["ROOM_NAME"],
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

echo "=== persona room=$ROOM_NAME identity=$PERSONA_IDENTITY ==="
uv run --group voice python tools/voice_e2e/persona_agent.py \
  --room "$ROOM_NAME" \
  --identity "$PERSONA_IDENTITY" \
  --max-turns "${PERSONA_MAX_TURNS:-4}" \
  > /tmp/moodcoco-persona.log 2>&1 &
echo "persona PID=$!"

echo "=== let it run 150s ==="
sleep "${E2E_DURATION_S:-150}"
touch "/tmp/${PERSONA_IDENTITY}.stop"
sleep 2
echo "=== done; capture logs ==="
