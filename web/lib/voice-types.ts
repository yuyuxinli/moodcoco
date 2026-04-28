// Voice types for the LiveKit-backed voice entry.
// F2.md §5.1 / §6 — authoritative shape; F9 backend must match VoiceTokenResponse.

/**
 * The 5 states of the voice state machine.
 * `idle / recording / processing / speaking` are the 4 functional states from
 * F2 §7. `error` is a non-functional pseudo-state used for rendering when an
 * error occurred while still being conceptually "idle" — it is set by the
 * `?mockVoiceState=error` debug override (F2 §11.3) and lets C take a clean
 * screenshot of the error UI without depending on a real failure path.
 */
export type VoiceState =
  | "idle"
  | "recording"
  | "processing"
  | "speaking"
  | "error";

/** Discrete error codes surfaced to the UI (F2 §8 + §5.1). */
export type VoiceErrorCode =
  | "MIC_PERMISSION_DENIED"
  | "TOKEN_FETCH_FAILED"
  | "ROOM_CONNECT_FAILED"
  | "ROOM_DISCONNECTED"
  | "AGENT_AUDIO_TIMEOUT";

export interface VoiceError {
  code: VoiceErrorCode;
  message: string;
  /** Whether the user can usefully press the button again immediately. */
  retriable: boolean;
}

/** POST /api/voice/token request body (F2 §6.1). */
export interface VoiceTokenRequest {
  session_id: string;
  /** Optional. Backend generates `voice-{session_id}-{uuid4[:8]}` if omitted. */
  room_name?: string;
}

/** POST /api/voice/token response body (F2 §6.1). */
export interface VoiceTokenResponse {
  /** LiveKit JWT access token (signed by F9 with LIVEKIT_API_KEY/SECRET). */
  token: string;
  /** LiveKit SFU WebSocket URL, e.g. "wss://demo.livekit.cloud". */
  ws_url: string;
  /** Canonical room name (echo of input or generated value). */
  room_name: string;
}
