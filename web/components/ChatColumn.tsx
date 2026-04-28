"use client";

import { useEffect, useRef } from "react";
import type { ChatHistoryItem } from "@/lib/types";
import MessageBubble from "./MessageBubble";
import VoiceButton from "./voice/VoiceButton";

interface Props {
  title: string;
  subtitle?: string;
  messages: ChatHistoryItem[];
  filter: "coco" | "persona";
  accent: "sky" | "pink";
  children?: React.ReactNode;
}

export default function ChatColumn({
  title,
  subtitle,
  messages,
  filter,
  accent,
  children,
}: Props) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length]);

  const headerColor =
    accent === "sky"
      ? "bg-sky-50 border-sky-200 text-sky-900"
      : "bg-pink-50 border-pink-200 text-pink-900";

  // 按时间顺序，只把 filter 匹配的气泡靠本侧；不匹配的占位透明
  // 简化：只渲染匹配的消息
  const side = filter === "coco" ? "left" : "right";

  return (
    <div className="flex h-full flex-1 flex-col bg-white">
      <div
        className={`border-b ${headerColor} px-4 py-3`}
      >
        <h2 className="text-sm font-semibold">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xs opacity-75">{subtitle}</p>}
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <p className="pt-8 text-center text-xs text-zinc-400">
            还没有消息
          </p>
        )}
        {messages
          .filter((m) => m.role === filter)
          .map((m, i) => (
            <MessageBubble key={i} item={m} side={side} />
          ))}
        <div ref={endRef} />
      </div>
      {filter === "coco" && (
        <div className="border-t border-zinc-200 bg-white p-3">
          <VoiceButton />
        </div>
      )}
      {children}
    </div>
  );
}
