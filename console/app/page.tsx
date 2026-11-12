"use client";

import { useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Citation = { n: number; doc: string; page: number; section: string };
type Message = {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  refusal?: string | null;
};
type Trace = {
  ts: string;
  session_id: string;
  question: string;
  refusal: string | null;
  citations: number;
  stage_ms: Record<string, number>;
  total_ms: number;
};

const ROLES = ["analyst", "engineer", "reviewer", "external"] as const;
const STAGE_LABELS: Record<string, string> = {
  condense: "Rewriting question",
  retrieve: "Retrieving evidence",
  grade: "Grading evidence",
  generate: "Drafting answer",
  attribute: "Verifying sentences",
};

export default function ConsolePage() {
  const [sessionId, setSessionId] = useState<string>("");
  const [role, setRole] = useState<(typeof ROLES)[number]>("analyst");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [traces, setTraces] = useState<Trace[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let id = localStorage.getItem("veritas-session");
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem("veritas-session", id);
    }
    setSessionId(id);
    void loadTraces();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, stage]);

  async function loadTraces() {
    try {
      const response = await fetch(`${API}/v1/trace/recent?count=15`);
      if (response.ok) {
        const body = await response.json();
        setTraces(body.traces ?? []);
      }
    } catch {
      // traces are a review aid, never block the chat
    }
  }

  async function send() {
    const question = input.trim();
    if (!question || busy) return;
    setInput("");
    setError(null);
    setBusy(true);
    setMessages((previous) => [
      ...previous,
      { role: "user", content: question },
      { role: "assistant", content: "" },
    ]);

    try {
      const response = await fetch(`${API}/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, question, role, stream: true }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({ message: response.statusText }));
        throw new Error(body.message ?? "request failed");
      }
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let frame = "";
      let citations: Citation[] = [];
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        frame += decoder.decode(value, { stream: true });
        const frames = frame.split("\n\n");
        frame = frames.pop() ?? "";
        for (const block of frames) {
          const eventLine = block.split("\n").find((l) => l.startsWith("event: "));
          const dataLine = block.split("\n").find((l) => l.startsWith("data: "));
          if (!eventLine || !dataLine) continue;
          const event = eventLine.slice(7).trim();
          const payload = JSON.parse(dataLine.slice(6));
          if (event === "token") {
            setMessages((previous) => {
              const next = [...previous];
              const last = next[next.length - 1];
              next[next.length - 1] = { ...last, content: last.content + payload.text + " " };
              return next;
            });
          } else if (event === "citations") {
            citations = payload.citations;
            setMessages((previous) => {
              const next = [...previous];
              const last = next[next.length - 1];
              next[next.length - 1] = { ...last, citations };
              return next;
            });
          } else if (event === "status") {
            setStage(STAGE_LABELS[payload.stage] ?? payload.stage);
          } else if (event === "meta") {
            setStage(null);
            setMessages((previous) => {
              const next = [...previous];
              const last = next[next.length - 1];
              next[next.length - 1] = {
                ...last,
                refusal: payload.refusal ?? null,
              };
              return next;
            });
          }
        }
      }
      void loadTraces();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "request failed");
      setMessages((previous) => previous.slice(0, -1));
    } finally {
      setBusy(false);
      setStage(null);
    }
  }

  return (
    <main className="mx-auto grid h-screen max-w-7xl grid-cols-1 gap-6 p-6 lg:grid-cols-[1fr_340px]">
      <section className="flex min-h-0 flex-col">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Veritas <span className="text-emerald-400">RAG</span>
            </h1>
            <p className="text-sm text-zinc-400">
              Every sentence answers to its evidence.
            </p>
          </div>
          <select
            value={role}
            onChange={(event) => setRole(event.target.value as (typeof ROLES)[number])}
            className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
            aria-label="Role"
          >
            {ROLES.map((value) => (
              <option key={value} value={value}>
                role: {value}
              </option>
            ))}
          </select>
        </header>

        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
          {messages.length === 0 && (
            <p className="mt-auto mb-auto text-center text-sm text-zinc-500">
              Ask a question about the ingested corpus. Answers arrive only with
              citations that survived verification; everything else is refused.
            </p>
          )}
          {messages.map((message, index) =>
            message.role === "user" ? (
              <div key={index} className="flex justify-end">
                <p className="max-w-[80%] rounded-2xl rounded-br-sm bg-emerald-700/80 px-4 py-2.5 text-sm">
                  {message.content}
                </p>
              </div>
            ) : (
              <div key={index} className="flex justify-start">
                <div
                  className={`max-w-[85%] rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm ${
                    message.refusal
                      ? "border border-amber-600/60 bg-amber-950/40 text-amber-200"
                      : "bg-zinc-800"
                  }`}
                >
                  {message.refusal ? (
                    <p className="font-medium">Refused: {message.content}</p>
                  ) : (
                    <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
                  )}
                  {message.citations && message.citations.length > 0 && (
                    <ul className="mt-3 space-y-1.5 border-t border-zinc-700/70 pt-3">
                      {message.citations.map((citation) => (
                        <li key={citation.n} className="text-xs text-zinc-400">
                          <span className="mr-1.5 rounded bg-zinc-700 px-1.5 py-0.5 font-mono text-zinc-200">
                            [{citation.n}]
                          </span>
                          {citation.doc}, page {citation.page}, {citation.section}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )
          )}
          {stage && (
            <p className="animate-pulse text-xs text-emerald-400">{stage}...</p>
          )}
          {error && <p className="text-xs text-red-400">{error}</p>}
          <div ref={bottomRef} />
        </div>

        <form
          className="mt-4 flex gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            void send();
          }}
        >
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask about the ingested documents..."
            className="flex-1 rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm outline-none focus:border-emerald-600"
            disabled={busy}
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="rounded-xl bg-emerald-600 px-6 py-3 text-sm font-medium disabled:opacity-40"
          >
            Ask
          </button>
        </form>
        <p className="mt-2 text-xs text-zinc-600">session: {sessionId}</p>
      </section>

      <aside className="hidden min-h-0 flex-col rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5 lg:flex">
        <h2 className="mb-4 text-sm font-semibold text-zinc-300">Request traces</h2>
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto text-xs">
          {traces.length === 0 && <p className="text-zinc-600">No requests yet.</p>}
          {traces.map((trace, index) => (
            <div key={index} className="rounded-xl border border-zinc-800 bg-zinc-900 p-3">
              <p className="truncate text-zinc-300">{trace.question || "(empty)"}</p>
              <p className="mt-1 text-zinc-500">
                {trace.refusal ? (
                  <span className="text-amber-400">refused: {trace.refusal}</span>
                ) : (
                  <span className="text-emerald-400">{trace.citations} citation(s)</span>
                )}
                {" · "}
                {trace.total_ms} ms
              </p>
              <p className="mt-1 text-zinc-600">
                {Object.entries(trace.stage_ms ?? {})
                  .filter(([key]) => key.endsWith("_ms"))
                  .map(([key, value]) => `${key.replace("_ms", "")} ${value}`)
                  .join(" · ")}
              </p>
            </div>
          ))}
        </div>
      </aside>
    </main>
  );
}
