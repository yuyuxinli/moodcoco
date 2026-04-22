"use client";

import {
  AlertTriangle,
  Flag,
  ListChecks,
  Smile,
  Sparkles,
  Wind,
  Wrench,
} from "lucide-react";
import type { ToolCall } from "@/lib/types";

export default function ToolCallCard({ tc }: { tc: ToolCall }) {
  const { name, args } = tc;

  if (name === "ai_options") {
    const opts = (args.options as (string | { id?: string; text?: string })[]) ?? [];
    const text = (args.text as string) ?? "";
    return (
      <div className="mt-2 rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-700">
        <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-zinc-500">
          <ListChecks className="h-3.5 w-3.5" />
          options
        </div>
        {text && <div className="mb-2 text-zinc-600">{text}</div>}
        <div className="flex flex-col gap-1">
          {opts.map((o, i) => {
            const label =
              typeof o === "string" ? o : (o.text ?? JSON.stringify(o));
            return (
              <div
                key={i}
                className="rounded-md border border-zinc-200 bg-white px-2.5 py-1.5 text-zinc-700"
              >
                {label}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (name === "ai_safety_brake") {
    const risk = (args.risk_level as string) ?? "unknown";
    const response = (args.response as string) ?? "";
    const riskColor =
      risk === "high"
        ? "bg-red-50 border-red-300 text-red-800"
        : risk === "medium"
        ? "bg-orange-50 border-orange-300 text-orange-800"
        : "bg-yellow-50 border-yellow-300 text-yellow-800";
    return (
      <div
        className={`mt-2 rounded-xl border p-3 text-sm ${riskColor}`}
      >
        <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold">
          <AlertTriangle className="h-3.5 w-3.5" />
          安全警报 · risk={risk}
        </div>
        {response && <div>{response}</div>}
      </div>
    );
  }

  // 4 种降级为 debug chip
  const icon =
    name === "ai_mood_select" ? (
      <Smile className="h-3.5 w-3.5" />
    ) : name === "ai_praise_popup" ? (
      <Sparkles className="h-3.5 w-3.5" />
    ) : name === "ai_body_sensation" ? (
      <Wind className="h-3.5 w-3.5" />
    ) : name === "ai_complete_conversation" ? (
      <Flag className="h-3.5 w-3.5" />
    ) : (
      <Wrench className="h-3.5 w-3.5" />
    );

  const summary = Object.entries(args)
    .map(([k, v]) => {
      const val = typeof v === "string" ? v : JSON.stringify(v);
      return `${k}: ${val.length > 50 ? val.slice(0, 50) + "…" : val}`;
    })
    .join(" · ");

  return (
    <div className="mt-2 inline-flex max-w-full items-start gap-1.5 rounded-lg border border-zinc-200 bg-zinc-100 px-2.5 py-1.5 text-xs text-zinc-600">
      {icon}
      <span className="font-mono font-medium">{name}</span>
      {summary && <span className="truncate text-zinc-500">· {summary}</span>}
    </div>
  );
}
