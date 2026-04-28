"use client";

import { useEffect, useRef, useState } from "react";
import ChatColumn from "@/components/ChatColumn";
import ControlBar from "@/components/ControlBar";
import ManualInput from "@/components/ManualInput";
import {
  autoConversation,
  cocoChat,
  listPersonas,
  personaChat,
  resetSession,
} from "@/lib/api";
import type {
  ChatHistoryItem,
  Mode,
  Persona,
  Speaker,
} from "@/lib/types";

const SESSION_ID = "web-demo";

export default function Home() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selectedPersona, setSelectedPersona] = useState<string>("yuyu");
  const [history, setHistory] = useState<ChatHistoryItem[]>([]);
  const [mode, setMode] = useState<Mode>("idle");
  const [turnBudget, setTurnBudget] = useState(4);
  const [nextSpeaker, setNextSpeaker] = useState<Speaker>("persona");
  const [elapsedMs, setElapsedMs] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startTimer = () => {
    const t0 = Date.now();
    setElapsedMs(0);
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setElapsedMs(Date.now() - t0);
    }, 200);
  };
  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setElapsedMs(0);
  };

  // 加载 persona 列表
  useEffect(() => {
    listPersonas()
      .then((ps) => {
        setPersonas(ps);
        if (ps.length > 0 && !ps.find((p) => p.id === selectedPersona)) {
          setSelectedPersona(ps[0].id);
        }
      })
      .catch((e) => setError(`加载 personas 失败: ${e.message}`));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 切 persona 自动 reset
  const initialLoadRef = useRef(true);
  useEffect(() => {
    if (initialLoadRef.current) {
      initialLoadRef.current = false;
      return;
    }
    resetSession()
      .then(() => {
        setHistory([]);
        setNextSpeaker("persona");
        setError(null);
      })
      .catch((e) => setError(`reset 失败: ${e.message}`));
  }, [selectedPersona]);

  const handleStart = async () => {
    setError(null);
    setMode("auto-running");
    startTimer();
    try {
      const resp = await autoConversation(
        selectedPersona,
        turnBudget,
        "persona",
        SESSION_ID,
      );
      setHistory(resp.history);
      if (resp.error) setError(resp.error);
      // 自动对话完，轮到 persona 再说（下一轮）
      setNextSpeaker("persona");
    } catch (e) {
      setError(`自动对话失败: ${(e as Error).message}`);
    } finally {
      setMode("idle");
      stopTimer();
    }
  };

  const handleStep = async () => {
    setError(null);
    setMode("loading");
    startTimer();
    try {
      if (nextSpeaker === "persona") {
        // persona 说一句
        const lastCocoMsg =
          [...history].reverse().find((h) => h.role === "coco")?.text ?? null;
        const resp = await personaChat(selectedPersona, history, lastCocoMsg);
        setHistory((h) => [
          ...h,
          { role: "persona" as const, text: resp.text },
        ]);
        setNextSpeaker("coco");
      } else {
        // coco 回一句
        const lastPersonaMsg =
          [...history].reverse().find((h) => h.role === "persona")?.text ?? "";
        if (!lastPersonaMsg) {
          throw new Error("没有 persona 消息，coco 无从回复");
        }
        const resp = await cocoChat(lastPersonaMsg, SESSION_ID);
        setHistory((h) => [
          ...h,
          {
            role: "coco" as const,
            text: resp.reply_text,
            tool_calls: resp.tool_calls,
          },
        ]);
        setNextSpeaker("persona");
      }
    } catch (e) {
      setError(`步进失败: ${(e as Error).message}`);
    } finally {
      setMode("idle");
      stopTimer();
    }
  };

  const handleReset = async () => {
    setError(null);
    try {
      await resetSession();
      setHistory([]);
      setNextSpeaker("persona");
    } catch (e) {
      setError(`reset 失败: ${(e as Error).message}`);
    }
  };

  const handleManualSend = async (text: string) => {
    setError(null);
    setMode("loading");
    startTimer();
    const personaItem: ChatHistoryItem = { role: "persona", text };
    setHistory((h) => [...h, personaItem]);
    try {
      const resp = await cocoChat(text, SESSION_ID);
      setHistory((h) => [
        ...h,
        {
          role: "coco" as const,
          text: resp.reply_text,
          tool_calls: resp.tool_calls,
        },
      ]);
      setNextSpeaker("persona");
    } catch (e) {
      setError(`Coco 回复失败: ${(e as Error).message}`);
    } finally {
      setMode("idle");
      stopTimer();
    }
  };

  return (
    <main className="flex h-screen flex-col bg-zinc-50">
      {error && (
        <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          ⚠ {error}
        </div>
      )}
      <div className="flex flex-1 overflow-hidden">
        <ChatColumn
          title="Coco（AI 心理陪伴）"
          subtitle="Fast + Slow 双层思考"
          messages={history}
          filter="coco"
          accent="sky"
        />
        <ControlBar
          personas={personas}
          selectedPersona={selectedPersona}
          onPersonaChange={setSelectedPersona}
          turnBudget={turnBudget}
          onTurnBudgetChange={setTurnBudget}
          mode={mode}
          nextSpeaker={nextSpeaker}
          onStart={handleStart}
          onStep={handleStep}
          onReset={handleReset}
          elapsedMs={elapsedMs}
        />
        <ChatColumn
          title={
            personas.find((p) => p.id === selectedPersona)?.name ??
            selectedPersona
          }
          subtitle="模拟人类 persona"
          messages={history}
          filter="persona"
          accent="pink"
        >
          <ManualInput
            onSend={handleManualSend}
            disabled={mode !== "idle"}
          />
        </ChatColumn>
      </div>
    </main>
  );
}
