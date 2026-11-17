"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import {
  CheckSquare,
  FileText,
  Gavel,
  LayoutGrid,
  LogOut,
  MessageSquareText,
  Mic,
  Radar,
  Users,
} from "lucide-react";

import { Select } from "@/components/ui/form";
import { useAuth } from "@/lib/auth";
import { initials } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

const NAV = [
  { href: "", label: "Overview", icon: LayoutGrid },
  { href: "/ask", label: "Ask", icon: MessageSquareText },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/meetings", label: "Meetings", icon: Mic },
  { href: "/decisions", label: "Decisions", icon: Gavel },
  { href: "/actions", label: "Actions", icon: CheckSquare },
  { href: "/gaps", label: "Gaps", icon: Radar },
  { href: "/team", label: "Team", icon: Users },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const { ws, workspace, me, role, projects, projectId, setProjectId } = useWorkspace();
  const base = `/w/${ws}`;

  useEffect(() => {
    if (auth.ready && !auth.email) router.replace("/login");
  }, [auth.ready, auth.email, router]);

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-r-2 border-ink bg-paper">
        <Link href="/app" className="block border-b-2 border-ink bg-ink px-5 py-4 text-paper hover:bg-ink/90">
          <span className="display block text-lg leading-none">WorkflowWise</span>
          <span className="label mt-2 block truncate text-acid">{workspace?.name ?? "…"}</span>
        </Link>

        <div className="border-b-2 border-ink p-4">
          <label className="label mb-1.5 block text-muted" htmlFor="project-scope">Project scope</label>
          <Select id="project-scope" value={projectId ?? ""} onChange={(e) => setProjectId(e.target.value || null)} className="h-9 text-xs">
            <option value="">All projects</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </Select>
        </div>

        <nav className="flex-1 overflow-y-auto py-2">
          {NAV.map((item, i) => {
            const href = base + item.href;
            const active = item.href === "" ? pathname === base : pathname.startsWith(href);
            return (
              <Link
                key={item.label}
                href={href}
                className={cn(
                  "group flex items-center gap-3 border-y-2 border-transparent px-5 py-2.5 font-mono text-[13px] font-bold uppercase tracking-wider",
                  active ? "border-ink bg-acid" : "hover:border-ink hover:bg-paper-2",
                )}
              >
                <span className="w-5 text-[10px] text-muted">{String(i).padStart(2, "0")}</span>
                <item.icon className="size-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3 border-t-2 border-ink p-4">
          <span className="flex size-9 shrink-0 items-center justify-center border-2 border-ink bg-cobalt font-mono text-xs font-bold text-white">
            {initials(me?.user.name || me?.user.email || "?")}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-bold">{me?.user.name ?? me?.user.email}</p>
            <p className="label text-[10px] text-muted">{role}</p>
          </div>
          <button
            title="Sign out"
            onClick={() => auth.signOut().then(() => router.replace("/login"))}
            className="cursor-pointer border-2 border-transparent p-1.5 hover:border-ink hover:bg-signal"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </aside>
      <main className="grid-bg min-w-0 flex-1">{children}</main>
    </div>
  );
}

export function PageHeader({
  index,
  title,
  subtitle,
  actions,
}: {
  index: string;
  title: string;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  const { projectId, projectName } = useWorkspace();
  return (
    <header className="flex flex-wrap items-end justify-between gap-6 border-b-2 border-ink bg-paper px-10 pb-6 pt-10">
      <div>
        <div className="mb-3 flex items-center gap-2">
          <span className="label bg-ink px-1.5 py-0.5 text-paper">{index}</span>
          <span className="label text-muted">{projectId ? `Project / ${projectName(projectId)}` : "All projects"}</span>
        </div>
        <h1 className="display text-5xl xl:text-6xl">{title}</h1>
        {subtitle && <p className="mt-3 max-w-2xl text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </header>
  );
}

export function StatusPill({ status }: { status: string }) {
  const tone: Record<string, string> = {
    ready: "bg-ok text-white",
    processing: "bg-cobalt text-white",
    pending: "bg-paper-2",
    failed: "bg-signal",
  };
  return (
    <span className={cn("label inline-flex items-center gap-1.5 border-2 border-ink px-1.5 py-px text-[10px] font-bold", tone[status] ?? "bg-white")}>
      {status === "processing" || status === "pending" ? <span className="cursor-blink">■</span> : null}
      {status}
    </span>
  );
}
