"use client";

// VoiceButton — press-to-toggle voice entry. F2.md §3.2 visual states.
// Owns the useLiveKitVoice hook so callers don't have to plumb props.

import { Loader2, Mic, MicOff, PhoneOff, Volume2 } from "lucide-react";
import type { ReactNode } from "react";

import { useLiveKitVoice } from "@/lib/use-livekit-voice";
import type { VoiceState } from "@/lib/voice-types";

interface Props {
  /** Session id passed to /api/voice/token. Defaults to "web-demo". */
  sessionId?: string;
  /** Disable the button (e.g. while text chat is busy). */
  disabled?: boolean;
}

interface StateConfig {
  label: string;
  icon: ReactNode;
  buttonClass: string;
  testId: string;
}

const STATE_CONFIG: Record<VoiceState, StateConfig> = {
  idle: {
    label: "语音通话",
    icon: <Mic className="h-4 w-4" />,
    buttonClass: "bg-teal-500 text-white hover:bg-teal-600 disabled:bg-teal-300",
    testId: "voice-btn-idle",
  },
  recording: {
    label: "录音中…",
    icon: <MicOff className="h-4 w-4" />,
    buttonClass:
      "bg-teal-600 text-white ring-2 ring-teal-300 animate-pulse disabled:bg-teal-400",
    testId: "voice-btn-recording",
  },
  processing: {
    label: "处理中…",
    icon: <Loader2 className="h-4 w-4 animate-spin" />,
    buttonClass: "bg-amber-500 text-white hover:bg-amber-600 disabled:bg-amber-300",
    testId: "voice-btn-processing",
  },
  speaking: {
    label: "播放中…",
    icon: <Volume2 className="h-4 w-4" />,
    buttonClass:
      "bg-sky-500 text-white animate-pulse hover:bg-sky-600 disabled:bg-sky-300",
    testId: "voice-btn-speaking",
  },
  // `error` is a pseudo-state used by ?mockVoiceState=error so C can capture
  // the error banner without depending on a real backend failure.
  error: {
    label: "语音通话",
    icon: <Mic className="h-4 w-4" />,
    buttonClass: "bg-teal-500 text-white hover:bg-teal-600 disabled:bg-teal-300",
    testId: "voice-btn-idle",
  },
};

export default function VoiceButton({
  sessionId = "web-demo",
  disabled = false,
}: Props) {
  const { state, error, toggle, disconnect, clearError } =
    useLiveKitVoice({ sessionId });

  const isActive = state !== "idle" && state !== "error";
  const config = STATE_CONFIG[state];

  const handleToggle = () => {
    void toggle();
  };
  const handleEndCall = () => {
    void disconnect();
  };

  return (
    <div className="flex flex-col gap-1.5" data-testid="voice-section">
      <button
        type="button"
        onClick={handleToggle}
        disabled={disabled}
        data-testid={config.testId}
        aria-label={config.label}
        className={`flex w-full items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium disabled:cursor-not-allowed ${config.buttonClass}`}
      >
        {config.icon}
        {config.label}
      </button>

      {isActive && (
        <button
          type="button"
          onClick={handleEndCall}
          disabled={disabled}
          data-testid="voice-btn-end-call"
          className="flex w-full items-center justify-center gap-2 rounded-md border border-red-300 bg-white px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <PhoneOff className="h-4 w-4" />
          结束通话
        </button>
      )}

      {error && (
        <div
          role="alert"
          data-testid="voice-error-banner"
          className="flex items-start justify-between gap-1 rounded-md bg-red-50 px-2 py-1.5 text-xs text-red-700"
        >
          <span>{error.message}</span>
          <button
            type="button"
            onClick={clearError}
            aria-label="关闭错误提示"
            className="shrink-0 font-bold hover:text-red-900"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
