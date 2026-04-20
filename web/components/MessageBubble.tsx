"use client";

import type { ChatHistoryItem } from "@/lib/types";
import ToolCallCard from "./ToolCallCard";

interface Props {
  item: ChatHistoryItem;
  side: "left" | "right";
}

export default function MessageBubble({ item, side }: Props) {
  const isLeft = side === "left";
  const bubbleColor = isLeft
    ? "bg-sky-100 text-sky-950 border-sky-200"
    : "bg-pink-100 text-pink-950 border-pink-200";

  const textContent = item.text?.trim();

  // 过滤出非 ai_message 的 tool call 展示为卡片
  const nonMessageTools =
    item.tool_calls?.filter((tc) => tc.name !== "ai_message") ?? [];

  return (
    <div className={`flex ${isLeft ? "justify-start" : "justify-end"}`}>
      <div className="max-w-[85%]">
        {textContent && (
          <div
            className={`rounded-2xl border px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${bubbleColor}`}
          >
            {textContent}
          </div>
        )}
        {nonMessageTools.map((tc, i) => (
          <ToolCallCard key={i} tc={tc} />
        ))}
      </div>
    </div>
  );
}
