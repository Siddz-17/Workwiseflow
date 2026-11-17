"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { ActionRow, DecisionRow, Stat } from "@/components/records";
import { PageHeader, StatusPill } from "@/components/shell";
import { Card, CardHeader, Empty } from "@/components/ui/card";
import { qs, useApi } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { Overview } from "@/lib/types";
import { useWorkspace } from "@/lib/workspace";

export default function OverviewPage() {
  const { ws, workspace, projectId } = useWorkspace();
  const { data, mutate } = useApi<Overview>(`/api/workspaces/${ws}/overview${qs({ project_id: projectId })}`);
  const base = `/w/${ws}`;

  return (
    <>
      <PageHeader
        index="00"
        title={workspace?.name ?? "Overview"}
        subtitle="What your team knows, what it decided, and what needs to happen next."
      />
      <div className="space-y-8 p-10">
        <section className="grid grid-cols-2 gap-5 md:grid-cols-4 xl:grid-cols-8">
          <Stat label="Documents" value={data?.documents ?? "–"} href={`${base}/documents`} />
          <Stat label="Meetings" value={data?.meetings ?? "–"} href={`${base}/meetings`} />
          <Stat label="Active decisions" value={data?.decisions_active ?? "–"} href={`${base}/decisions`} />
          <Stat label="Open actions" value={data?.actions_open ?? "–"} href={`${base}/actions`} />
          <Stat label="Overdue" value={data?.actions_overdue ?? "–"} tone="signal" href={`${base}/actions?view=overdue`} />
          <Stat label="No owner" value={data?.actions_unassigned ?? "–"} tone="signal" href={`${base}/actions?view=unassigned`} />
          <Stat label="Open questions" value={data?.open_questions ?? "–"} href={`${base}/gaps`} />
          <Stat label="Conflicts" value={data?.conflicts ?? "–"} tone="signal" href={`${base}/gaps`} />
        </section>

        <Link
          href={`${base}/ask`}
          className="flex items-center justify-between border-2 border-ink bg-ink px-6 py-5 text-paper shadow-[var(--shadow-hard)] hover:bg-ink/90"
        >
          <span className="display text-2xl">Ask your workspace anything<span className="cursor-blink text-acid">_</span></span>
          <ArrowRight className="size-6 text-acid" />
        </Link>

        <div className="grid gap-8 xl:grid-cols-2">
          <Card>
            <CardHeader index="A" title="Next up — open actions" action={<Link className="label underline" href={`${base}/actions`}>All</Link>} />
            {data?.upcoming_actions.length ? (
              data.upcoming_actions.map((a) => <ActionRow key={a.id} a={a} onChange={() => mutate()} editable={false} />)
            ) : (
              <div className="p-4"><Empty title="Nothing open">Upload a meeting to extract action items.</Empty></div>
            )}
          </Card>
          <Card>
            <CardHeader index="D" title="Recent decisions" action={<Link className="label underline" href={`${base}/decisions`}>All</Link>} />
            {data?.recent_decisions.length ? (
              data.recent_decisions.map((d) => <DecisionRow key={d.id} d={d} compact />)
            ) : (
              <div className="p-4"><Empty title="No decisions yet">Decisions extracted from meetings show up here.</Empty></div>
            )}
          </Card>
        </div>

        <Card>
          <CardHeader index="F" title="Recently added documents" action={<Link className="label underline" href={`${base}/documents`}>All</Link>} />
          {data?.recent_documents.length ? (
            <table className="w-full text-sm">
              <tbody>
                {data.recent_documents.map((d) => (
                  <tr key={d.id} className="border-b-2 border-ink last:border-0">
                    <td className="px-4 py-3 font-bold">
                      <Link href={`${base}/documents/${d.id}`} className="hover:underline">{d.title}</Link>
                    </td>
                    <td className="px-4 py-3"><StatusPill status={d.status} /></td>
                    <td className="label px-4 py-3 text-right text-[10px] text-muted">{relativeTime(d.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-4"><Empty title="Empty memory">Upload PDFs, DOCX or text to get started.</Empty></div>
          )}
        </Card>
      </div>
    </>
  );
}
