"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus } from "lucide-react";

import { PageHeader, StatusPill } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { Empty } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { DropZone } from "@/components/upload";
import { api, qs, useApi } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Meeting } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

const today = () => new Date().toISOString().slice(0, 10);

export default function MeetingsPage() {
  const router = useRouter();
  const { ws, projectId, projects, projectName, can } = useWorkspace();
  const { data: meetings } = useApi<Meeting[]>(`/api/workspaces/${ws}/meetings${qs({ project_id: projectId })}`, {
    refreshInterval: (d) => (d?.some((m) => m.status === "pending" || m.status === "processing") ? 1500 : 0),
  });
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"file" | "text">("file");
  const [files, setFiles] = useState<File[]>([]);
  const [title, setTitle] = useState("");
  const [heldOn, setHeldOn] = useState(today());
  const [project, setProject] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("title", title);
      form.append("held_on", heldOn);
      if (project) form.append("project_id", project);
      if (mode === "file" && files[0]) form.append("file", files[0]);
      else form.append("text", text);
      const m = await api<Meeting>(`/api/workspaces/${ws}/meetings`, { body: form });
      setOpen(false);
      router.push(`/w/${ws}/meetings/${m.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
      setBusy(false);
    }
  }

  const ready = title.trim() && (mode === "file" ? files.length > 0 : text.trim().length > 0);

  return (
    <>
      <PageHeader
        index="03"
        title="Meetings"
        subtitle="Upload a transcript or paste your notes. WorkflowWise extracts decisions, action items with owners and deadlines, and open questions."
        actions={
          can("member") && (
            <Button
              variant="accent"
              onClick={() => {
                setProject(projectId ?? "");
                setFiles([]);
                setError(null);
                setBusy(false);
                setOpen(true);
              }}
            >
              <Plus /> Add meeting
            </Button>
          )
        }
      />
      <div className="p-10">
        {meetings?.length === 0 && <Empty title="No meetings yet">Add your last team meeting to see decisions and action items appear.</Empty>}
        <div className="space-y-4">
          {meetings?.map((m) => (
            <Link
              key={m.id}
              href={`/w/${ws}/meetings/${m.id}`}
              className="grid grid-cols-[120px_1fr_auto] items-start gap-6 border-2 border-ink bg-white p-5 shadow-[var(--shadow-hard-sm)] transition-transform hover:-translate-x-px hover:-translate-y-px hover:shadow-[var(--shadow-hard)]"
            >
              <div className="border-r-2 border-ink pr-4">
                <p className="display text-3xl">{formatDate(m.held_on, { day: "2-digit", month: undefined, year: undefined })}</p>
                <p className="label text-[10px]">{formatDate(m.held_on, { day: undefined })}</p>
              </div>
              <div className="min-w-0">
                <p className="text-lg font-bold">{m.title}</p>
                {m.summary && <p className="mt-1 line-clamp-2 text-sm text-muted">{m.summary}</p>}
                <div className="label mt-2 flex gap-4 text-[10px] text-muted">
                  {m.attendees.length > 0 && <span>{m.attendees.slice(0, 5).join(", ")}{m.attendees.length > 5 ? "…" : ""}</span>}
                  {projectName(m.project_id) && <span>{projectName(m.project_id)}</span>}
                </div>
              </div>
              <StatusPill status={m.status} />
            </Link>
          ))}
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent title="Add meeting">
          <div className="space-y-4">
            <div className="grid grid-cols-[1fr_160px] gap-4">
              <Field label="Title"><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Weekly product sync" /></Field>
              <Field label="Date"><Input type="date" value={heldOn} onChange={(e) => setHeldOn(e.target.value)} /></Field>
            </div>
            <Field label="Project">
              <Select value={project} onChange={(e) => setProject(e.target.value)}>
                <option value="">No project</option>
                {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </Select>
            </Field>
            <div className="flex border-2 border-ink">
              {(["file", "text"] as const).map((k) => (
                <button
                  key={k}
                  onClick={() => setMode(k)}
                  className={cn("label flex-1 cursor-pointer py-2 font-bold", mode === k ? "bg-ink text-paper" : "bg-white hover:bg-paper-2", k === "text" && "border-l-2 border-ink")}
                >
                  {k === "file" ? "Upload transcript" : "Paste notes"}
                </button>
              ))}
            </div>
            {mode === "file" ? (
              <DropZone files={files} onFiles={setFiles} multiple={false} />
            ) : (
              <Textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                className="min-h-56 font-mono text-xs"
                placeholder={"Attendees: Ana, Ben\n\nDecisions:\n- Launch on March 3\n\nAction items:\n- Ben to update the plan by Friday\n\nOpen questions:\n- Who owns migration?"}
              />
            )}
            {error && <p className="border-2 border-ink bg-signal p-2 font-mono text-xs">{error}</p>}
            <Button variant="accent" className="w-full" disabled={!ready || busy} onClick={submit}>
              {busy ? "Uploading…" : "Extract decisions & actions"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
