create extension if not exists vector;

drop table if exists public.documents;

create table public.documents (
    id bigserial primary key,
    content text,
    metadata jsonb,
    document_id text not null,
    chunk_index int not null,
    fingerprint text not null,
    embedding vector(1024)
);

create unique index documents_document_chunk_unique
on public.documents(document_id, chunk_index);

alter table public.documents
add column fts tsvector
generated always as (
    to_tsvector('simple', coalesce(content, ''))
) stored;

create index documents_fts_idx
on public.documents
using gin (fts);

create or replace function public.match_documents(
    query_embedding vector(1024),
    match_count int default 5
)
returns table (
    id bigint,
    content text,
    metadata jsonb,
    similarity float
)
language sql
as $$
    select
        documents.id,
        documents.content,
        documents.metadata,
        1 - (documents.embedding <=> query_embedding) as similarity
    from public.documents
    where documents.embedding is not null
    order by documents.embedding <=> query_embedding
    limit match_count;
$$;

create or replace function public.hybrid_search(
    query_text text,
    query_embedding vector(1024),
    match_count int default 10,
    full_text_weight float default 1,
    semantic_weight float default 1,
    rrf_k int default 10
)
returns table (
    id bigint,
    content text,
    metadata jsonb,
    embedding vector(1024),
    hybrid_score float
)
language sql
as $$
    with full_text as (
        select
            d.id,
            row_number() over (
                order by ts_rank_cd(
                    d.fts,
                    websearch_to_tsquery('simple', query_text)
                ) desc
            ) as rank_ix
        from public.documents d
        where d.fts @@ websearch_to_tsquery(
            'simple',
            query_text
        )
        order by rank_ix
        limit least(match_count, 30) * 2
    ),

    semantic as (
        select
            d.id,
            row_number() over (
                order by d.embedding <=> query_embedding
            ) as rank_ix
        from public.documents d
        where d.embedding is not null
        order by d.embedding <=> query_embedding
        limit least(match_count, 30) * 2
    ),

    fused as (
        select
            coalesce(ft.id, sem.id) as id,

            coalesce(
                1.0 / (rrf_k + ft.rank_ix),
                0.0
            ) * full_text_weight

            +

            coalesce(
                1.0 / (rrf_k + sem.rank_ix),
                0.0
            ) * semantic_weight

            as hybrid_score

        from full_text ft

        full outer join semantic sem
            on ft.id = sem.id
    )

    select
        d.id,
        d.content,
        d.metadata,
        d.embedding,
        fused.hybrid_score
    from fused
    join public.documents d
        on d.id = fused.id
    order by fused.hybrid_score desc
    limit match_count;
$$;

grant usage, select
on sequence public.documents_id_seq
to anon;

grant select, insert, update, delete
on public.documents
to anon;

alter table public.documents
enable row level security;

create policy "Allow insert documents"
on public.documents
for insert
to anon
with check (true);

create policy "Allow select documents"
on public.documents
for select
to anon
using (true);

create policy "Allow update documents"
on public.documents
for update
to anon
using (true)
with check (true);

create policy "Allow delete documents"
on public.documents
for delete
to anon
using (true);

drop table if exists public.query_logs;

create table public.query_logs (
    id bigint generated always as identity primary key,
    query text not null,
    timestamp timestamptz not null default now(),
    anon_id uuid not null
);

grant insert
on table public.query_logs
to anon;

grant usage, select
on sequence public.query_logs_id_seq
to anon;

create policy "Allow anon insert query logs"
on public.query_logs
for insert
to anon
with check (true);

create or replace function public.delete_expired_query_logs()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    deleted_count integer;
begin
    delete from public.query_logs
    where timestamp < now() - interval '30 days';

    get diagnostics deleted_count = row_count;
    return deleted_count;
end;
$$;

revoke execute
on function public.delete_expired_query_logs()
from anon, authenticated;

create index idx_query_logs_timestamp
on public.query_logs(timestamp);

alter database postgres
set timezone = 'Asia/Jakarta';

