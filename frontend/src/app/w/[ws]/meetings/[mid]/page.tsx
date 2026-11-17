"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FileText, RefreshCw, Trash2 } from "lucide-react";

import { ActionRow, DecisionRow } from "@/components/records";
import { PageHeader, StatusPill } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, Empty } from "@/components/ui/card";
import { api, useApi } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { MeetingDetail } from "@/lib/types";
import { useWorkspace } from "@/lib/workspace";

export default function MeetingPage() {
  const { mid } = useParams<{ mid: string }>();
  const router = useRouter();
  const { ws, can } = useWorkspace();
  const path = `/api/workspaces/${ws}/meetings/${mid}`;
  const { data: m, mutate } = useApi<MeetingDetail>(path, {
    refreshInterval: (x) => (x && (x.status === "pending" || x.status === "processing") ? 1500 : 0),
  });
  if (!m) return <p className="label m-10">Loading…</p>;
  const working = m.status === "pending" || m.status === "processing";

  return (
    <>
      <PageHeader
        index="03"
        title={m.title}
        subtitle={<span className="font-mono text-sm">{formatDate(m.held_on, { weekday: "long" })}</span>}
        actions={
          <>
            {m.document_id && (
              <Button variant="outline" asChild>
                <Link href={`/w/${ws}/documents/${m.document_id}`}><FileText /> Transcript</Link>
              </Button>
            )}
            {can("member") && (
              <>
                <Button variant="outline" size="icon" title="Re-run extraction" onClick={() => api(`${path}/reprocess`, { method: "POST" }).then(() => mutate())}>
                  <RefreshCw />
                </Button>
                <Button
                  variant="danger"
                  size="icon"
                  title="Delete meeting"
                  onClick={async () => {
                    if (!confirm("Delete this meeting, its transcript and everything extracted from it?")) return;
                    await api(path, { method: "DELETE" });
                    router.push(`/w/${ws}/meetings`);
                  }}
                >
                  <Trash2 />
                </Button>
              </>
            )}
          </>
        }
      />
      <div className="space-y-8 p-10">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
          <Card>
            <CardHeader index="Σ" title="Summary" action={<StatusPill status={m.status} />} />
            <p className="p-5 text-lg leading-relaxed">
              {working ? "Reading the transcript and extracting decisions, actions and questions…" : m.summary || "—"}
            </p>
            {m.error && <p className="border-t-2 border-ink bg-signal p-3 font-mono text-xs">{m.error}</p>}
          </Card>
          <Card>
            <CardHeader title="Attendees" />
            <div className="flex flex-wrap gap-2 p-4">
              {m.attendees.length ? m.attendees.map((a) => <Badge key={a}>{a}</Badge>) : <span className="text-sm text-muted">Not detected</span>}
            </div>
          </Card>
        </div>

        <Card>
          <CardHeader index="D" title={`Decisions · ${m.decisions.length}`} />
          {m.decisions.length ? m.decisions.map((d) => (
            <div key={d.id}>
              <DecisionRow d={d} />
              {d.source_quote && (
                <blockquote className="mx-4 mb-3 border-l-4 border-ink bg-paper-2 px-3 py-1.5 font-mono text-xs">“{d.source_quote}”</blockquote>
              )}
            </div>
          )) : <div className="p-4"><Empty title={working ? "Extracting…" : "No decisions found"} /></div>}
        </Card>

        <Card>
          <CardHeader index="A" title={`Action items · ${m.action_items.length}`} />
          {m.action_items.length ? (
            m.action_items.map((a) => <ActionRow key={a.id} a={a} onChange={() => mutate()} showMeeting={false} />)
          ) : (
            <div className="p-4"><Empty title={working ? "Extracting…" : "No action items found"} /></div>
          )}
        </Card>

        <Card>
          <CardHeader index="?" title={`Open questions · ${m.open_questions.length}`} />
          {m.open_questions.length ? (
            <ul>
              {m.open_questions.map((q) => (
                <li key={q.id} className="flex items-center justify-between gap-4 border-b-2 border-ink px-4 py-3 last:border-0">
                  <span>{q.question}</span>
                  <Badge tone={q.status === "open" ? "signal" : "ok"}>{q.status}</Badge>
                </li>
              ))}
            </ul>
          ) : (
            <div className="p-4"><Empty title={working ? "Extracting…" : "No open questions"} /></div>
          )}
        </Card>
      </div>
    </>
  );
}
