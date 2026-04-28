from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MiniMaxSynthesisOptions:
    model: str = "speech-2.6-hd"
    voice_id: str = "male-qn-qingse"
    speed: float = 1.0
    vol: float = 1.0
    pitch: int = 0
    voice_modify_pitch: int = -16
    voice_modify_intensity: int = -24
    voice_modify_timbre: int = 0
    file_format: str = "mp3"


@dataclass(frozen=True)
class MiniMaxAccountConfig:
    account_id: str
    api_key: str
    model: str = "speech-2.6-hd"
    voice_id: str = "male-qn-qingse"
    speed: float = 1.0
    vol: float = 1.0
    pitch: int = 0
    voice_modify_pitch: int = -16
    voice_modify_intensity: int = -24
    voice_modify_timbre: int = 0
    file_format: str = "mp3"
    enabled: bool = True
    priority: int = 100
    max_inflight: int = 8

    def to_synthesis_options(self) -> MiniMaxSynthesisOptions:
        return MiniMaxSynthesisOptions(
            model=self.model,
            voice_id=self.voice_id,
            speed=self.speed,
            vol=self.vol,
            pitch=self.pitch,
            voice_modify_pitch=self.voice_modify_pitch,
            voice_modify_intensity=self.voice_modify_intensity,
            voice_modify_timbre=self.voice_modify_timbre,
            file_format=self.file_format,
        )
