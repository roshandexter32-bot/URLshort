-- Run this once in Supabase: SQL Editor -> New query -> Run
create table if not exists public.urls (
  code        text primary key,
  long_url    text not null,
  clicks      integer not null default 0,
  expires_at  double precision,          -- unix timestamp, null = never expires
  created_at  timestamptz not null default now()
);

-- Only our server (using the secret/service_role key) touches this table.
alter table public.urls enable row level security;
