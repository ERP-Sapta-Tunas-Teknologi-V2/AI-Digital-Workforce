create extension if not exists vector;

-- Table: documents

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

create unique index documents_document_chunk_unique on public.documents(document_id, chunk_index);

alter table public.documents add column fts tsvector
generated always as (to_tsvector('simple', coalesce(content, ''))) stored;

create index documents_fts_idx on public.documents using gin (fts);

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
    rrf_k int default 10,
    category_filter text[] default null
)
returns table (
    id bigint,
    content text,
    metadata jsonb,
    chunk_index int,
    embedding vector(1024),
    hybrid_score float
)
language sql
as $$
    with full_text as (
        select
            d.id,
            row_number() over (
                order by ts_rank_cd(d.fts, query) desc
            ) as rank_ix
        from public.documents d,
            lateral (
                select
                    coalesce(
                        nullif(websearch_to_tsquery('simple', query_text), ''),
                        to_tsquery('simple',
                            array_to_string(regexp_split_to_array(trim(query_text), '\s+'), ' | ')
                        )
                    ) as query
            ) q
        where d.fts @@ query
          and (category_filter is null or d.metadata->>'category' = any(category_filter))
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
          and (category_filter is null or d.metadata->>'category' = any(category_filter))
        order by d.embedding <=> query_embedding
        limit least(match_count, 30) * 2
    ),

    fused as (
        select
            coalesce(ft.id, sem.id) as id,
            coalesce(1.0 / (rrf_k + ft.rank_ix), 0.0) * full_text_weight
            + coalesce(1.0 / (rrf_k + sem.rank_ix), 0.0) * semantic_weight
            as hybrid_score
        from full_text ft
        full outer join semantic sem on ft.id = sem.id
    )

    select d.id, d.content, d.metadata, d.chunk_index, d.embedding, fused.hybrid_score
    from fused
    join public.documents d on d.id = fused.id
    order by fused.hybrid_score desc
    limit match_count;
$$;

grant usage, select on sequence public.documents_id_seq to anon;
grant select, insert, update, delete on public.documents to anon;

alter table public.documents enable row level security;

create policy "Allow insert documents" on public.documents for insert to anon with check (true);
create policy "Allow select documents" on public.documents for select to anon using (true);
create policy "Allow update documents" on public.documents for update to anon using (true) with check (true);
create policy "Allow delete documents" on public.documents for delete to anon using (true);

-- Table: interaction_logs

drop table if exists public.interaction_logs;
create table public.interaction_logs (
    id bigint generated always as identity primary key,
    request_id text,
    session_id text,
    query text not null,
    answer text,
    sources jsonb,
    timestamp timestamptz not null default now(),
    anon_id uuid not null
);

grant insert on table public.interaction_logs to anon;
grant usage, select on sequence public.interaction_logs_id_seq to anon;
grant select, insert, update on table public.interaction_logs to service_role;

create policy "Allow anon insert query logs" on public.interaction_logs for insert to anon with check (true);

create or replace function public.delete_expired_interaction_logs()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    deleted_count integer;
begin
    delete from public.interaction_logs i
    where (
        -- baris tanpa feedback: retensi 30 hari
        not exists (
            select 1 from public.response_feedback f
            where f.request_id = i.request_id
        )
        and i.timestamp < now() - interval '30 days'
    )
    or (
        -- baris dengan feedback: retensi 90 hari
        exists (
            select 1 from public.response_feedback f
            where f.request_id = i.request_id
        )
        and i.timestamp < now() - interval '90 days'
    );

    get diagnostics deleted_count = row_count;
    return deleted_count;
end;
$$;

revoke execute on function public.delete_expired_interaction_logs() from anon, authenticated; 

create index idx_interaction_logs_timestamp on public.interaction_logs(timestamp);
create unique index interaction_logs_request_id_unique on public.interaction_logs(request_id);

alter database postgres set timezone = 'Asia/Jakarta';

alter table public.interaction_logs enable row level security;

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
    from public.interaction_logs q
    where q.timestamp >= now() - make_interval(days => days)
    group by q.query
    order by total_queries desc
    limit result_limit;
$$;

revoke execute on function public.get_top_faq(int, int) from anon, authenticated;
grant execute on function public.get_top_faq(int, int) to service_role;

-- Table: chat_usage_logs

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

create index if not exists idx_chat_usage_logs_request_id on public.chat_usage_logs(request_id);
create index if not exists idx_chat_usage_logs_created_at on public.chat_usage_logs(created_at);

grant insert, select on table public.chat_usage_logs to service_role;
grant usage, select on all sequences in schema public to service_role;

-- Table: index_usage_logs

create table if not exists public.index_usage_logs (
    id bigint generated by default as identity primary key,
    embedding_model text,
    embedding_cost numeric(18, 10) default 0,
    embedding_tokens integer default 0,
    created_at timestamptz default now()
);

