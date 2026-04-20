#!/usr/bin/env bash
# 循环叹息引导脚本 —— 通过 openclaw message send 定时发送
# ⚠️  这是备用脚本。正式版请用 breathe-fast.py（单 WebSocket 连接，节奏更准）。
#
# 用法: breathe.sh <channel> [cycles]
# 示例: breathe.sh feishu 3
#
# target 自动从 sessions.json 查找（最近活跃的该 channel 会话）
# 中断: kill $(cat /tmp/breathe.pid)

CHANNEL="$1"
CYCLES="${2:-3}"

if [ -z "$CHANNEL" ]; then
  echo "用法: breathe.sh <channel> [cycles]"
  exit 1
fi

DRY_RUN="${DRY_RUN:-}"
PIDFILE="/tmp/breathe.pid"

# 从 sessions.json 自动查找 target 和 accountId
if [ -z "$DRY_RUN" ]; then
  SESSIONS_FILE="$HOME/.openclaw/agents/coco/sessions/sessions.json"
  ROUTING=$(python3 -c "
import json, sys
with open('$SESSIONS_FILE') as f:
    data = json.load(f)
best, best_ts = None, 0
for key, val in data.items():
    if isinstance(val, dict) and val.get('lastChannel') == '$CHANNEL':
        ts = int(val.get('updatedAt', 0))
        if ts > best_ts:
            best, best_ts = val, ts
if best and best.get('lastTo'):
    print(best['lastTo'])
    print(best.get('lastAccountId', ''))
else:
    sys.exit(1)
" 2>/dev/null)

  TARGET=$(echo "$ROUTING" | sed -n '1p')
  ACCOUNT=$(echo "$ROUTING" | sed -n '2p')

  if [ -z "$TARGET" ]; then
    echo "错误：找不到 channel=$CHANNEL 的 target" >&2
    exit 1
  fi
fi

# 如果已有实例在跑，先杀掉
if [ -f "$PIDFILE" ]; then
  OLD_PID=$(cat "$PIDFILE" 2>/dev/null)
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    kill "$OLD_PID" 2>/dev/null
    sleep 0.5
  fi
fi

# 写入 PID，退出时清理
echo $$ > "$PIDFILE"
cleanup() { rm -f "$PIDFILE"; }
trap cleanup EXIT
trap 'exit 0' TERM INT

# sleep 的包装：后台 sleep + wait，使 SIGTERM 可立即中断
pause() { sleep "$1" & wait $!; }

# 高精度时间戳（秒，小数）—— macOS date 不支持 %N，用 python3
_now() { python3 -c 'import time; print(f"{time.time():.4f}")'; }

send() {
  if [ -n "$DRY_RUN" ]; then
    echo "[$(date +%H:%M:%S)] $1"
  else
    local cmd=(openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "$1")
    [ -n "$ACCOUNT" ] && cmd+=(--account "$ACCOUNT")
    if ! "${cmd[@]}"; then
      echo "发送失败，退出" >&2
      exit 1
    fi
  fi
}

# send + adaptive pause：发送后只睡「目标间隔 − 实际发送耗时」
send_and_pause() {
  local target_secs="$1"; shift
  local t0; t0=$(_now)
  send "$@"
  local t1; t1=$(_now)
  local remaining; remaining=$(awk "BEGIN{r=$target_secs-($t1-$t0); printf \"%.2f\", (r>0?r:0)}")
  pause "$remaining"
}

send_and_pause 2 "跟我一起，就一个动作。跟着数就行。"

for ((i=1; i<=CYCLES; i++)); do
  send_and_pause 4 "鼻子吸气，数 4 秒 —— 1、2、3、4"

  send_and_pause 2 "再追一小口，撑满 —— 1、2"

  send_and_pause 8 "嘴巴慢慢吐 …… 8 秒，不急 —— 1、2、3、4、5、6、7、8"

  if [ "$i" -lt "$CYCLES" ]; then
    send "再来。"
  fi
done

send_and_pause 1 "好了。"
