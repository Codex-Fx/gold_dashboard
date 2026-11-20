-- Run this ONCE in Supabase: Dashboard -> SQL Editor -> New query -> paste -> Run

-- one row per symbol per day
create table if not exists daily_prices (
    symbol text not null,
    date   date not null,
    open   double precision not null,
    high   double precision not null,
    low    double precision not null,
    close  double precision not null,
    primary key (symbol, date)      -- the same day can never be saved twice
);

-- one row every time the update script runs (used by the "Last update" text)
create table if not exists update_log (
    id            bigint generated always as identity primary key,
    ran_at        timestamptz not null default now(),
    status        text not null,               -- 'OK' or 'FAILED'
    rows_loaded   integer not null default 0,
    rows_rejected integer not null default 0,  -- rows that failed Pydantic validation
    message       text
);

-- Row Level Security ON: nobody can read or write with the public (anon) key.
-- Our scripts use the service_role / secret key, which bypasses RLS.
alter table daily_prices enable row level security;
alter table update_log   enable row level security;
