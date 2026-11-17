"use client";

import { useParams } from "next/navigation";

import { Shell } from "@/components/shell";
import { WorkspaceProvider } from "@/lib/workspace";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const { ws } = useParams<{ ws: string }>();
  return (
    <WorkspaceProvider ws={ws}>
      <Shell>{children}</Shell>
    </WorkspaceProvider>
  );
}