create index if not exists idx_index_usage_logs_id on public.index_usage_logs(id);
create index if not exists idx_index_usage_logs_created_at on public.index_usage_logs(created_at);

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

revoke execute on function public.get_daily_cost_report(date) from anon, authenticated;
revoke execute on function public.get_weekly_cost_report(date) from anon, authenticated;

grant execute on function public.get_daily_cost_report(date) to service_role;
grant execute on function public.get_weekly_cost_report(date) to service_role;

-- Table: budget_alerts

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

create index if not exists idx_budget_alerts_created_at on public.budget_alerts(created_at);
create index if not exists idx_budget_alerts_id on public.budget_alerts(id);

grant insert, select on public.budget_alerts to service_role;
grant usage, select on all sequences in schema public to service_role;

-- Table: document_status

create table if not exists public.document_status (
    document_id text primary key,
    source text not null,
    category text not null,
    status text not null default 'pending',
    detail text,
    last_ingested_at timestamptz,
    version_status text not null default 'active',  -- 'active' | 'superseded'
    superseded_by text,   -- document_id versi baru
    superseded_at timestamptz,
    created_at timestamptz default now()
);

create index if not exists idx_document_status_category on public.document_status(category);
create index if not exists idx_document_status_status on public.document_status(status);
create index if not exists idx_document_status_version on public.document_status(version_status);

grant select, insert, update, delete on public.document_status to service_role;
grant usage, select on all sequences in schema public to service_role;

alter table public.document_status enable row level security;

create policy "Allow service_role all on document_status" on public.document_status
for all to service_role using (true) with check (true);

-- Table: ingestion_logs

create table if not exists public.ingestion_logs (
    id bigint generated by default as identity primary key,
    document_id text not null,
    category text not null,
    filename text not null,
    total_chunks int default 0,
    chunks_inserted int default 0,
    chunks_updated int default 0,
    chunks_skipped int default 0,
    chunks_deleted int default 0,
    chunks_failed int default 0,
    parse_error text,
    status text not null,  -- 'success' | 'failed'
    duration_seconds numeric(10, 3),
    created_at timestamptz default now()
);

create index if not exists idx_ingestion_logs_category on public.ingestion_logs(category);
create index if not exists idx_ingestion_logs_created_at on public.ingestion_logs(created_at);
create index if not exists idx_ingestion_logs_document_id on public.ingestion_logs(document_id);

grant insert, select on public.ingestion_logs to service_role;
grant usage, select on all sequences in schema public to service_role;

create or replace function public.get_ingestion_report(
    start_date date default current_date - 7,
    end_date date default current_date
)
returns table (
    category text,
    total_runs bigint,
    total_inserted bigint,
    total_updated bigint,
    total_skipped bigint,
    total_deleted bigint,
    total_failed bigint,
    failed_runs bigint
)
language sql
security definer
set search_path = public
as $$
    select
        category,
        count(*) as total_runs,
        coalesce(sum(chunks_inserted), 0) as total_inserted,
        coalesce(sum(chunks_updated), 0) as total_updated,
        coalesce(sum(chunks_skipped), 0) as total_skipped,
        coalesce(sum(chunks_deleted), 0) as total_deleted,
        coalesce(sum(chunks_failed), 0) as total_failed,
        count(*) filter (where status = 'failed') as failed_runs
    from public.ingestion_logs
    where created_at >= start_date
      and created_at < end_date + interval '1 day'
    group by category
    order by category;
$$;

revoke execute on function public.get_ingestion_report(date, date) from anon, authenticated;
grant execute on function public.get_ingestion_report(date, date) to service_role;

-- Table: document_flags

create table if not exists public.document_flags (
    document_id text primary key,
    flag_type text not null,     -- 'duplicate' | 'stale' | 'confidential' | 'expired'
    detail text,
    duplicate_of text,           -- document_id lain jika flag_type = 'duplicate'
    file_hash text,
    created_at timestamptz default now()
);

create index if not exists idx_document_flags_type on public.document_flags(flag_type);

grant select, insert, update, delete on public.document_flags to service_role;

alter table public.document_flags enable row level security;

create policy "Allow service_role all on document_flags" on public.document_flags for all
to service_role using (true) with check (true);

-- Table: response_feedback

create table public.response_feedback (
    id bigserial primary key,
    request_id text not null references public.interaction_logs(request_id) on delete cascade,
    rating text not null check (rating in ('up', 'down')),
    reason text,
    created_at timestamptz default now()
);

create index idx_response_feedback_request_id on public.response_feedback(request_id);
create index idx_response_feedback_rating on public.response_feedback(rating);

grant select, insert, update on public.response_feedback to service_role;
grant usage, select on all sequences in schema public to service_role;

create policy "Allow service_role all on response_feedback" on public.response_feedback
for all to service_role using (true) with check (true);

