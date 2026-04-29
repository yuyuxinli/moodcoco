#!/usr/bin/env bash
set -e
echo "=== nuke ==="
pkill -9 -f "run_agent_worker" 2>/dev/null || true
pkill -9 -f "voice_entrypoint" 2>/dev/null || true
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
uv run --group voice python /tmp/run_agent_worker.py dev > /tmp/moodcoco-agent.log 2>&1 &
# wait for registration
for i in {1..30}; do
  grep -q "registered worker" /tmp/moodcoco-agent.log && break
  sleep 1
done

echo "=== explicit dispatch ==="
uv run --group voice python /tmp/dispatch_agent.py >> /tmp/moodcoco-agent.log 2>&1 || true
sleep 2

echo "=== persona ==="
cd /Users/jianghongwei/Documents/moodcoco
uv run --group voice python tools/voice_e2e/persona_agent.py > /tmp/moodcoco-persona.log 2>&1 &
echo "persona PID=$!"

echo "=== let it run 90s ==="
sleep 90
echo "=== done; capture logs ==="
