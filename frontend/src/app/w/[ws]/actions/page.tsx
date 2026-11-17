"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Plus } from "lucide-react";

import { ActionRow } from "@/components/records";
import { PageHeader } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { Card, Empty } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/form";
import { api, qs, useApi } from "@/lib/api";
import type { ActionItem } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

const VIEWS = [
  { id: "incomplete", label: "Incomplete", params: { status: "incomplete" } },
  { id: "overdue", label: "Overdue", params: { overdue: true } },
  { id: "unassigned", label: "No owner", params: { unassigned: true, status: "incomplete" } },
  { id: "mine", label: "Mine", params: { mine: true, status: "incomplete" } },
  { id: "done", label: "Done", params: { status: "done" } },
  { id: "all", label: "All", params: {} },
] as const;

function Actions() {
  const search = useSearchParams();
  const initial = VIEWS.find((v) => v.id === search.get("view"))?.id ?? "incomplete";
  const [view, setView] = useState<string>(initial);
  const { ws, projectId, members, can } = useWorkspace();
  const active = VIEWS.find((v) => v.id === view) ?? VIEWS[0];
  const { data, mutate } = useApi<ActionItem[]>(`/api/workspaces/${ws}/actions${qs({ ...active.params, project_id: projectId })}`, {
    keepPreviousData: true,
  });
  const [title, setTitle] = useState("");
  const [owner, setOwner] = useState("");
  const [due, setDue] = useState("");

  async function add(e: React.FormEvent) {
    e.preventDefault();
    await api(`/api/workspaces/${ws}/actions`, {
      body: { title, owner_user_id: owner || null, due_on: due || null, project_id: projectId },
    });
    setTitle("");
    setDue("");
    setOwner("");
    mutate();
  }

  return (
    <>
      <PageHeader
        index="05"
        title="Action items"
        subtitle="Every commitment from every meeting. Overdue and ownerless tasks are flagged so nothing silently drops."
      />
      <div className="p-10">
        <div className="mb-6 flex flex-wrap border-2 border-ink bg-white shadow-[var(--shadow-hard-sm)]">
          {VIEWS.map((v, i) => (
            <button
              key={v.id}
              onClick={() => setView(v.id)}
              className={cn(
                "label cursor-pointer px-5 py-3 font-bold",
                i > 0 && "border-l-2 border-ink",
                view === v.id ? (v.id === "overdue" || v.id === "unassigned" ? "bg-signal" : "bg-ink text-paper") : "hover:bg-paper-2",
              )}
            >
              {v.label}
            </button>
          ))}
          <span className="label ml-auto self-center px-5 text-muted">{data?.length ?? 0} items</span>
        </div>

        {can("member") && (
          <form onSubmit={add} className="mb-6 grid grid-cols-[1fr_200px_160px_auto] gap-3">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Add an action item…" />
            <Select value={owner} onChange={(e) => setOwner(e.target.value)}>
              <option value="">Unassigned</option>
              {members.map((m) => <option key={m.user.id} value={m.user.id}>{m.user.name || m.user.email}</option>)}
            </Select>
            <Input type="date" value={due} onChange={(e) => setDue(e.target.value)} className="font-mono text-xs" />
            <Button type="submit" variant="accent" disabled={title.trim().length < 2}><Plus /> Add</Button>
          </form>
        )}

        {data && data.length === 0 ? (
          <Empty title={view === "overdue" ? "Nothing overdue" : view === "unassigned" ? "Everything has an owner" : "No action items"}>
            {view === "incomplete" ? "Upload a meeting to extract action items automatically." : null}
          </Empty>
        ) : (
          <Card>{data?.map((a) => <ActionRow key={a.id} a={a} onChange={() => mutate()} />)}</Card>
        )}
      </div>
    </>
  );
}

export default function ActionsPage() {
  return (
    <Suspense fallback={<p className="label m-10">Loading…</p>}>
      <Actions />
    </Suspense>
  );
}
