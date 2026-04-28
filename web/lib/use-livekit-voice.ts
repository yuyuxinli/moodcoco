"use client";

// React hook owning the voice state machine.
// F2.md §5.2 (skeleton) + §7 (state machine) + §8 (error catalog).
// Only this module talks to React; raw SDK lives in lib/livekit.ts.
// `?mockVoiceState=` (F2 §11.3) short-circuits all real network/SDK work.

import { useCallback, useEffect, useRef, useState } from "react";
import { RemoteAudioTrack, RoomEvent, type DisconnectReason } from "livekit-client";

import { fetchVoiceToken } from "./api";
import {
  AgentTimeoutError, ConnectError, MicPermissionError,
  VoiceRoomHandle, connectToVoiceRoom, disconnectVoiceRoom,
} from "./livekit";
import type { VoiceError, VoiceErrorCode, VoiceState } from "./voice-types";

const AGENT_AUDIO_TIMEOUT_MS = 8000;
const MOCK_STATES: ReadonlySet<string> = new Set(["idle", "recording", "processing", "speaking", "error"]);
const MOCK_ERRORS: ReadonlySet<string> = new Set([
  "MIC_PERMISSION_DENIED", "TOKEN_FETCH_FAILED", "ROOM_CONNECT_FAILED",
  "ROOM_DISCONNECTED", "AGENT_AUDIO_TIMEOUT",
]);

const ERROR_COPY: Record<VoiceErrorCode, { message: string; retriable: boolean }> = {
  MIC_PERMISSION_DENIED: { message: "麦克风权限被拒绝，请在浏览器设置中允许访问麦克风", retriable: false },
  TOKEN_FETCH_FAILED:    { message: "连接服务失败，请稍后重试", retriable: true },
  ROOM_CONNECT_FAILED:   { message: "语音连接失败，请检查网络后重试", retriable: true },
  ROOM_DISCONNECTED:     { message: "通话意外断开，请重新连接", retriable: true },
  AGENT_AUDIO_TIMEOUT:   { message: "语音助手无响应，请稍后重试", retriable: true },
};

export interface UseLiveKitVoiceOptions { sessionId?: string }
export interface UseLiveKitVoiceReturn {
  state: VoiceState;
  error: VoiceError | null;
  /** Toggle: idle → start, anything else → stop. */
  toggle: () => Promise<void>;
  /** Force-disconnect (used by an explicit "结束通话" button). */
  disconnect: () => Promise<void>;
  isAgentSpeaking: boolean;
  clearError: () => void;
}

function buildError(code: VoiceErrorCode): VoiceError {
  return { code, ...ERROR_COPY[code] };
}

interface MockInit { state: VoiceState; error: VoiceError | null; isMock: boolean }

function computeMockInit(): MockInit {
  const empty: MockInit = { state: "idle", error: null, isMock: false };
  if (typeof window === "undefined" || process.env.NODE_ENV === "production") return empty;
  const p = new URLSearchParams(window.location.search);
  const ms = p.get("mockVoiceState");
  const me = p.get("mockVoiceError");
  const state = ms && MOCK_STATES.has(ms) ? (ms as VoiceState) : null;
  const error = me && MOCK_ERRORS.has(me) ? buildError(me as VoiceErrorCode) : null;
  return { state: state ?? "idle", error, isMock: state !== null || error !== null };
}

