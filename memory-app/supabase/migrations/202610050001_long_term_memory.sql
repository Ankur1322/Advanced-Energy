-- Production long-term memory schema for AI chat.
-- Run with: supabase db push

create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists public.conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null default 'New conversation',
  summary text,
  pinned boolean not null default false,
  message_count integer not null default 0,
  summarized_message_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  role text not null check (role in ('system', 'user', 'assistant', 'tool')),
  content text not null,
  token_count integer not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists public.memories (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  conversation_id uuid references public.conversations(id) on delete set null,
  content text not null,
  embedding vector(1536) not null,
  importance double precision not null default 0.5 check (importance >= 0 and importance <= 1),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.memory_rate_limits (
  user_id uuid primary key references auth.users(id) on delete cascade,
  window_started timestamptz not null default now(),
  request_count integer not null default 0
);

create index if not exists conversations_user_updated_idx
  on public.conversations (user_id, pinned desc, updated_at desc);

create index if not exists messages_conversation_created_idx
  on public.messages (conversation_id, created_at asc);

create index if not exists memories_user_created_idx
  on public.memories (user_id, created_at desc);

create index if not exists memories_conversation_idx
  on public.memories (conversation_id) where conversation_id is not null;

-- Realtime powers sidebar ordering and live message delivery in the React app.
do $$
begin
  alter publication supabase_realtime add table public.conversations;
exception when duplicate_object then null;
end;
$$;

do $$
begin
  alter publication supabase_realtime add table public.messages;
exception when duplicate_object then null;
end;
$$;

-- HNSW gives good recall without a training step and is preferred for production pgvector.
create index if not exists memories_embedding_hnsw_idx
  on public.memories using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists conversations_set_updated_at on public.conversations;
create trigger conversations_set_updated_at
before update on public.conversations
for each row execute function public.set_updated_at();

create or replace function public.bump_conversation_after_message()
returns trigger
language plpgsql
as $$
begin
  update public.conversations
  set
    message_count = message_count + 1,
    updated_at = now()
  where id = new.conversation_id;
  return new;
end;
$$;

drop trigger if exists messages_bump_conversation on public.messages;
create trigger messages_bump_conversation
after insert on public.messages
for each row execute function public.bump_conversation_after_message();

create or replace function public.match_memories(
  query_embedding vector(1536),
  match_user_id uuid,
  match_count integer default 8,
  match_conversation_id uuid default null
)
returns table (
  id uuid,
  user_id uuid,
  conversation_id uuid,
  content text,
  importance double precision,
  metadata jsonb,
  created_at timestamptz,
  similarity double precision
)
language sql
stable
as $$
  select
    memories.id,
    memories.user_id,
    memories.conversation_id,
    memories.content,
    memories.importance,
    memories.metadata,
    memories.created_at,
    1 - (memories.embedding <=> query_embedding) as similarity
  from public.memories
  where
    memories.user_id = match_user_id
    and (
      match_conversation_id is null
      or memories.conversation_id = match_conversation_id
      or memories.conversation_id is null
    )
  order by memories.embedding <=> query_embedding
  limit least(greatest(match_count, 1), 20);
$$;

create or replace function public.consume_embedding_rate_limit(
  target_user_id uuid,
  max_requests integer default 60
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  current_window timestamptz;
  current_count integer;
begin
  insert into public.memory_rate_limits (user_id) values (target_user_id)
  on conflict (user_id) do nothing;
  select window_started, request_count into current_window, current_count
  from public.memory_rate_limits where user_id = target_user_id for update;
  if current_window < now() - interval '1 minute' then
    update public.memory_rate_limits set window_started = now(), request_count = 1 where user_id = target_user_id;
    return true;
  end if;
  if current_count >= least(greatest(max_requests, 1), 120) then return false; end if;
  update public.memory_rate_limits set request_count = request_count + 1 where user_id = target_user_id;
  return true;
end;
$$;

alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.memories enable row level security;

drop policy if exists "Users manage own conversations" on public.conversations;
create policy "Users manage own conversations"
on public.conversations
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists "Users read own messages" on public.messages;
create policy "Users read own messages"
on public.messages
for select
using (
  exists (
    select 1 from public.conversations
    where conversations.id = messages.conversation_id
      and conversations.user_id = auth.uid()
  )
);

drop policy if exists "Users insert own messages" on public.messages;
create policy "Users insert own messages"
on public.messages
for insert
with check (
  exists (
    select 1 from public.conversations
    where conversations.id = messages.conversation_id
      and conversations.user_id = auth.uid()
  )
);

drop policy if exists "Users read own memories" on public.memories;
create policy "Users read own memories"
on public.memories
for select
using (auth.uid() = user_id);

-- Writes to memories should happen from trusted server code with the Supabase
-- service-role key. This policy intentionally avoids client-side memory writes.