grant select, insert
on table public.query_logs
to service_role;

alter table public.query_logs
enable row level security;

create or replace function public.get_top_faq(
    days int default 30,
    result_limit int default 5
)
returns table (
    query text,
    total_queries bigint,
    last_asked timestamptz
)
language sql
security definer
set search_path = public
as $$
    select
        q.query,
        count(*) as total_queries,
        max(q.timestamp) as last_asked
    from public.query_logs q
    where q.timestamp >= now() - make_interval(days => days)
    group by q.query
    order by total_queries desc
    limit result_limit;
$$;

revoke execute
on function public.get_top_faq(int, int)
from anon, authenticated;

grant execute
on function public.get_top_faq(int, int)
to service_role;

create table if not exists public.chat_usage_logs (
    id bigint generated by default as identity primary key,
    request_id text not null,
    anon_id uuid,
    total_cost numeric(18, 10) default 0,
    total_tokens integer default 0,
    embedding_model text,
    embedding_cost numeric(18, 10) default 0,
    embedding_tokens integer default 0,
    llm_model text,
    llm_total_cost numeric(18, 10) default 0,
    llm_input_cost numeric(18, 10) default 0,
    llm_input_tokens integer default 0,
    llm_output_cost numeric(18, 10) default 0,
    llm_output_tokens integer default 0,
    created_at timestamptz default now()
);

create index if not exists idx_chat_usage_logs_request_id
on public.chat_usage_logs(request_id);

create index if not exists idx_chat_usage_logs_created_at
on public.chat_usage_logs(created_at);

grant insert, select on table public.chat_usage_logs to service_role;
grant usage, select on all sequences in schema public to service_role;

create table if not exists public.index_usage_logs (
    id bigint generated by default as identity primary key,
    embedding_model text,
    embedding_cost numeric(18, 10) default 0,
    embedding_tokens integer default 0,
    created_at timestamptz default now()
);

create index if not exists idx_index_usage_logs_id
on public.index_usage_logs(id);

create index if not exists idx_index_usage_logs_created_at
on public.index_usage_logs(created_at);

grant insert, select on table public.index_usage_logs to service_role;
grant usage, select on all sequences in schema public to service_role;

create or replace function public.get_daily_cost_report(
    report_date date default current_date
)
returns table (
    total_cost numeric,
    embedding_cost numeric,
    llm_cost numeric,
    total_tokens bigint,
    embedding_tokens bigint,
    llm_input_tokens bigint,
    llm_output_tokens bigint,
    chat_requests bigint,
    index_runs bigint
)
language sql
security definer
set search_path = public
as $$
    select
        coalesce((
            select sum(total_cost)
            from public.chat_usage_logs
            where created_at >= report_date
              and created_at < report_date + interval '1 day'
        ), 0)
        +
        coalesce((
            select sum(embedding_cost)
            from public.index_usage_logs
            where created_at >= report_date
              and created_at < report_date + interval '1 day'
        ), 0) as total_cost,

        coalesce((
            select sum(embedding_cost)
            from public.chat_usage_logs
            where created_at >= report_date
              and created_at < report_date + interval '1 day'
        ), 0)
        +
        coalesce((
            select sum(embedding_cost)
            from public.index_usage_logs
            where created_at >= report_date
              and created_at < report_date + interval '1 day'
        ), 0) as embedding_cost,

        coalesce((
            select sum(llm_total_cost)
            from public.chat_usage_logs
            where created_at >= report_date
              and created_at < report_date + interval '1 day'
        ), 0) as llm_cost,

        coalesce((
            select sum(total_tokens)
            from public.chat_usage_logs
            where created_at >= report_date
              and created_at < report_date + interval '1 day'
        ), 0)
        +
        coalesce((
            select sum(embedding_tokens)
            from public.index_usage_logs
            where created_at >= report_date
              and created_at < report_date + interval '1 day'
        ), 0) as total_tokens,

        coalesce((
            select sum(embedding_tokens)
            from public.chat_usage_logs
            where created_at >= report_date
              and created_at < report_date + interval '1 day'
        ), 0)
        +
        coalesce((
            select sum(embedding_tokens)
            from public.index_usage_logs
            where created_at >= report_date
              and created_at < report_date + interval '1 day'
        ), 0) as embedding_tokens,

        coalesce((
            select sum(llm_input_tokens)
            from public.chat_usage_logs
            where created_at >= report_date
              and created_at < report_date + interval '1 day'
        ), 0) as llm_input_tokens,

        coalesce((
            select sum(llm_output_tokens)
            from public.chat_usage_logs
            where created_at >= report_date
              and created_at < report_date + interval '1 day'
        ), 0) as llm_output_tokens,

        coalesce((
            select count(*)
            from public.chat_usage_logs
            where created_at >= report_date
              and created_at < report_date + interval '1 day'
        ), 0) as chat_requests,

        coalesce((
            select count(*)
            from public.index_usage_logs
            where created_at >= report_date
              and created_at < report_date + interval '1 day'
        ), 0) as index_runs;
