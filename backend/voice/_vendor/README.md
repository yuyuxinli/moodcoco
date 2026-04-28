# `_vendor/psy/` — Vendored from psychologists

Copied 2026-04-29 from `~/Documents/psychologists/backend/services/shared/`:

- `stt/speech_to_text_xfyun_service.py` — 讯飞 ASR WebSocket 客户端
- `stt/streaming_stt_manager.py` — 流式 STT 管理
- `tts/service.py` — MiniMax TTS HTTP 客户端

These are **copies, not symlinks**. moodcoco evolves them independently. Upstream
bug fixes in psychologists must be manually re-vendored — track diffs via
`diff -r backend/voice/_vendor/psy/ ~/Documents/psychologists/backend/services/shared/`.

LiveKit plugin wrappers (F3/F4) live in `backend/voice/plugins/{xfyun_stt,minimax_tts}.py`
and `import` from these vendored modules directly:

```python
from backend.voice._vendor.psy.stt.speech_to_text_xfyun_service import XfyunASR
from backend.voice._vendor.psy.tts.service import MiniMaxTTSService
```

Do not modify files under `_vendor/` to fix moodcoco-specific bugs — wrap them
in the plugin layer instead, so the next re-vendor doesn't lose your changes.
