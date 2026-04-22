"use client";

import type { Persona } from "@/lib/types";

interface Props {
  personas: Persona[];
  selected: string;
  onChange: (id: string) => void;
  disabled?: boolean;
}

export default function PersonaSelector({
  personas,
  selected,
  onChange,
  disabled,
}: Props) {
  const current = personas.find((p) => p.id === selected);
  return (
    <div className="w-full">
      <label className="mb-1 block text-xs font-medium text-zinc-500">
        模拟人类 persona
      </label>
      <select
        value={selected}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm text-zinc-700 focus:border-pink-400 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
      >
        {personas.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name} ({p.id})
          </option>
        ))}
      </select>
      {current && (
        <p className="mt-1 line-clamp-2 text-xs text-zinc-500">
          {current.preview}…
        </p>
      )}
    </div>
  );
}