$$;

create or replace function public.get_weekly_cost_report(
    end_date date default current_date
)
returns table (
    report_date date,
    total_cost numeric,
    embedding_cost numeric,
    llm_cost numeric,
    total_tokens bigint,
    chat_requests bigint,
    index_runs bigint
)
language sql
security definer
set search_path = public
as $$
    with dates as (
        select generate_series(
            end_date - interval '6 days',
            end_date,
            interval '1 day'
        )::date as report_date
    ),

    chat as (
        select
            created_at::date as report_date,
            coalesce(sum(total_cost), 0) as total_cost,
            coalesce(sum(embedding_cost), 0) as embedding_cost,
            coalesce(sum(llm_total_cost), 0) as llm_cost,
            coalesce(sum(total_tokens), 0) as total_tokens,
            count(*) as chat_requests
        from public.chat_usage_logs
        where created_at >= end_date - interval '6 days'
          and created_at < end_date + interval '1 day'
        group by created_at::date
    ),

    indexing as (
        select
            created_at::date as report_date,
            coalesce(sum(embedding_cost), 0) as embedding_cost,
            coalesce(sum(embedding_tokens), 0) as embedding_tokens,
            count(*) as index_runs
        from public.index_usage_logs
        where created_at >= end_date - interval '6 days'
          and created_at < end_date + interval '1 day'
        group by created_at::date
    )

    select
        d.report_date,

        coalesce(c.total_cost, 0)
        + coalesce(i.embedding_cost, 0) as total_cost,

        coalesce(c.embedding_cost, 0)
        + coalesce(i.embedding_cost, 0) as embedding_cost,

        coalesce(c.llm_cost, 0) as llm_cost,

        coalesce(c.total_tokens, 0)
        + coalesce(i.embedding_tokens, 0) as total_tokens,

        coalesce(c.chat_requests, 0) as chat_requests,
        coalesce(i.index_runs, 0) as index_runs

    from dates d
    left join chat c
        on c.report_date = d.report_date
    left join indexing i
        on i.report_date = d.report_date
    order by d.report_date;
$$;

revoke execute
on function public.get_daily_cost_report(date)
from anon, authenticated;

revoke execute
on function public.get_weekly_cost_report(date)
from anon, authenticated;

grant execute
on function public.get_daily_cost_report(date)
to service_role;

grant execute
on function public.get_weekly_cost_report(date)
to service_role;

create table if not exists public.budget_alerts (
    id bigint generated by default as identity primary key,
    period_type text not null,
    period_date date not null,
    alert_type text not null,
    cost numeric(18, 10) not null,
    budget numeric(18, 10) not null,
    usage_percent numeric(10, 2) not null,
    created_at timestamptz default now(),
    unique(period_type, period_date, alert_type)
);

create index if not exists idx_budget_alerts_created_at
on public.budget_alerts(created_at);

create index if not exists idx_budget_alerts_id
on public.budget_alerts(id);

grant insert, select
on public.budget_alerts
to service_role;

grant usage, select
on all sequences in schema public
to service_role;