"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/form";
import { api, useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Me, Workspace } from "@/lib/types";

export default function WorkspacePicker() {
  const auth = useAuth();
  const router = useRouter();
  const { data, error, mutate } = useApi<Me>(auth.email ? "/api/me" : null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (auth.ready && !auth.email) router.replace("/login");
  }, [auth.ready, auth.email, router]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const ws = await api<Workspace>("/api/workspaces", { body: { name } });
      await mutate();
      router.push(`/w/${ws.id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
      setBusy(false);
    }
  }

  return (
    <div className="grid-bg min-h-screen">
      <header className="flex items-center justify-between border-b-2 border-ink bg-paper px-8 py-4">
        <Link href="/" className="display text-xl">WorkflowWise</Link>
        <div className="flex items-center gap-4">
          <span className="label text-muted">{auth.email}</span>
          <Button variant="outline" size="sm" onClick={() => auth.signOut().then(() => router.replace("/login"))}>
            <LogOut /> Sign out
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-8 py-16">
        <h1 className="display text-6xl">Workspaces</h1>
        <p className="mt-3 text-muted">Each workspace is a separate memory with its own members, projects and documents.</p>

        {error && (
          <p className="mt-8 border-2 border-ink bg-signal p-3 font-mono text-sm">
            Can&apos;t reach the API: {error.message}. Is the backend running?
          </p>
        )}

        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {data?.workspaces.map((w) => (
            <Link key={w.id} href={`/w/${w.id}`} className="group">
              <Card className="transition-transform group-hover:-translate-x-1 group-hover:-translate-y-1 group-hover:shadow-[var(--shadow-hard-lg)]">
                <div className="flex items-start justify-between p-6">
                  <div>
                    <p className="display text-3xl">{w.name}</p>
                    <Badge tone="ink" className="mt-3">{w.role}</Badge>
                  </div>
                  <ArrowRight className="size-6 transition-transform group-hover:translate-x-1" />
                </div>
              </Card>
            </Link>
          ))}

          <Card>
            <CardHeader index="+" title="New workspace" />
            <form onSubmit={create} className="space-y-3 p-5">
              <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme Inc." />
              {err && <p className="font-mono text-xs text-signal">{err}</p>}
              <Button type="submit" variant="accent" className="w-full" disabled={busy || !name.trim()}>
                Create workspace
              </Button>
            </form>
          </Card>
        </div>
        {data && data.workspaces.length === 0 && (
          <p className="label mt-8 text-muted">Invited by a teammate? Their workspace appears here once they add your email.</p>
        )}
      </main>
    </div>
  );
}