export function useLiveKitVoice(opts: UseLiveKitVoiceOptions = {}): UseLiveKitVoiceReturn {
  const sessionId = opts.sessionId ?? "web-demo";
  // Mock-state via URL param computed once via lazy initialiser to satisfy
  // React 19 rules (no setState in effect, no ref reads during render).
  const [mockInit] = useState<MockInit>(computeMockInit);
  const [state, setState] = useState<VoiceState>(mockInit.state);
  const [error, setError] = useState<VoiceError | null>(mockInit.error);

  const handleRef = useRef<VoiceRoomHandle | null>(null);
  const audioElRef = useRef<HTMLAudioElement | null>(null);
  const stateRef = useRef<VoiceState>(mockInit.state);
  const isMockRef = useRef<boolean>(mockInit.isMock);

  const transitionTo = useCallback((next: VoiceState, reason: string) => {
    const prev = stateRef.current;
    if (prev === next) return;
    stateRef.current = next;
    console.info("[voice] state transition", { from: prev, to: next, reason, sessionId });
    setState(next);
  }, [sessionId]);

  const flagError = useCallback((code: VoiceErrorCode, level: "error" | "warn" = "error") => {
    (level === "error" ? console.error : console.warn)("[voice] error", { code, sessionId });
    setError(buildError(code));
  }, [sessionId]);

  const detachAgentAudio = useCallback(() => {
    const el = audioElRef.current;
    if (!el) return;
    try { el.pause(); el.srcObject = null; } catch { /* best-effort */ }
  }, []);

  const attachAgentAudio = useCallback((track: RemoteAudioTrack) => {
    if (!audioElRef.current) {
      audioElRef.current = document.createElement("audio");
      audioElRef.current.autoplay = true;
    }
    track.attach(audioElRef.current);
    console.info("[voice] agent audio attached", { sessionId });
    transitionTo("speaking", "agent_audio_subscribed");
  }, [sessionId, transitionTo]);

  useEffect(() => {
    if (!mockInit.isMock) return;
    console.info("[voice] mock mode active", {
      mockState: mockInit.state, mockError: mockInit.error?.code ?? null, sessionId,
    });
  }, [mockInit, sessionId]);

  const start = useCallback(async () => {
    if (isMockRef.current) return;
    if (stateRef.current !== "idle") {
      console.warn("[voice] start called in non-idle state", { state: stateRef.current, sessionId });
      return;
    }
    setError(null);

    // 1. Token first — fail fast on backend errors before grabbing the mic.
    let tokenResp;
    try {
      console.info("[voice] fetching token", { sessionId });
      tokenResp = await fetchVoiceToken({ session_id: sessionId });
      console.info("[voice] token fetched", { room_name: tokenResp.room_name, sessionId });
    } catch (err) {
      console.error("[voice] token fetch failed", {
        error: err instanceof Error ? err.message : String(err), sessionId,
      });
      flagError("TOKEN_FETCH_FAILED");
      return;
    }

    // 2. Mic + connect + publish.
    let handle: VoiceRoomHandle;
    try {
      handle = await connectToVoiceRoom(tokenResp.token, tokenResp.ws_url, {
        agentAudioTimeoutMs: AGENT_AUDIO_TIMEOUT_MS,
      });
      handleRef.current = handle;
      console.info("[voice] room connected + mic published", {
        room_name: tokenResp.room_name, sessionId,
      });
    } catch (err) {
      if (err instanceof MicPermissionError) { flagError("MIC_PERMISSION_DENIED"); return; }
      // ConnectError or unknown — both surface as ROOM_CONNECT_FAILED.
      console.error("[voice] room connect failed", {
        error: err instanceof Error ? err.message : String(err),
        kind: err instanceof ConnectError ? "ConnectError" : "Unknown",
        ws_url: tokenResp.ws_url, sessionId,
      });
      flagError("ROOM_CONNECT_FAILED");
      return;
    }

    // 3. Wire disconnect handler for this connection.
    handle.room.on(RoomEvent.Disconnected, (reason: DisconnectReason | undefined) => {
      const reasonStr = reason !== undefined ? String(reason) : "unknown";
      if (handleRef.current === handle) handleRef.current = null;
      detachAgentAudio();
      if (stateRef.current !== "idle") transitionTo("idle", `room_disconnected:${reasonStr}`);
      // 1 == DisconnectReason.CLIENT_INITIATED in livekit-client v2.
      if (reason !== 1) {
        console.warn("[voice] room disconnected unexpectedly", { reason: reasonStr, sessionId });
        flagError("ROOM_DISCONNECTED", "warn");
      } else {
        console.info("[voice] room disconnected (client initiated)", { sessionId });
      }
    });

    transitionTo("recording", "mic_published");

    // 4. Wait for agent audio or timeout.
    handle.agentTrack$.then(
      (track) => { if (handleRef.current === handle) attachAgentAudio(track); },
      (err) => {
        if (handleRef.current !== handle) return;
        if (err instanceof AgentTimeoutError) {
          console.warn("[voice] agent audio timeout", { timeout_ms: err.timeoutMs, sessionId });
          flagError("AGENT_AUDIO_TIMEOUT", "warn");
          void disconnectVoiceRoom(handle);
          handleRef.current = null;
          transitionTo("idle", "agent_audio_timeout");
        }
      },
    );
  }, [attachAgentAudio, detachAgentAudio, flagError, sessionId, transitionTo]);

  const stop = useCallback(async () => {
    if (isMockRef.current) return;
    console.info("[voice] stop called", { state: stateRef.current, sessionId });
    detachAgentAudio();
    const handle = handleRef.current;
    handleRef.current = null;
    await disconnectVoiceRoom(handle);
    transitionTo("idle", "user_stop");
    setError(null);
  }, [detachAgentAudio, sessionId, transitionTo]);

  const toggle = useCallback(async () => {
    if (stateRef.current === "idle") await start(); else await stop();
  }, [start, stop]);

  const clearError = useCallback(() => setError(null), []);

  // Cleanup on unmount.
  useEffect(() => () => {
    detachAgentAudio();
    const h = handleRef.current;
    handleRef.current = null;
    void disconnectVoiceRoom(h);
  }, [detachAgentAudio]);

  return { state, error, toggle, disconnect: stop, isAgentSpeaking: state === "speaking", clearError };
}
