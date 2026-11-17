"use client";

import { createContext, useContext } from "react";

import { useApi } from "./api";
import { useLocal } from "./local-store";
import type { Me, Member, Project, Role, Workspace } from "./types";

const RANK: Record<Role, number> = { viewer: 0, member: 1, admin: 2, owner: 3 };

interface WorkspaceState {
  ws: string;
  workspace: Workspace | undefined;
  me: Me | undefined;
  role: Role;
  can: (minimum: Role) => boolean;
  projects: Project[];
  members: Member[];
  projectId: string | null;
  setProjectId: (id: string | null) => void;
  projectName: (id: string | null) => string | null;
  refreshProjects: () => void;
  refreshMembers: () => void;
}

const Ctx = createContext<WorkspaceState | null>(null);

export function WorkspaceProvider({ ws, children }: { ws: string; children: React.ReactNode }) {
  const { data: workspace } = useApi<Workspace>(`/api/workspaces/${ws}`);
  const { data: me } = useApi<Me>("/api/me");
  const { data: projects, mutate: mp } = useApi<Project[]>(`/api/workspaces/${ws}/projects`);
  const { data: members, mutate: mm } = useApi<Member[]>(`/api/workspaces/${ws}/members`);
  const storageKey = `wfw.project.${ws}`;
  const [projectId, setProjectId] = useLocal(storageKey);

  const role: Role = workspace?.role ?? "viewer";
  const value: WorkspaceState = {
    ws,
    workspace,
    me,
    role,
    can: (minimum) => RANK[role] >= RANK[minimum],
    projects: projects ?? [],
    members: members ?? [],
    projectId: projects?.some((p) => p.id === projectId) ? projectId : null,
    setProjectId,
    projectName: (id) => (id ? projects?.find((p) => p.id === id)?.name ?? null : null),
    refreshProjects: () => void mp(),
    refreshMembers: () => void mm(),
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWorkspace() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useWorkspace must be used inside <WorkspaceProvider>");
  return v;
}
