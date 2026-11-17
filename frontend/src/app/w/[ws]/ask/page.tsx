"use client";

import Link from "next/link";
import { Fragment, useEffect, useRef, useState } from "react";
import { ArrowUp, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/card";
import { Select, Textarea } from "@/components/ui/form";
import { api, useApi } from "@/lib/api";
import { answerBlocks, relativeTime, splitCitations } from "@/lib/format";
import type { AskResult, Citation, Message, Thread, ThreadDetail } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

const SUGGESTIONS = [
  "What did we decide about pricing?",
  "Who owns the launch checklist?",
  "What are the onboarding steps for new engineers?",
  "Which deadlines are coming up this week?",
];

function AnswerText({ text, onCite }: { text: string; onCite: (n: number) => void }) {
  const inline = (s: string) =>
    splitCitations(s).map((seg, i) =>
      seg.type === "text" ? (
        <Fragment key={i}>{seg.text}</Fragment>
      ) : (
        <button
          key={i}
          onClick={() => onCite(seg.n)}
          className="mx-0.5 inline-flex h-5 min-w-5 cursor-pointer items-center justify-center border-2 border-ink bg-acid px-1 align-text-top font-mono text-[10px] font-bold hover:bg-ink hover:text-acid"
        >
          {seg.n}
        </button>
      ),
    );
  return (
    <div className="prose-answer leading-relaxed">
      {answerBlocks(text).map((b, i) =>
        b.type === "p" ? <p key={i}>{inline(b.text)}</p> : (
          <ul key={i}>{b.items.map((it, j) => <li key={j}>{inline(it)}</li>)}</ul>
        ),
      )}
    </div>
  );
}

function SourceCard({ c, ws, active }: { c: Citation; ws: string; active: boolean }) {
  return (
    <Link
      id={`src-${c.n}`}
      href={`/w/${ws}/documents/${c.document_id}#chunk-${c.chunk_id}`}
      className={cn(
        "block border-2 border-ink bg-white p-3 transition-transform hover:-translate-x-px hover:-translate-y-px hover:shadow-[var(--shadow-hard-sm)]",
        active && "bg-acid shadow-[var(--shadow-hard-sm)]",
      )}
    >
      <div className="flex items-center gap-2">
        <span className="flex size-5 items-center justify-center bg-ink font-mono text-[10px] font-bold text-acid">{c.n}</span>
        <span className="truncate text-sm font-bold">{c.title}</span>
      </div>
      <div className="label mt-1.5 flex gap-3 text-[10px] text-muted">
        <span>{c.kind}</span>
        {c.page && <span>Page {c.page}</span>}
        <span>Match {Math.round(c.score * 100)}%</span>
      </div>
      <p className="mt-2 line-clamp-4 font-mono text-[11px] leading-relaxed text-ink/80">{c.snippet}</p>
    </Link>
  );
}

export default function AskPage() {
  const { ws, projectId, projectName } = useWorkspace();
  const { data: threads, mutate: refreshThreads } = useApi<Thread[]>(`/api/workspaces/${ws}/chat/threads`);
  const [threadId, setThreadId] = useState<string | null>(null);
  const { data: thread, mutate: refreshThread } = useApi<ThreadDetail>(threadId ? `/api/workspaces/${ws}/chat/threads/${threadId}` : null);
  const [pending, setPending] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeCite, setActiveCite] = useState<{ msg: string; n: number } | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  const messages = [...(thread?.messages ?? []), ...pending];
  const lastAnswer = [...messages].reverse().find((m) => m.role === "assistant");
  const panelMsg = messages.find((m) => m.id === activeCite?.msg) ?? lastAnswer;

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  async function send(q: string) {
    const question = q.trim();
    if (!question || busy) return;
    setBusy(true);
    setError(null);
    setInput("");
    const now = new Date().toISOString();
    setPending([{ id: "pending-q", role: "user", content: question, citations: [], confidence: null, answered: true, created_at: now }]);
    try {
      const res = await api<AskResult>(`/api/workspaces/${ws}/chat/ask`, {
        body: { question, thread_id: threadId, project_id: threadId ? undefined : projectId },
      });
      if (!threadId) setThreadId(res.thread.id);
      await Promise.all([refreshThread(), refreshThreads()]);
      setActiveCite(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
      setInput(question);
    } finally {
      setPending([]);
      setBusy(false);
    }
  }

  async function removeThread(id: string) {
    await api(`/api/workspaces/${ws}/chat/threads/${id}`, { method: "DELETE" });
    if (id === threadId) setThreadId(null);
    refreshThreads();
  }

  return (
    <div className="grid h-screen grid-cols-[minmax(0,1fr)] lg:grid-cols-[220px_minmax(0,1fr)] 2xl:grid-cols-[240px_minmax(0,1fr)_340px]">
      {/* Threads */}
      <aside className="hidden min-h-0 flex-col border-r-2 border-ink bg-paper lg:flex">
        <div className="border-b-2 border-ink p-3">
          <Button variant="accent" className="w-full" onClick={() => { setThreadId(null); setActiveCite(null); }}>
            <Plus /> New question
          </Button>
        </div>
        <p className="label border-b-2 border-ink px-3 py-2 text-muted">History</p>
        <div className="flex-1 overflow-y-auto">
          {threads?.map((t) => (
            <div
              key={t.id}
              className={cn("group flex items-start gap-2 border-b border-ink/20 px-3 py-2.5", t.id === threadId ? "bg-ink text-paper" : "hover:bg-paper-2")}
            >
              <button className="min-w-0 flex-1 cursor-pointer text-left" onClick={() => { setThreadId(t.id); setActiveCite(null); }}>
                <p className="line-clamp-2 text-sm leading-snug">{t.title}</p>
                <p className={cn("label mt-1 text-[10px]", t.id === threadId ? "text-acid" : "text-muted")}>{relativeTime(t.updated_at)}</p>
              </button>
              <button title="Delete thread" onClick={() => removeThread(t.id)} className="hidden cursor-pointer p-0.5 group-hover:block">
                <Trash2 className="size-3.5" />
              </button>
            </div>
          ))}
          {threads?.length === 0 && <p className="p-3 text-xs text-muted">Your conversations are saved here.</p>}
        </div>
      </aside>

      {/* Conversation */}
      <section className="flex min-h-0 flex-col">
        <header className="flex items-center justify-between gap-4 border-b-2 border-ink bg-paper px-8 py-4">
          <div className="min-w-0">
            <p className="label text-muted">01 / Ask your workspace</p>
            <h1 className="display mt-1 truncate text-2xl">{thread?.title ?? "New question"}</h1>
          </div>
          <div className="flex items-center gap-2 lg:hidden">
            <Select
              aria-label="Conversation history"
              className="h-8 w-48 text-xs"
              value={threadId ?? ""}
              onChange={(e) => { setThreadId(e.target.value || null); setActiveCite(null); }}
            >
              <option value="">+ New question</option>
              {threads?.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
            </Select>
          </div>
          <Badge tone="ink" className="hidden md:inline-flex">
            Scope · {thread ? projectName(thread.project_id) ?? "All projects" : projectName(projectId) ?? "All projects"}
          </Badge>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto px-8 py-8">
          {messages.length === 0 && (
            <div className="mx-auto max-w-2xl pt-10">
              <p className="display text-5xl">What do you need to know?</p>
              <p className="mt-4 text-muted">
                Answers come only from your team&apos;s documents, meeting notes and records — with citations. If nothing
                covers it, the question is logged as a knowledge gap.
              </p>
              <div className="mt-8 grid gap-3 md:grid-cols-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="cursor-pointer border-2 border-ink bg-white p-4 text-left text-sm font-bold shadow-[var(--shadow-hard-sm)] hover:bg-acid"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="ml-auto max-w-2xl border-2 border-ink bg-ink px-4 py-3 text-paper">
                {m.content}
              </div>
            ) : (
              <div
                key={m.id}
                className={cn("max-w-3xl border-2 border-ink bg-white shadow-[var(--shadow-hard)]", !m.answered && "bg-paper-2")}
              >
                <div className="flex items-center justify-between border-b-2 border-ink px-4 py-1.5">
                  <span className="label text-[10px] font-bold">{m.answered ? "Answer" : "Not in workspace"}</span>
                  {m.answered && (
                    <span className="label text-[10px] text-muted">
                      {m.citations.length} source{m.citations.length === 1 ? "" : "s"}
                    </span>
                  )}
                </div>
                <div className="px-4 py-3">
                  <AnswerText
                    text={m.content}
                    onCite={(n) => {
                      setActiveCite({ msg: m.id, n });
                      document.getElementById(`cite-${m.id}-${n}`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
                    }}
                  />
                </div>
                {m.citations.length > 0 && (
                  <div className="grid gap-px border-t-2 border-ink bg-ink 2xl:hidden">
                    {m.citations.map((c) => (
                      <Link
                        key={c.chunk_id}
                        id={`cite-${m.id}-${c.n}`}
                        href={`/w/${ws}/documents/${c.document_id}#chunk-${c.chunk_id}`}
                        className={cn(
                          "flex min-w-0 items-baseline gap-3 bg-paper px-4 py-2 text-sm hover:bg-acid [&>span:nth-child(2)]:shrink-0",
                          activeCite?.msg === m.id && activeCite.n === c.n && "bg-acid",
                        )}
                      >
                        <span className="font-mono text-[10px] font-bold">[{c.n}]</span>
                        <span className="font-bold">{c.title}</span>
                        {c.page && <span className="label text-[10px] text-muted">p.{c.page}</span>}
                        <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-muted">{c.snippet}</span>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ),
          )}
          {busy && (
            <div className="label max-w-3xl border-2 border-dashed border-ink px-4 py-3">
              Searching workspace<span className="cursor-blink">_</span>
            </div>
          )}
          <div ref={bottom} />
        </div>

        <form
          onSubmit={(e) => { e.preventDefault(); send(input); }}
          className="border-t-2 border-ink bg-paper p-4"
        >
          {error && <p className="mb-2 border-2 border-ink bg-signal px-3 py-1.5 font-mono text-xs">{error}</p>}
          <div className="flex gap-3">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              placeholder={threadId ? "Ask a follow-up…" : "Ask a question about your team's work…"}
              className="min-h-12 resize-none"
              rows={2}
            />
            <Button type="submit" size="lg" variant="accent" disabled={busy || !input.trim()} className="h-auto">
              <ArrowUp /> Ask
            </Button>
          </div>
          <p className="label mt-2 text-[10px] text-muted">Enter to send · Shift+Enter for a new line</p>
        </form>
      </section>

      {/* Sources */}
      <aside className="hidden min-h-0 flex-col border-l-2 border-ink bg-paper-2 2xl:flex">
        <p className="label border-b-2 border-ink bg-paper px-4 py-3 font-bold">Sources</p>
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {panelMsg?.citations.length ? (
            panelMsg.citations.map((c) => (
              <SourceCard key={c.chunk_id} c={c} ws={ws} active={activeCite?.msg === panelMsg.id && activeCite.n === c.n} />
            ))
          ) : (
            <p className="text-sm text-muted">Cited passages appear here. Click a source to open it at the exact passage.</p>
          )}
        </div>
      </aside>
    </div>
  );
}
