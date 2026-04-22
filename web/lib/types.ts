export interface Persona {
  id: string;
  name: string;
  preview: string;
}

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
}

export interface ChatHistoryItem {
  role: "coco" | "persona";
  text: string;
  tool_calls?: ToolCall[] | null;
}

export interface CocoChatResp {
  reply_text: string;
  tool_calls: ToolCall[];
  needs_deep: boolean;
  slow_history: string[];
}

export interface PersonaChatResp {
  text: string;
}

export interface AutoConvResp {
  history: ChatHistoryItem[];
  error?: string | null;
}

export type Mode = "idle" | "auto-running" | "stepping" | "loading";
export type Speaker = "persona" | "coco";
