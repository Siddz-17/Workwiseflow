"use client";

import Link from "next/link";
import { useState } from "react";
import { Check, Quote, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/form";
import { api } from "@/lib/api";
import { dueLabel, formatDate } from "@/lib/format";
import type { ActionItem, ActionStatus, Decision, DecisionStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

const DECISION_TONE: Record<DecisionStatus, "acid" | "muted" | "signal" | "default"> = {
  active: "acid",
  proposed: "default",
  superseded: "muted",
  revoked: "signal",
};

export function DecisionStatusBadge({ status }: { status: DecisionStatus }) {
  return <Badge tone={DECISION_TONE[status]}>{status}</Badge>;
}

export function DecisionRow({ d, compact = false }: { d: Decision; compact?: boolean }) {
  const { ws, projectName } = useWorkspace();
  return (
    <div className={cn("border-b-2 border-ink px-4 py-3 last:border-b-0", d.status !== "active" && "opacity-70")}>
      <div className="flex items-start justify-between gap-3">
        <p className={cn("font-bold leading-snug", d.status === "superseded" && "line-through decoration-2")}>{d.title}</p>
        <DecisionStatusBadge status={d.status} />
      </div>
      {!compact && d.rationale && <p className="mt-1 text-sm text-muted">Why: {d.rationale}</p>}
      <div className="label mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-muted">
        <span>{formatDate(d.decided_on)}</span>
        {d.approved_by && <span>Approved · {d.approved_by}</span>}
        {d.meeting_title && d.meeting_id && (
          <Link className="underline hover:text-ink" href={`/w/${ws}/meetings/${d.meeting_id}`}>
            ↳ {d.meeting_title}
          </Link>
        )}
        {projectName(d.project_id) && <span>{projectName(d.project_id)}</span>}
      </div>
    </div>
  );
}

const STATUS_NEXT: Record<ActionStatus, ActionStatus> = { open: "in_progress", in_progress: "done", done: "open" };

export function ActionRow({
  a,
  onChange,
  editable = true,
  showMeeting = true,
}: {
  a: ActionItem;
  onChange?: () => void;
  editable?: boolean;
  showMeeting?: boolean;
}) {
  const { ws, members, can } = useWorkspace();
  const canEdit = editable && can("member");
  const [busy, setBusy] = useState(false);
  const [showQuote, setShowQuote] = useState(false);

  async function patch(body: Record<string, unknown>) {
    setBusy(true);
    try {
      await api(`/api/workspaces/${ws}/actions/${a.id}`, { method: "PATCH", body });
      onChange?.();
    } finally {
      setBusy(false);
    }
  }

  const unassigned = !a.owner_user_id && !a.owner_name;
  return (
    <div
      className={cn(
        "grid grid-cols-[auto_1fr_auto] items-start gap-3 border-b-2 border-ink px-4 py-3 last:border-b-0",
        a.overdue && "bg-signal/10",
        busy && "opacity-60",
      )}
    >
      <button
        disabled={!canEdit}
        onClick={() => patch({ status: STATUS_NEXT[a.status] })}
        title={`Status: ${a.status} (click to advance)`}
        className={cn(
          "mt-0.5 flex size-5 cursor-pointer items-center justify-center border-2 border-ink disabled:cursor-default",
          a.status === "done" ? "bg-ink text-paper" : a.status === "in_progress" ? "bg-cobalt" : "bg-white hover:bg-acid",
        )}
      >
        {a.status === "done" && <Check className="size-3" strokeWidth={4} />}
      </button>
      <div className="min-w-0">
        <p className={cn("leading-snug", a.status === "done" && "text-muted line-through")}>{a.title}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {a.overdue && <Badge tone="signal">Overdue</Badge>}
          {unassigned && a.status !== "done" && <Badge tone="ink">No owner</Badge>}
          {a.status === "in_progress" && <Badge tone="cobalt">In progress</Badge>}
          {showMeeting && a.meeting_title && a.meeting_id && (
            <Link href={`/w/${ws}/meetings/${a.meeting_id}`} className="label text-[10px] text-muted underline hover:text-ink">
              ↳ {a.meeting_title}
            </Link>
          )}
          {a.source_quote && (
            <button onClick={() => setShowQuote((s) => !s)} className="label flex cursor-pointer items-center gap-1 text-[10px] text-muted hover:text-ink">
              <Quote className="size-3" /> Source
            </button>
          )}
        </div>
        {showQuote && a.source_quote && (
          <blockquote className="mt-2 border-l-4 border-ink bg-paper-2 px-3 py-1.5 font-mono text-xs">{a.source_quote}</blockquote>
        )}
      </div>
      <div className="flex items-center gap-2">
        {canEdit ? (
          <>
            <Select
              aria-label="Owner"
              className={cn("h-8 w-40 text-xs", unassigned && "bg-paper-2")}
              value={a.owner_user_id ?? (a.owner_name ? `name:${a.owner_name}` : "")}
              onChange={(e) => {
                const v = e.target.value;
                if (!v) patch({ owner_user_id: null, owner_name: null });
                else if (!v.startsWith("name:")) patch({ owner_user_id: v });
              }}
            >
              <option value="">— Unassigned —</option>
              {a.owner_name && !a.owner_user_id && <option value={`name:${a.owner_name}`}>{a.owner_name} (not a member)</option>}
              {members.map((m) => (
                <option key={m.user.id} value={m.user.id}>{m.user.name || m.user.email}</option>
              ))}
            </Select>
            <Input
              aria-label="Due date"
              type="date"
              className="h-8 w-36 font-mono text-xs"
              value={a.due_on ?? ""}
              onChange={(e) => patch({ due_on: e.target.value || null })}
            />
            <button
              title="Delete"
              onClick={() => confirm("Delete this action item?") && api(`/api/workspaces/${ws}/actions/${a.id}`, { method: "DELETE" }).then(onChange)}
              className="cursor-pointer border-2 border-transparent p-1 hover:border-ink hover:bg-signal"
            >
              <Trash2 className="size-4" />
            </button>
          </>
        ) : (
          <span className="label text-[10px] text-muted">{a.owner_name ?? "Unassigned"}</span>
        )}
        <span className={cn("label w-24 text-right text-[10px]", a.overdue ? "font-bold text-signal" : "text-muted")}>
          {a.status === "done" ? "Done" : dueLabel(a.due_on)}
        </span>
      </div>
    </div>
  );
}

export function Stat({ label, value, tone, href }: { label: string; value: number | string; tone?: "signal" | "acid"; href?: string }) {
  const inner = (
    <div className={cn("h-full border-2 border-ink p-4", tone === "signal" && Number(value) > 0 ? "bg-signal" : tone === "acid" ? "bg-acid" : "bg-white")}>
      <p className="label text-[10px]">{label}</p>
      <p className="display mt-3 text-5xl">{value}</p>
    </div>
  );
  return href ? (
    <Link href={href} className="block shadow-[var(--shadow-hard)] transition-transform hover:-translate-x-px hover:-translate-y-px">
      {inner}
    </Link>
  ) : (
    <div className="shadow-[var(--shadow-hard)]">{inner}</div>
  );
}
