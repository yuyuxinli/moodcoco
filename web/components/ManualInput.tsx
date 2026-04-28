"use client";

import { Send } from "lucide-react";
import { useState } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export default function ManualInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState("");

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  return (
    <div className="border-t border-zinc-200 bg-white p-3">
      <div className="flex gap-2">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          disabled={disabled}
          rows={2}
          placeholder="以 persona 身份手动发言（回车发送 / Shift+Enter 换行）"
          className="flex-1 resize-none rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-800 placeholder:text-zinc-400 focus:border-pink-400 focus:outline-none disabled:opacity-50"
        />
        <button
          onClick={submit}
          disabled={disabled || !value.trim()}
          className="flex items-center gap-1 rounded-md bg-pink-500 px-3 py-2 text-sm font-medium text-white hover:bg-pink-600 disabled:cursor-not-allowed disabled:bg-pink-300"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
