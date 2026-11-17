"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Trash2, UserPlus } from "lucide-react";

import { PageHeader } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Input, Select, Textarea } from "@/components/ui/form";
import { api, useApi } from "@/lib/api";
import { formatDate, initials } from "@/lib/format";
import type { Invite, Role } from "@/lib/types";
import { useWorkspace } from "@/lib/workspace";

const ROLES: Role[] = ["viewer", "member", "admin", "owner"];
const ROLE_HELP: Record<Role, string> = {
  viewer: "Read everything and ask questions",
  member: "Upload, edit decisions and actions",
  admin: "Manage members and projects",
  owner: "Everything, including deleting the workspace",
};

export default function TeamPage() {
  const router = useRouter();
  const { ws, workspace, members, projects, me, can, refreshMembers, refreshProjects } = useWorkspace();
  const admin = can("admin");
  const { data: invites, mutate: refreshInvites } = useApi<Invite[]>(admin ? `/api/workspaces/${ws}/invites` : null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("member");
  const [msg, setMsg] = useState<string | null>(null);
  const [pName, setPName] = useState("");
  const [pDesc, setPDesc] = useState("");

  async function run(fn: () => Promise<unknown>, ok?: string) {
    setMsg(null);
    try {
      await fn();
      if (ok) setMsg(ok);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed");
    }
    refreshMembers();
    refreshInvites();
    refreshProjects();
  }

  return (
    <>
      <PageHeader index="07" title="Team" subtitle="Members, roles and projects for this workspace." />
      <div className="grid gap-8 p-10 xl:grid-cols-2">
        <div className="space-y-8">
          <Card>
            <CardHeader index="M" title={`Members · ${members.length}`} />
            {members.map((m) => (
              <div key={m.user.id} className="flex items-center gap-4 border-b-2 border-ink px-4 py-3 last:border-0">
                <span className="flex size-9 shrink-0 items-center justify-center border-2 border-ink bg-paper-2 font-mono text-xs font-bold">
                  {initials(m.user.name || m.user.email)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-bold">{m.user.name || m.user.email} {m.user.id === me?.user.id && <Badge tone="acid">You</Badge>}</p>
                  <p className="label truncate text-[10px] text-muted">{m.user.email} · joined {formatDate(m.joined_at)}</p>
                </div>
                {admin ? (
                  <Select
                    className="h-8 w-32 text-xs"
                    value={m.role}
                    onChange={(e) => run(() => api(`/api/workspaces/${ws}/members/${m.user.id}`, { method: "PATCH", body: { role: e.target.value } }))}
                  >
                    {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </Select>
                ) : (
                  <Badge tone="ink">{m.role}</Badge>
                )}
                {(admin || m.user.id === me?.user.id) && (
                  <button
                    title={m.user.id === me?.user.id ? "Leave workspace" : "Remove"}
                    className="cursor-pointer border-2 border-transparent p-1 hover:border-ink hover:bg-signal"
                    onClick={() =>
                      confirm(m.user.id === me?.user.id ? "Leave this workspace?" : `Remove ${m.user.email}?`) &&
                      run(async () => {
                        await api(`/api/workspaces/${ws}/members/${m.user.id}`, { method: "DELETE" });
                        if (m.user.id === me?.user.id) router.push("/app");
                      })
                    }
                  >
                    <Trash2 className="size-4" />
                  </button>
                )}
              </div>
            ))}
          </Card>

          {admin && (
            <Card>
              <CardHeader index="+" title="Invite by email" />
              <form
                className="space-y-3 p-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  run(async () => {
                    const r = await api<{ status: string }>(`/api/workspaces/${ws}/invites`, { body: { email, role } });
                    setEmail("");
                    setMsg(r.status === "added" ? "Added to workspace." : "Invite saved — they'll join automatically when they sign in with that email.");
                  });
                }}
              >
                <div className="grid grid-cols-[1fr_140px_auto] gap-3">
                  <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="teammate@company.com" />
                  <Select value={role} onChange={(e) => setRole(e.target.value as Role)}>
                    {ROLES.filter((r) => r !== "owner" || can("owner")).map((r) => <option key={r} value={r}>{r}</option>)}
                  </Select>
                  <Button type="submit" variant="accent"><UserPlus /> Invite</Button>
                </div>
                <p className="font-mono text-[11px] text-muted">{ROLE_HELP[role]}</p>
                {msg && <p className="border-2 border-ink bg-acid px-2 py-1 font-mono text-xs">{msg}</p>}
              </form>
              {invites && invites.length > 0 && (
                <div className="border-t-2 border-ink">
                  <p className="label bg-paper-2 px-4 py-2 text-[10px]">Pending invites</p>
                  {invites.map((i) => (
                    <div key={i.id} className="flex items-center justify-between border-t border-ink/20 px-4 py-2 text-sm">
                      <span>{i.email} <Badge>{i.role}</Badge></span>
                      <button className="label cursor-pointer text-[10px] underline" onClick={() => run(() => api(`/api/workspaces/${ws}/invites/${i.id}`, { method: "DELETE" }))}>
                        Revoke
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}
        </div>

        <div className="space-y-8">
          <Card>
            <CardHeader index="P" title={`Projects · ${projects.length}`} />
            {projects.map((p) => (
              <div key={p.id} className="flex items-start justify-between gap-4 border-b-2 border-ink px-4 py-3 last:border-0">
                <div>
                  <p className="font-bold">{p.name}</p>
                  {p.description && <p className="text-sm text-muted">{p.description}</p>}
                </div>
                {admin && (
                  <button
                    title="Delete project"
                    className="cursor-pointer border-2 border-transparent p-1 hover:border-ink hover:bg-signal"
                    onClick={() => confirm(`Delete project “${p.name}”? Its documents stay in the workspace without a project.`) && run(() => api(`/api/workspaces/${ws}/projects/${p.id}`, { method: "DELETE" }))}
                  >
                    <Trash2 className="size-4" />
                  </button>
                )}
              </div>
            ))}
            {admin && (
              <form
                className="space-y-3 border-t-2 border-ink p-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  run(() => api(`/api/workspaces/${ws}/projects`, { body: { name: pName, description: pDesc || null } })).then(() => {
                    setPName("");
                    setPDesc("");
                  });
                }}
              >
                <Input required value={pName} onChange={(e) => setPName(e.target.value)} placeholder="New project name" />
                <Textarea value={pDesc} onChange={(e) => setPDesc(e.target.value)} placeholder="What is this project about? (optional)" className="min-h-16" />
                <Button type="submit" variant="outline">Create project</Button>
              </form>
            )}
          </Card>

          <Card>
            <CardHeader index="R" title="Roles" />
            {ROLES.map((r) => (
              <div key={r} className="grid grid-cols-[90px_1fr] gap-3 border-b-2 border-ink px-4 py-2.5 text-sm last:border-0">
                <Badge tone={r === "owner" ? "ink" : "default"} className="justify-self-start">{r}</Badge>
                <span>{ROLE_HELP[r]}</span>
              </div>
            ))}
          </Card>

          {can("owner") && (
            <Card className="border-signal">
              <CardHeader index="×" title="Danger zone" className="bg-signal" />
              <div className="flex items-center justify-between gap-4 p-4">
                <p className="text-sm">Delete <b>{workspace?.name}</b> and everything in it. This can&apos;t be undone.</p>
                <Button
                  variant="danger"
                  onClick={async () => {
                    if (prompt(`Type the workspace name to confirm: ${workspace?.name}`) !== workspace?.name) return;
                    await api(`/api/workspaces/${ws}`, { method: "DELETE" });
                    router.push("/app");
                  }}
                >
                  Delete workspace
                </Button>
              </div>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
