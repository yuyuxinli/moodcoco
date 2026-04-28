from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import httpx

from backend.voice._vendor.psy.tts.types import MiniMaxAccountConfig, MiniMaxSynthesisOptions

log = logging.getLogger(__name__)


def parse_minimax_url_result(result: Dict) -> Tuple[Optional[str], Dict, Optional[Dict]]:
    base_resp = result.get("base_resp", {})
    base_status_code = base_resp.get("status_code")
    base_status_msg = base_resp.get("status_msg")
    data = result.get("data", {})
    extra_info = dict(result.get("extra_info", {}) or {})

    subtitles = extra_info.get("subtitle") or data.get("subtitle")
    if subtitles:
        extra_info["subtitles"] = subtitles

    request_id = (
        extra_info.get("request_id")
        or data.get("request_id")
        or base_resp.get("request_id")
    )
    if request_id:
        extra_info["request_id"] = request_id

    if base_status_code != 0:
        return None, extra_info, {
            "reason": "base_resp_error",
            "base_status_code": base_status_code,
            "base_status_msg": base_status_msg,
            "request_id": request_id,
        }

    audio_url = data.get("audio")
    if not audio_url:
        return None, extra_info, {
            "reason": "empty_audio",
            "base_status_code": base_status_code,
            "base_status_msg": base_status_msg,
            "request_id": request_id,
            "data_keys": sorted(data.keys()),
        }

    return audio_url, extra_info, None


class MiniMaxTTSClient:
    def __init__(self, config: MiniMaxAccountConfig, output_dir: str) -> None:
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.api_url = "https://api.minimaxi.com/v1/t2a_v2"
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _build_request_body(
        self,
        text: str,
        options: MiniMaxSynthesisOptions,
        *,
        stream: bool = False,
        output_format: str = "hex",
    ) -> Dict:
        body = {
            "model": options.model,
            "text": text,
            "stream": stream,
            "voice_setting": {
                "voice_id": options.voice_id,
                "speed": options.speed,
                "vol": options.vol,
                "pitch": options.pitch,
            },
            "audio_setting": {
                "sample_rate": 16000,
                "bitrate": 128000,
                "format": options.file_format,
                "channel": 1,
            },
            "subtitle_enable": True,
            "output_format": output_format,
            "voice_modify": {
                "pitch": options.voice_modify_pitch,
                "intensity": options.voice_modify_intensity,
                "timbre": options.voice_modify_timbre,
            },
        }
        return body

    async def synthesize_url(
        self,
        text: str,
        options: Optional[MiniMaxSynthesisOptions] = None,
    ) -> Tuple[Optional[str], Dict]:
        if not self.config.api_key or not text or not text.strip():
            return None, {}
        resolved = options or self.config.to_synthesis_options()
        body = self._build_request_body(text, resolved, output_format="url")
        headers = {"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"}
        client = self._get_client()
        response = await client.post(self.api_url, json=body, headers=headers)
        response.raise_for_status()
        result = response.json()
        audio_url, extra_info, failure = parse_minimax_url_result(result)
        if failure:
            extra_info["failure_reason"] = failure.get("reason")
            extra_info["failure_status_code"] = failure.get("base_status_code")
            extra_info["failure_status_msg"] = failure.get("base_status_msg")
            log.warning(
                "MiniMax synthesize_url returned no audio",
                extra={
                    "account_id": self.config.account_id,
                    "voice_id": resolved.voice_id,
                    "model": resolved.model,
                    "failure": failure,
                },
            )
            return None, extra_info
        return audio_url, extra_info

    async def synthesize(
        self,
        text: str,
        options: Optional[MiniMaxSynthesisOptions] = None,
    ) -> Tuple[Optional[str], Dict]:
        if not self.config.api_key or not text or not text.strip():
            return None, {}
        resolved = options or self.config.to_synthesis_options()
        body = self._build_request_body(text, resolved, output_format="hex")
        headers = {"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"}
        client = self._get_client()
        response = await client.post(self.api_url, json=body, headers=headers)
        response.raise_for_status()
        result = response.json()
        if result.get("base_resp", {}).get("status_code") != 0:
            return None, {}
        audio_hex = result.get("data", {}).get("audio")
        if not audio_hex:
            return None, {}
        audio_bytes = bytes.fromhex(audio_hex)
        filename = f"tts_{int(time.time() * 1000)}.{resolved.file_format}"
        filepath = self.output_dir / filename
        filepath.write_bytes(audio_bytes)
        return filename, result.get("extra_info", {})

    async def synthesize_bytes(
        self,
        text: str,
        options: Optional[MiniMaxSynthesisOptions] = None,
    ) -> Tuple[Optional[bytes], Dict]:
        if not self.config.api_key or not text or not text.strip():
            return None, {}
        resolved = options or self.config.to_synthesis_options()
        body = self._build_request_body(text, resolved, output_format="hex")
        headers = {"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"}
        client = self._get_client()
        response = await client.post(self.api_url, json=body, headers=headers)
        response.raise_for_status()
        result = response.json()
        if result.get("base_resp", {}).get("status_code") != 0:
            return None, {}
        audio_hex = result.get("data", {}).get("audio")
        if not audio_hex:
            return None, {}
        return bytes.fromhex(audio_hex), result.get("extra_info", {})
