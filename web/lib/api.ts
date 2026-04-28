import type {
  AutoConvResp,
  ChatHistoryItem,
  CocoChatResp,
  Persona,
  PersonaChatResp,
  Speaker,
} from "./types";
import type {
  VoiceTokenRequest,
  VoiceTokenResponse,
} from "./voice-types";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text.slice(0, 200)}`);
  }
  return (await res.json()) as T;
}

export function listPersonas(): Promise<Persona[]> {
  return request<Persona[]>("/api/personas");
}

export function cocoChat(
  user_msg: string,
  session_id = "web-demo",
): Promise<CocoChatResp> {
  return request<CocoChatResp>("/api/coco/chat", {
    method: "POST",
    body: JSON.stringify({ user_msg, session_id }),
  });
}

export function personaChat(
  persona_id: string,
  history: ChatHistoryItem[],
  latest_coco_msg: string | null,
): Promise<PersonaChatResp> {
  return request<PersonaChatResp>("/api/persona/chat", {
    method: "POST",
    body: JSON.stringify({ persona_id, history, latest_coco_msg }),
  });
}

export function autoConversation(
  persona_id: string,
  turns: number,
  starter: Speaker = "persona",
  session_id = "web-demo",
): Promise<AutoConvResp> {
  return request<AutoConvResp>("/api/auto-conversation", {
    method: "POST",
    body: JSON.stringify({ persona_id, turns, starter, session_id }),
  });
}

export function resetSession(): Promise<{ status: string }> {
  return request<{ status: string }>("/api/reset", { method: "POST" });
}

/**
 * POST /api/voice/token — fetch a LiveKit room access JWT.
 * Contract authored in F2.md §6.1; F9 backend conforms to this signature.
 */
export function fetchVoiceToken(
  req: VoiceTokenRequest,
): Promise<VoiceTokenResponse> {
  return request<VoiceTokenResponse>("/api/voice/token", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
