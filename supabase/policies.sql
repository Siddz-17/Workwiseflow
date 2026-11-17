-- ---------------------------------------------------------------------------------------------------
-- Row Level Security
--
-- The FastAPI backend connects with the database owner role (bypasses RLS) and enforces workspace roles
-- itself. These policies are defense in depth: if anyone queries Supabase directly with a user's JWT
-- (supabase-js, PostgREST), they only ever see rows from workspaces they belong to, and never write.
-- ---------------------------------------------------------------------------------------------------

create or replace function public.is_workspace_member(ws text)
returns boolean
language sql
security definer
stable
set search_path = public
as $$
  select exists (
    select 1 from memberships m where m.workspace_id = ws and m.user_id = auth.uid()::text
  );
$$;

alter table users          enable row level security;
alter table workspaces     enable row level security;
alter table memberships    enable row level security;
alter table invites        enable row level security;
alter table projects       enable row level security;
alter table documents      enable row level security;
alter table chunks         enable row level security;
alter table meetings       enable row level security;
alter table decisions      enable row level security;
alter table action_items   enable row level security;
alter table open_questions enable row level security;
alter table conflicts      enable row level security;
alter table chat_threads   enable row level security;
alter table chat_messages  enable row level security;

drop policy if exists "self" on users;
create policy "self" on users for select to authenticated
  using (id = auth.uid()::text or exists (
    select 1 from memberships a join memberships b on a.workspace_id = b.workspace_id
    where a.user_id = auth.uid()::text and b.user_id = users.id));

drop policy if exists "member read" on workspaces;
create policy "member read" on workspaces for select to authenticated using (public.is_workspace_member(id));

do $$
declare t text;
begin
  foreach t in array array['memberships','projects','documents','chunks','meetings','decisions',
                           'action_items','open_questions','conflicts']
  loop
    execute format('drop policy if exists "member read" on %I', t);
    execute format('create policy "member read" on %I for select to authenticated using (public.is_workspace_member(workspace_id))', t);
  end loop;
end $$;

drop policy if exists "own threads" on chat_threads;
create policy "own threads" on chat_threads for select to authenticated using (user_id = auth.uid()::text);

drop policy if exists "own messages" on chat_messages;
create policy "own messages" on chat_messages for select to authenticated
  using (exists (select 1 from chat_threads t where t.id = thread_id and t.user_id = auth.uid()::text));

-- Invites are only visible to the backend (service role).

-- ---------------------------------------------------------------------------------------------------
-- Storage: private bucket for uploaded documents and transcripts. Only the backend (service role)
-- reads and writes it; users download through the API, which checks workspace membership.
-- ---------------------------------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('documents', 'documents', false)
on conflict (id) do nothing;
