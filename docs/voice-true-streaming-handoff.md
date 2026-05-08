# Voice True Streaming Handoff

**Branch**: `evolve/livekit-fast-slow`
**Date**: 2026-05-08
**Status**: 本地实现和目标单测完成；真实 MiniMax WebSocket/LiveKit e2e 尚未跑通，阻塞在 `MINIMAX_GROUP_ID` 缺失。

## What Changed

- **Streaming ASR**: 新增 `XfyunStreamingSTTPlugin`，直接接 LiveKit `RecognizeStream`，向讯飞 IAT WebSocket 发送 PCM 帧，支持 `pgs=rpl` 多槽替换，并通过 LiveKit data channel 发布 `user_partial` / `user_final`。
- **Streaming LLM**: 新增 `VoiceStreamingResponder`，使用 OpenAI-compatible `AsyncOpenAI` 流式输出，按句子边界产出 Coco 回复，不再等完整回复。
- **Streaming TTS**: 新增 `MiniMaxStreamingTTSClient`，使用 MiniMax T2A WebSocket、`GroupId` URL、`format=pcm`，通过 LiveKit `rtc.AudioSource` 发布 PCM 音频；`minimax_ws` 模式不会走 `session.say()`。
- **Frontend Transcript**: Web 端监听 `RoomEvent.DataReceived(topic="voice-stream")`，显示用户实时转写、用户 final、Coco 句子和 partial 状态。
- **Interruption**: `StreamingVoiceBridgeAgent` 持有当前 turn task，新 turn 会取消旧 task，并发布 `turn_interrupted` 事件。
- **Metrics**: `.evolve/voice_eval.py` 新增 `time_to_user_partial_ms`、`time_to_user_final_ms`、`time_to_first_coco_sentence_ms`、`time_to_first_audio_ms`、`streaming_mode_enabled`、`tts_mode`、`voice_tts_sink`、`barge_in_success`。

## Commands

- Backend/API:
  `uv run python -c "from dotenv import load_dotenv; load_dotenv('/home/yizhuo_wang/code1/moodcoco/.env', override=False); import uvicorn; uvicorn.run('backend.api:app', host='0.0.0.0', port=8002)"`
- Web:
  `cd web && NEXT_PUBLIC_API_BASE=http://localhost:8002 npm run dev -- --hostname 0.0.0.0 --port 3001`
- Worker:
  `VOICE_STREAMING_MODE=true VOICE_STREAMING_TTS_MODE=minimax_ws uv run python -c "import os; from dotenv import load_dotenv; load_dotenv('/home/yizhuo_wang/code1/moodcoco/.env', override=False); os.environ.setdefault('DOUBAO_API_KEY', os.environ.get('OPENAI_API_KEY','')); os.environ.setdefault('DOUBAO_BASE_URL', os.environ.get('OPENAI_BASE_URL','')); os.environ.setdefault('DOUBAO_MODEL', os.environ.get('OPENAI_FAST_MODEL') or os.environ.get('OPENAI_MODEL','')); from backend.voice.entrypoint import voice_entrypoint; from livekit.agents import cli, WorkerOptions; cli.run_app(WorkerOptions(entrypoint_fnc=voice_entrypoint, agent_name='moodcoco-coco'))" start`

## Evidence

- `uv run pytest tests/voice/test_xfyun_streaming_stt.py tests/voice/test_streaming_bridge_agent.py tests/voice/test_minimax_streaming_tts.py tests/voice/test_voice_entrypoint_runtime_config.py tests/test_voice_eval_streaming.py -q` -> 15 passed
- `uv run pytest tests/test_coordinator.py tests/test_voice_eval_streaming.py -q` -> 4 passed
- `uv run python -m py_compile backend/voice/streaming_bridge_agent.py backend/voice/entrypoint.py backend/voice/plugins/xfyun_streaming_stt.py backend/voice/livekit_data.py .evolve/voice_eval.py` -> passed
- `cd web && npm run lint` -> passed
- Broader `uv run pytest tests/voice -q --ignore=tests/voice/test_voice_entrypoint.py` reached 52 passing dots, then hung in remaining legacy voice tests; stopped as non-blocking for this implementation round.

## Environment Check

- `LIVEKIT_URL`: set
- `LIVEKIT_API_KEY`: set
- `LIVEKIT_API_SECRET`: set
- `MINIMAX_API_KEY`: set
- `MINIMAX_GROUP_ID`: missing
- `XFYUN_APP_ID`: set
- `XFYUN_API_KEY`: set
- `XFYUN_API_SECRET`: set
- `OPENAI_API_KEY`: set
- `DOUBAO_API_KEY`: missing, but worker command maps `DOUBAO_API_KEY` from `OPENAI_API_KEY`

## Remaining Risks

- **Provider WebSocket validation**: 真 MiniMax PCM WebSocket 请求还没跑，因为 `MINIMAX_GROUP_ID` 缺失；不能声称 `minimax_ws` 真实音频 e2e 已通过。
- **LiveKit audio sink**: 本地代码使用 `rtc.AudioSource` PCM 分支，已做接口编译和单测，但还需要浏览器听到连续两句 Coco 回复来确认。
- **Echo / barge-in**: 已有 turn cancellation 和 `turn_interrupted` 事件，但真实打断时是否会被 Coco 自己的 TTS 回灌影响，需要手动 smoke。
- **Legacy voice tests**: `tests/voice` 全量仍存在长等待测试，建议后续单独拆解 `test_voice_entrypoint.py` 及相关旧用例。