alter table public.response_feedback enable row level security;
alter table public.response_feedback add constraint response_feedback_request_id_unique unique (request_id);

create or replace function public.get_problematic_answers(
    days int default 30,
    min_downvotes int default 1,
    result_limit int default 20
)
returns table (
    request_id text,
    question text,
    answer text,
    sources jsonb,
    upvotes bigint,
    downvotes bigint,
    reasons text[],
    last_feedback_at timestamptz
)
language sql
security definer
set search_path = public
as $$
    select
        i.request_id,
        i.query as question,
        i.answer,
        i.sources,
        count(*) filter (where f.rating = 'up') as upvotes,
        count(*) filter (where f.rating = 'down') as downvotes,
        array_remove(array_agg(f.reason) filter (where f.rating = 'down'), null) as reasons,
        max(f.created_at) as last_feedback_at
    from public.interaction_logs i
    join public.response_feedback f on f.request_id = i.request_id
    where i.timestamp >= now() - make_interval(days => days)
    group by i.request_id, i.query, i.answer, i.sources
    having count(*) filter (where f.rating = 'down') >= min_downvotes
    order by downvotes desc, last_feedback_at desc
    limit result_limit;
$$;

revoke execute on function public.get_problematic_answers(int, int, int) from anon, authenticated;
grant execute on function public.get_problematic_answers(int, int, int) to service_role;

create or replace function public.get_flagged_documents(
    days int default 30,
    result_limit int default 20
)
returns table (
    source text,
    chunk_index int,
    flagged_count bigint,
    total_referenced_count bigint,
    flag_ratio numeric
)
language sql
security definer
set search_path = public
as $$
    with all_refs as (
        select
            src->>'source' as source,
            (src->>'chunk_index')::int as chunk_index,
            f.rating
        from public.interaction_logs i
        join public.response_feedback f
            on f.request_id = i.request_id
        cross join lateral jsonb_array_elements(
            coalesce(i.sources, '[]'::jsonb)
        ) as src
        where i.timestamp >= now() - make_interval(days => days)
    )
    select
        source,
        chunk_index,
        count(*) filter (where rating = 'down') as flagged_count,
        count(*) as total_referenced_count,
        round(
            count(*) filter (where rating = 'down')::numeric
            / nullif(count(*), 0),
            2
        ) as flag_ratio
    from all_refs
    where source is not null
    group by source, chunk_index
    having count(*) filter (where rating = 'down') > 0
    order by flagged_count desc, flag_ratio desc
    limit result_limit;
$$;

revoke execute on function public.get_flagged_documents(int, int) from anon, authenticated;
grant execute on function public.get_flagged_documents(int, int) to service_role;

create or replace function public.get_dashboard_summary(
    days int default 30
)
returns table (
    query_volume jsonb,
    total_queries bigint,
    total_feedback bigint,
    positive_feedback_rate numeric,
    top_referenced_documents jsonb
)
language sql
security definer
set search_path = public
as $$
    with volume as (
        select
            i.timestamp::date as report_date,
            count(*) as total
        from public.interaction_logs i
        where i.timestamp >= now() - make_interval(days => days)
        group by i.timestamp::date
        order by report_date
    ),

    feedback_summary as (
        select
            count(*) as total_feedback,
            count(*) filter (where rating = 'up') as total_up
        from public.response_feedback f
        join public.interaction_logs i on i.request_id = f.request_id
        where i.timestamp >= now() - make_interval(days => days)
    ),

    doc_refs as (
        select
            src->>'source' as source,
            max(src->>'category') as category,
            count(*) as referenced_count
        from public.interaction_logs i
        cross join lateral jsonb_array_elements(coalesce(i.sources, '[]'::jsonb)) as src
        where i.timestamp >= now() - make_interval(days => days)
          and src->>'source' is not null
        group by src->>'source'
        order by referenced_count desc
        limit 10
    )

    select
        (
            select coalesce(jsonb_agg(jsonb_build_object(
                'date', report_date,
                'total', total
            ) order by report_date), '[]'::jsonb)
            from volume
        ) as query_volume,

        (select coalesce(sum(total), 0) from volume) as total_queries,

        (select total_feedback from feedback_summary) as total_feedback,

        (
            select case
                when total_feedback > 0
                    then round(total_up::numeric / total_feedback * 100, 2)
                else 0
            end
            from feedback_summary
        ) as positive_feedback_rate,

        (
            select coalesce(jsonb_agg(jsonb_build_object(
                'source', source,
                'category', category,
                'referenced_count', referenced_count
            )), '[]'::jsonb)
            from doc_refs
        ) as top_referenced_documents;
$$;

revoke execute on function public.get_dashboard_summary(int) from anon, authenticated;
grant execute on function public.get_dashboard_summary(int) to service_role;