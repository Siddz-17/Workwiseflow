"use client";

import Link from "next/link";
import { useState } from "react";
import { BadgeCheck, Check, Radar, X } from "lucide-react";

import { PageHeader } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, Empty } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/form";
import { api, qs, useApi } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { Gaps, Question } from "@/lib/types";
import { useWorkspace } from "@/lib/workspace";

export default function GapsPage() {
  const { ws, projectId, can } = useWorkspace();
  const { data, mutate } = useApi<Gaps>(`/api/workspaces/${ws}/gaps${qs({ project_id: projectId })}`);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<string | null>(null);
  const [answering, setAnswering] = useState<Question | null>(null);
  const [answer, setAnswer] = useState("");
  const member = can("member");

  async function scan() {
    setScanning(true);
    try {
      const r = await api<{ new_conflicts: number }>(`/api/workspaces/${ws}/gaps/scan`, { method: "POST" });
      setScanResult(r.new_conflicts ? `${r.new_conflicts} new conflict(s) found` : "No new conflicts found");
      mutate();
    } finally {
      setScanning(false);
    }
  }

  async function setQuestion(id: string, body: Record<string, unknown>) {
    await api(`/api/workspaces/${ws}/questions/${id}`, { method: "PATCH", body });
    mutate();
  }

  return (
    <>
      <PageHeader
        index="06"
        title="Knowledge gaps"
        subtitle="Questions nobody has answered, documents that may be out of date, and sources that contradict each other."
        actions={member && (
          <>
            {scanResult && <span className="label text-muted">{scanResult}</span>}
            <Button variant="accent" onClick={scan} disabled={scanning}><Radar /> {scanning ? "Scanning…" : "Scan for conflicts"}</Button>
          </>
        )}
      />
      <div className="space-y-8 p-10">
        <div className="grid grid-cols-3 gap-5">
          {[
            ["Unanswered questions", data?.questions.length],
            ["Possibly outdated", data?.outdated.length],
            ["Conflicts", data?.conflicts.length],
          ].map(([k, v]) => (
            <div key={String(k)} className={`border-2 border-ink p-4 shadow-[var(--shadow-hard)] ${Number(v) > 0 ? "bg-signal" : "bg-white"}`}>
              <p className="label text-[10px]">{k}</p>
              <p className="display mt-2 text-5xl">{v ?? "–"}</p>
            </div>
          ))}
        </div>

        <Card>
          <CardHeader index="!" title="Conflicting information" />
          {data?.conflicts.length ? (
            data.conflicts.map((c) => (
              <div key={c.id} className="border-b-2 border-ink last:border-0">
                <div className="flex items-center justify-between gap-4 bg-paper-2 px-4 py-2">
                  <p className="text-sm font-bold">{c.explanation}</p>
                  <div className="flex items-center gap-2">
                    <Badge tone="ink">{c.kind}</Badge>
                    {member && (
                      <>
                        <Button size="sm" variant="outline" onClick={() => api(`/api/workspaces/${ws}/conflicts/${c.id}`, { method: "PATCH", body: { status: "resolved" } }).then(() => mutate())}>
                          <Check /> Resolved
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => api(`/api/workspaces/${ws}/conflicts/${c.id}`, { method: "PATCH", body: { status: "dismissed" } }).then(() => mutate())}>
                          <X /> Not a conflict
                        </Button>
                      </>
                    )}
                  </div>
                </div>
                <div className="grid md:grid-cols-2">
                  {[[c.a_label, c.a_text], [c.b_label, c.b_text]].map(([label, text], i) => (
                    <div key={i} className={`p-4 ${i === 1 ? "border-t-2 border-ink md:border-l-2 md:border-t-0" : ""}`}>
                      <p className="label mb-2 text-[10px] text-muted">{i === 0 ? "A" : "B"} · {label}</p>
                      <p className="font-mono text-xs leading-relaxed">{text}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))
          ) : (
            <div className="p-4"><Empty title="No conflicts">New decisions are checked automatically. Run a scan to compare documents.</Empty></div>
          )}
        </Card>

        <Card>
          <CardHeader index="?" title="Unanswered questions" />
          {data?.questions.length ? (
            data.questions.map((q) => (
              <div key={q.id} className="flex items-center justify-between gap-4 border-b-2 border-ink px-4 py-3 last:border-0">
                <div>
                  <p className="font-bold">{q.question}</p>
                  <p className="label mt-1 text-[10px] text-muted">
                    {q.source === "chat" ? `Asked in chat ${q.times_asked}× · nothing in the workspace answered it` : "Raised in a meeting"} · {relativeTime(q.created_at)}
                    {q.meeting_id && <> · <Link className="underline" href={`/w/${ws}/meetings/${q.meeting_id}`}>meeting</Link></>}
                  </p>
                </div>
                {member && (
                  <div className="flex shrink-0 gap-2">
                    <Button size="sm" variant="accent" onClick={() => { setAnswering(q); setAnswer(""); }}>Answer</Button>
                    <Button size="sm" variant="ghost" onClick={() => setQuestion(q.id, { status: "dismissed" })}>Dismiss</Button>
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="p-4"><Empty title="No open questions" /></div>
          )}
        </Card>

        <Card>
          <CardHeader index="⌛" title="Possibly outdated documents" />
          {data?.outdated.length ? (
            data.outdated.map(({ document: d, reason }) => (
              <div key={d.id} className="flex items-center justify-between gap-4 border-b-2 border-ink px-4 py-3 last:border-0">
                <div>
                  <Link href={`/w/${ws}/documents/${d.id}`} className="font-bold hover:underline">{d.title}</Link>
                  <p className="label mt-1 text-[10px] text-muted">{reason}</p>
                </div>
                {member && !d.superseded_by_id && (
                  <Button size="sm" variant="outline" onClick={() => api(`/api/workspaces/${ws}/documents/${d.id}/verify`, { method: "POST" }).then(() => mutate())}>
                    <BadgeCheck /> Still accurate
                  </Button>
                )}
              </div>
            ))
          ) : (
            <div className="p-4"><Empty title="Everything is fresh" /></div>
          )}
        </Card>
      </div>

      <Dialog open={!!answering} onOpenChange={(o) => !o && setAnswering(null)}>
        <DialogContent title="Answer question" description={answering?.question}>
          <div className="space-y-4">
            <Textarea value={answer} onChange={(e) => setAnswer(e.target.value)} className="min-h-40" placeholder="Write the answer your team should find next time…" />
            <p className="font-mono text-[11px] text-muted">The answer is saved to the workspace as a record, so the next person who asks gets it — with a citation.</p>
            <Button
              variant="accent"
              className="w-full"
              disabled={!answer.trim()}
              onClick={async () => {
                if (!answering) return;
                await setQuestion(answering.id, { status: "answered", answer, save_as_document: true });
                setAnswering(null);
              }}
            >
              Save answer to workspace
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
