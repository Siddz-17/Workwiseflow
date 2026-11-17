"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BadgeCheck, Plus, Quote } from "lucide-react";

import { DecisionStatusBadge } from "@/components/records";
import { PageHeader } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { Card, Empty } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { api, qs, useApi } from "@/lib/api";
import { formatDate, relativeTime } from "@/lib/format";
import type { Decision, DecisionStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

const STATUSES: DecisionStatus[] = ["active", "proposed", "superseded", "revoked"];

export default function DecisionsPage() {
  const { ws, projectId, projectName, projects, can } = useWorkspace();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 300);
    return () => clearTimeout(t);
  }, [q]);
  const { data, mutate } = useApi<Decision[]>(
    `/api/workspaces/${ws}/decisions${qs({ q: debounced, status, project_id: projectId })}`,
    { keepPreviousData: true },
  );
  const { data: all } = useApi<Decision[]>(`/api/workspaces/${ws}/decisions`);
  const current = data?.find((d) => d.id === selected) ?? data?.[0];
  const byId = new Map((all ?? []).map((d) => [d.id, d]));

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", rationale: "", approved_by: "", decided_on: "", project_id: "" });

  async function patch(id: string, body: Record<string, unknown>) {
    await api(`/api/workspaces/${ws}/decisions/${id}`, { method: "PATCH", body });
    mutate();
  }

  async function create() {
    await api(`/api/workspaces/${ws}/decisions`, {
      body: { ...form, decided_on: form.decided_on || null, project_id: form.project_id || null },
    });
    setOpen(false);
    setForm({ title: "", rationale: "", approved_by: "", decided_on: "", project_id: "" });
    mutate();
  }

  const editable = can("member");
  const supersededBy = current?.superseded_by_id ? byId.get(current.superseded_by_id) : undefined;
  const supersedes = (all ?? []).filter((d) => d.superseded_by_id === current?.id);

  return (
    <>
      <PageHeader
        index="04"
        title="Decisions"
        subtitle="What was decided, why, who approved it — and whether it still stands."
        actions={editable && (
          <Button variant="accent" onClick={() => { setForm((f) => ({ ...f, project_id: projectId ?? "" })); setOpen(true); }}>
            <Plus /> Record decision
          </Button>
        )}
      />
      <div className="p-10">
        <div className="mb-6 flex gap-3">
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search decisions — e.g. “billing”, “hiring”, “Q3 launch”" className="max-w-xl" />
          <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-44">
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </Select>
        </div>

        {data && data.length === 0 ? (
          <Empty title={debounced ? "No matches" : "No decisions yet"}>
            {debounced ? "Try a broader term." : "Decisions are extracted automatically from meetings, or record one manually."}
          </Empty>
        ) : (
          <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_420px]">
            <Card className="self-start">
              {data?.map((d) => (
                <button
                  key={d.id}
                  onClick={() => setSelected(d.id)}
                  className={cn(
                    "grid w-full cursor-pointer grid-cols-[100px_1fr_auto] items-start gap-4 border-b-2 border-ink px-4 py-3 text-left last:border-0",
                    current?.id === d.id ? "bg-acid" : "hover:bg-paper",
                  )}
                >
                  <span className="label pt-0.5 text-[10px]">{formatDate(d.decided_on)}</span>
                  <span className={cn("font-bold leading-snug", d.status === "superseded" && "text-muted line-through")}>{d.title}</span>
                  <DecisionStatusBadge status={d.status} />
                </button>
              ))}
            </Card>

            {current && (
              <Card className="self-start xl:sticky xl:top-6">
                <div className="border-b-2 border-ink bg-ink p-5 text-paper">
                  <DecisionStatusBadge status={current.status} />
                  <p className="display mt-3 text-2xl leading-tight">{current.title}</p>
                </div>
                <dl className="divide-y-2 divide-ink text-sm">
                  <Row k="Why">{current.rationale || <span className="text-muted">Not recorded</span>}</Row>
                  <Row k="Approved by">{current.approved_by || <span className="text-muted">Unknown</span>}</Row>
                  <Row k="Decided">{formatDate(current.decided_on)}</Row>
                  <Row k="Project">{projectName(current.project_id) ?? "—"}</Row>
                  <Row k="Source">
                    {current.meeting_id ? (
                      <Link href={`/w/${ws}/meetings/${current.meeting_id}`} className="underline">{current.meeting_title}</Link>
                    ) : "Recorded manually"}
                  </Row>
                  <Row k="Last confirmed">{current.last_confirmed_at ? relativeTime(current.last_confirmed_at) : "Never"}</Row>
                  {supersededBy && (
                    <Row k="Replaced by">
                      <button className="cursor-pointer text-left underline" onClick={() => setSelected(supersededBy.id)}>{supersededBy.title}</button>
                    </Row>
                  )}
                  {supersedes.length > 0 && (
                    <Row k="Replaces">
                      {supersedes.map((s) => (
                        <button key={s.id} className="block cursor-pointer text-left underline" onClick={() => setSelected(s.id)}>{s.title}</button>
                      ))}
                    </Row>
                  )}
                </dl>
                {current.source_quote && (
                  <blockquote className="flex gap-2 border-t-2 border-ink bg-paper-2 p-4 font-mono text-xs">
                    <Quote className="size-4 shrink-0" /> {current.source_quote}
                  </blockquote>
                )}
                {editable && (
                  <div className="space-y-3 border-t-2 border-ink p-4">
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={() => patch(current.id, { confirm: true })}>
                        <BadgeCheck /> Still valid
                      </Button>
                      <Select
                        aria-label="Status"
                        className="h-8 text-xs"
                        value={current.status}
                        onChange={(e) => patch(current.id, { status: e.target.value })}
                      >
                        {STATUSES.map((s) => <option key={s} value={s}>Mark {s}</option>)}
                      </Select>
                    </div>
                    <Select
                      aria-label="Superseded by"
                      className="h-8 text-xs"
                      value=""
                      onChange={(e) => e.target.value && patch(current.id, { superseded_by_id: e.target.value })}
                    >
                      <option value="">Superseded by…</option>
                      {(all ?? []).filter((d) => d.id !== current.id && d.status === "active").map((d) => (
                        <option key={d.id} value={d.id}>{d.title.slice(0, 80)}</option>
                      ))}
                    </Select>
                  </div>
                )}
              </Card>
            )}
          </div>
        )}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent title="Record a decision">
          <div className="space-y-4">
            <Field label="Decision"><Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Use Postgres for analytics" /></Field>
            <Field label="Why"><Textarea value={form.rationale} onChange={(e) => setForm({ ...form, rationale: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Approved by"><Input value={form.approved_by} onChange={(e) => setForm({ ...form, approved_by: e.target.value })} /></Field>
              <Field label="Date"><Input type="date" value={form.decided_on} onChange={(e) => setForm({ ...form, decided_on: e.target.value })} /></Field>
            </div>
            <Field label="Project">
              <Select value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })}>
                <option value="">No project</option>
                {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </Select>
            </Field>
            <Button variant="accent" className="w-full" disabled={form.title.trim().length < 2} onClick={create}>Save decision</Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[110px_1fr] gap-3 px-4 py-2.5">
      <dt className="label pt-0.5 text-[10px] text-muted">{k}</dt>
      <dd>{children}</dd>
    </div>
  );
}
