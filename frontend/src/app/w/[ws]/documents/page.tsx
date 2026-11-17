"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ClipboardPaste, Upload } from "lucide-react";

import { PageHeader, StatusPill } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { Badge, Card, Empty } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { DropZone } from "@/components/upload";
import { api, qs, useApi } from "@/lib/api";
import { bytes, relativeTime } from "@/lib/format";
import type { DocumentT } from "@/lib/types";
import { useWorkspace } from "@/lib/workspace";

function ProjectSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const { projects } = useWorkspace();
  return (
    <Select value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">No project</option>
      {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
    </Select>
  );
}

export default function DocumentsPage() {
  const { ws, projectId, projectName, can } = useWorkspace();
  const [filter, setFilter] = useState("");
  const [kind, setKind] = useState("");
  const { data: docs, mutate } = useApi<DocumentT[]>(`/api/workspaces/${ws}/documents${qs({ project_id: projectId, kind })}`, {
    refreshInterval: (d) => (d?.some((x) => x.status === "pending" || x.status === "processing") ? 1500 : 0),
  });

  const [uploadOpen, setUploadOpen] = useState(false);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [docKind, setDocKind] = useState("document");
  const [project, setProject] = useState(projectId ?? "");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const visible = useMemo(() => {
    const f = filter.toLowerCase();
    return (docs ?? []).filter((d) => !f || d.title.toLowerCase().includes(f) || d.summary?.toLowerCase().includes(f));
  }, [docs, filter]);

  async function upload() {
    setBusy(true);
    setError(null);
    try {
      for (const f of files) {
        const form = new FormData();
        form.append("file", f);
        form.append("kind", docKind);
        if (project) form.append("project_id", project);
        await api(`/api/workspaces/${ws}/documents`, { body: form });
      }
      setFiles([]);
      setUploadOpen(false);
      mutate();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function paste() {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/workspaces/${ws}/documents/text`, { body: { title, content: text, kind: docKind, project_id: project || null } });
      setTitle("");
      setText("");
      setPasteOpen(false);
      mutate();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  const open = (which: "upload" | "paste") => {
    setProject(projectId ?? "");
    setError(null);
    (which === "upload" ? setUploadOpen : setPasteOpen)(true);
  };

  return (
    <>
      <PageHeader
        index="02"
        title="Documents"
        subtitle="Specs, policies, PDFs and project records. Everything here is searchable and citable. Re-uploading a file with the same name creates a new version."
        actions={
          can("member") && (
            <>
              <Button variant="outline" onClick={() => open("paste")}><ClipboardPaste /> Paste text</Button>
              <Button variant="accent" onClick={() => open("upload")}><Upload /> Upload</Button>
            </>
          )
        }
      />

      <div className="p-10">
        <div className="mb-6 flex gap-3">
          <Input placeholder="Filter by title or summary…" value={filter} onChange={(e) => setFilter(e.target.value)} className="max-w-md" />
          <Select value={kind} onChange={(e) => setKind(e.target.value)} className="w-48">
            <option value="">Documents &amp; records</option>
            <option value="document">Documents</option>
            <option value="record">Project records</option>
            <option value="meeting">Meeting transcripts</option>
          </Select>
        </div>

        {docs && visible.length === 0 ? (
          <Empty title="No documents">Upload a PDF, Word file or notes to start building your team&apos;s memory.</Empty>
        ) : (
          <Card>
            <table className="w-full text-sm">
              <thead>
                <tr className="label border-b-2 border-ink bg-paper-2 text-left text-[10px]">
                  <th className="px-4 py-2">Title</th>
                  <th className="px-4 py-2">Project</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Size</th>
                  <th className="px-4 py-2 text-right">Added</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((d) => (
                  <tr key={d.id} className="border-b-2 border-ink align-top last:border-0 hover:bg-paper">
                    <td className="max-w-xl px-4 py-3">
                      <Link href={`/w/${ws}/documents/${d.id}`} className="font-bold hover:underline">{d.title}</Link>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        {d.kind !== "document" && <Badge tone="cobalt">{d.kind}</Badge>}
                        {d.version > 1 && <Badge tone="acid">v{d.version}</Badge>}
                        {d.superseded_by_id && <Badge tone="muted">Superseded</Badge>}
                      </div>
                      {d.summary && <p className="mt-1.5 line-clamp-2 text-xs text-muted">{d.summary}</p>}
                      {d.error && <p className="mt-1.5 font-mono text-xs text-signal">{d.error}</p>}
                    </td>
                    <td className="label px-4 py-3 text-[10px]">{projectName(d.project_id) ?? "—"}</td>
                    <td className="px-4 py-3"><StatusPill status={d.status} /></td>
                    <td className="px-4 py-3 font-mono text-xs">{bytes(d.size_bytes)}</td>
                    <td className="label px-4 py-3 text-right text-[10px] text-muted">{relativeTime(d.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
        <DialogContent title="Upload documents">
          <div className="space-y-4">
            <DropZone files={files} onFiles={setFiles} />
            <div className="grid grid-cols-2 gap-4">
              <Field label="Project"><ProjectSelect value={project} onChange={setProject} /></Field>
              <Field label="Type">
                <Select value={docKind} onChange={(e) => setDocKind(e.target.value)}>
                  <option value="document">Document</option>
                  <option value="record">Project record</option>
                </Select>
              </Field>
            </div>
            {error && <p className="border-2 border-ink bg-signal p-2 font-mono text-xs">{error}</p>}
            <Button variant="accent" className="w-full" disabled={!files.length || busy} onClick={upload}>
              {busy ? "Uploading…" : `Upload ${files.length || ""} file${files.length === 1 ? "" : "s"}`}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={pasteOpen} onOpenChange={setPasteOpen}>
        <DialogContent title="Paste text" description="Useful for Slack threads, emails or wiki pages you want the team to be able to find.">
          <div className="space-y-4">
            <Field label="Title"><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Slack: #eng decision on queues" /></Field>
            <Field label="Content"><Textarea value={text} onChange={(e) => setText(e.target.value)} className="min-h-56" /></Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Project"><ProjectSelect value={project} onChange={setProject} /></Field>
              <Field label="Type">
                <Select value={docKind} onChange={(e) => setDocKind(e.target.value)}>
                  <option value="document">Document</option>
                  <option value="record">Project record</option>
                </Select>
              </Field>
            </div>
            {error && <p className="border-2 border-ink bg-signal p-2 font-mono text-xs">{error}</p>}
            <Button variant="accent" className="w-full" disabled={!title.trim() || !text.trim() || busy} onClick={paste}>
              Save to workspace
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
