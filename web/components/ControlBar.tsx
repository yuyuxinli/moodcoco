"use client";

import { Play, RotateCcw, SkipForward } from "lucide-react";
import type { Mode, Persona, Speaker } from "@/lib/types";
import PersonaSelector from "./PersonaSelector";

interface Props {
  personas: Persona[];
  selectedPersona: string;
  onPersonaChange: (id: string) => void;
  turnBudget: number;
  onTurnBudgetChange: (n: number) => void;
  mode: Mode;
  nextSpeaker: Speaker;
  onStart: () => void;
  onStep: () => void;
  onReset: () => void;
  elapsedMs: number;
}

export default function ControlBar({
  personas,
  selectedPersona,
  onPersonaChange,
  turnBudget,
  onTurnBudgetChange,
  mode,
  nextSpeaker,
  onStart,
  onStep,
  onReset,
  elapsedMs,
}: Props) {
  const busy = mode === "auto-running" || mode === "loading";
  const modeLabel =
    mode === "auto-running"
      ? `自动对话中…${(elapsedMs / 1000).toFixed(0)}s`
      : mode === "loading"
      ? `等待回复…${(elapsedMs / 1000).toFixed(0)}s`
      : mode === "stepping"
      ? `步进中 · 下一步: ${nextSpeaker === "persona" ? "玩家" : "Coco"}`
      : "待机";

  return (
    <div className="flex h-full w-72 flex-col justify-between border-x border-zinc-200 bg-zinc-50 p-4">
      <div className="space-y-4">
        <div>
          <h1 className="text-base font-semibold text-zinc-800">
            moodcoco · 双 AI 对话
          </h1>
          <p className="mt-1 text-xs text-zinc-500">{modeLabel}</p>
        </div>

        <PersonaSelector
          personas={personas}
          selected={selectedPersona}
          onChange={onPersonaChange}
          disabled={busy}
        />

        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-500">
            自动对话轮数 (1-8)
          </label>
          <input
            type="number"
            min={1}
            max={8}
            value={turnBudget}
            disabled={busy}
            onChange={(e) =>
              onTurnBudgetChange(
                Math.max(1, Math.min(8, Number(e.target.value) || 1)),
              )
            }
            className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm text-zinc-700 focus:border-pink-400 focus:outline-none disabled:opacity-50"
          />
          <p className="mt-1 text-xs text-zinc-400">
            1 轮 = persona 说一句 + Coco 回一句
          </p>
        </div>

        <div className="space-y-2 pt-2">
          <button
            onClick={onStart}
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-md bg-pink-500 px-3 py-2 text-sm font-medium text-white hover:bg-pink-600 disabled:cursor-not-allowed disabled:bg-pink-300"
          >
            <Play className="h-4 w-4" />
            开始自动对话
          </button>
          <button
            onClick={onStep}
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <SkipForward className="h-4 w-4" />
            单步
          </button>
          <button
            onClick={onReset}
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RotateCcw className="h-4 w-4" />
            重置会话
          </button>
        </div>
      </div>

      <div className="text-xs text-zinc-400 leading-relaxed">
        <p>左侧 Coco（Fast/Slow 双层）</p>
        <p>右侧 模拟人类（persona 角色扮演）</p>
        <p className="mt-2">右栏底部可手动发言替代 persona</p>
      </div>
    </div>
  );
}
