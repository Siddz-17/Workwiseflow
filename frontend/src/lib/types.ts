export type Role = "viewer" | "member" | "admin" | "owner";

export interface User {
  id: string;
  email: string;
  name: string | null;
}

export interface Workspace {
  id: string;
  name: string;
  created_at: string;
  role: Role | null;
}

export interface Me {
  user: User;
  workspaces: Workspace[];
}

export interface Member {
  user: User;
  role: Role;
  joined_at: string;
}

export interface Invite {
  id: string;
  email: string;
  role: Role;
  created_at: string;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export type DocStatus = "pending" | "processing" | "ready" | "failed";

export interface DocumentT {
  id: string;
  project_id: string | null;
  title: string;
  kind: "document" | "meeting" | "record";
  filename: string | null;
  mime_type: string | null;
  size_bytes: number;
  status: DocStatus;
  error: string | null;
  summary: string | null;
  char_count: number;
  version: number;
  superseded_by_id: string | null;
  uploaded_by: string | null;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Chunk {
  id: string;
  ordinal: number;
  page: number | null;
  content: string;
}

export interface DocumentDetail extends DocumentT {
  chunks: Chunk[];
  uploader: User | null;
}

export interface Citation {
  n: number;
  document_id: string;
  chunk_id: string;
  title: string;
  kind: string;
  page: number | null;
  snippet: string;
  score: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  confidence: number | null;
  answered: boolean;
  created_at: string;
}

export interface Thread {
  id: string;
  title: string;
  project_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ThreadDetail extends Thread {
  messages: Message[];
}

export interface AskResult {
  thread: Thread;
  question: Message;
  answer: Message;
}

export type DecisionStatus = "active" | "proposed" | "superseded" | "revoked";

export interface Decision {
  id: string;
  project_id: string | null;
  meeting_id: string | null;
  title: string;
  rationale: string | null;
  approved_by: string | null;
  decided_on: string | null;
  status: DecisionStatus;
  superseded_by_id: string | null;
  source_quote: string | null;
  last_confirmed_at: string | null;
  created_at: string;
  updated_at: string;
  meeting_title: string | null;
}

export type ActionStatus = "open" | "in_progress" | "done";

export interface ActionItem {
  id: string;
  project_id: string | null;
  meeting_id: string | null;
  title: string;
  owner_name: string | null;
  owner_user_id: string | null;
  due_on: string | null;
  status: ActionStatus;
  source_quote: string | null;
  completed_at: string | null;
  created_at: string;
  overdue: boolean;
  meeting_title: string | null;
}

export interface Question {
  id: string;
  project_id: string | null;
  meeting_id: string | null;
  question: string;
  source: "meeting" | "chat";
  times_asked: number;
  status: "open" | "answered" | "dismissed";
  answer: string | null;
  created_at: string;
}

export interface Meeting {
  id: string;
  project_id: string | null;
  document_id: string | null;
  title: string;
  held_on: string;
  attendees: string[];
  summary: string | null;
  status: DocStatus;
  error: string | null;
  created_at: string;
}

export interface MeetingDetail extends Meeting {
  decisions: Decision[];
  action_items: ActionItem[];
  open_questions: Question[];
}

export interface Conflict {
  id: string;
  kind: "decision" | "document";
  a_ref: string;
  b_ref: string;
  a_label: string;
  b_label: string;
  a_text: string;
  b_text: string;
  explanation: string;
  status: string;
  created_at: string;
}

export interface Gaps {
  questions: Question[];
  outdated: { document: DocumentT; reason: string }[];
  conflicts: Conflict[];
}

export interface Overview {
  documents: number;
  meetings: number;
  decisions_active: number;
  actions_open: number;
  actions_overdue: number;
  actions_unassigned: number;
  open_questions: number;
  conflicts: number;
  recent_decisions: Decision[];
  upcoming_actions: ActionItem[];
  recent_documents: DocumentT[];
}
