"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BadgeCheck, ExternalLink, RefreshCw, Trash2 } from "lucide-react";

import { PageHeader, StatusPill } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/form";
import { api, openFile, useApi } from "@/lib/api";
import { bytes, formatDate, relativeTime } from "@/lib/format";
import type { DocumentDetail } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

export default function DocumentPage() {
  const { doc } = useParams<{ doc: string }>();
  const router = useRouter();
  const { ws, projects, can } = useWorkspace();
  const path = `/api/workspaces/${ws}/documents/${doc}`;
  const { data: d, mutate, error } = useApi<DocumentDetail>(path, {
    refreshInterval: (x) => (x && (x.status === "pending" || x.status === "processing") ? 1500 : 0),
  });
  const [target, setTarget] = useState<string | null>(null);

  useEffect(() => {
    const read = () => setTarget(window.location.hash.replace("#chunk-", "") || null);
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);

  useEffect(() => {
    if (target && d) document.getElementById(`chunk-${target}`)?.scrollIntoView({ block: "center" });
  }, [target, d]);

  if (error) return <p className="m-10 border-2 border-ink bg-signal p-4 font-mono">{error.message}</p>;
  if (!d) return <p className="label m-10">Loading…</p>;

  const member = can("member");
  return (
    <>
      <PageHeader
        index="02"
        title={d.title}
        subtitle={d.summary ?? undefined}
        actions={
          <>
            <Button variant="outline" onClick={() => openFile(`${path}/file`)}><ExternalLink /> Original</Button>
            {member && (
              <>
                <Button variant="outline" onClick={() => api(`${path}`, { method: "PATCH", body: { verified: true } }).then(() => mutate())}>
                  <BadgeCheck /> Still accurate
                </Button>
                <Button variant="outline" size="icon" title="Reprocess" onClick={() => api(`${path}/reprocess`, { method: "POST" }).then(() => mutate())}>
                  <RefreshCw />
                </Button>
                <Button
                  variant="danger"
                  size="icon"
                  title="Delete"
                  onClick={async () => {
                    if (!confirm("Delete this document and everything extracted from it?")) return;
                    await api(path, { method: "DELETE" });
                    router.push(`/w/${ws}/documents`);
                  }}
                >
                  <Trash2 />
                </Button>
              </>
            )}
          </>
        }
      />
      <div className="grid gap-8 p-10 xl:grid-cols-[minmax(0,1fr)_300px]">
        <Card>
          <CardHeader index="TXT" title={`Extracted text · ${d.chunks.length} passages`} />
          {d.status !== "ready" && (
            <div className="border-b-2 border-ink p-4">
              <StatusPill status={d.status} />
              {d.error && <p className="mt-2 font-mono text-xs text-signal">{d.error}</p>}
            </div>
          )}
          <div>
            {d.chunks.map((c) => (
              <div
                key={c.id}
                id={`chunk-${c.id}`}
                className={cn("scroll-mt-24 border-b border-ink/15 px-6 py-4 last:border-0", target === c.id && "chunk-highlight")}
              >
                <p className="label mb-2 text-[10px] text-muted">
                  §{c.ordinal + 1}{c.page ? ` · page ${c.page}` : ""}
                </p>
                <p className="whitespace-pre-wrap text-[15px] leading-relaxed">{c.content}</p>
              </div>
            ))}
          </div>
        </Card>

        <aside className="space-y-6">
          <Card>
            <CardHeader title="Details" />
            <dl className="divide-y-2 divide-ink text-sm">
              {[
                ["Status", <StatusPill key="s" status={d.status} />],
                ["Type", d.kind],
                ["Version", <span key="v">v{d.version} {d.superseded_by_id && <Badge tone="muted">Superseded</Badge>}</span>],
                ["File", d.filename],
                ["Size", bytes(d.size_bytes)],
                ["Uploaded", `${formatDate(d.created_at)} · ${d.uploader?.name ?? d.uploader?.email ?? "—"}`],
                ["Verified", d.last_verified_at ? relativeTime(d.last_verified_at) : "Never"],
              ].map(([k, v]) => (
                <div key={String(k)} className="grid grid-cols-[90px_1fr] gap-2 px-4 py-2.5">
                  <dt className="label text-[10px] text-muted">{k}</dt>
                  <dd className="break-words">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>
          {d.superseded_by_id && (
            <Link
              href={`/w/${ws}/documents/${d.superseded_by_id}`}
              className="block border-2 border-ink bg-acid p-4 font-bold shadow-[var(--shadow-hard)]"
            >
              A newer version exists → open latest
            </Link>
          )}
          {member && (
            <Card>
              <CardHeader title="Project" />
              <div className="p-4">
                <Select
                  value={d.project_id ?? ""}
                  onChange={(e) => api(path, { method: "PATCH", body: { project_id: e.target.value || null } }).then(() => mutate())}
                >
                  <option value="">No project</option>
                  {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </Select>
              </div>
            </Card>
          )}
        </aside>
      </div>
    </>
  );
}
