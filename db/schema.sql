-- Schema della lega di fantacalcio.
-- Da eseguire nel SQL Editor di Supabase (Postgres). Lo stesso schema, in
-- versione SQLite, viene creato automaticamente da src/fantacalcio/demo_data.py
-- per il database di demo usato quando non ci sono credenziali.

create table if not exists squadre (
    id          bigserial primary key,
    nome        text not null unique,
    allenatore  text not null,
    crediti     integer not null default 500,
    creata_il   timestamptz not null default now()
);

create table if not exists giocatori (
    id          bigserial primary key,
    nome        text not null,
    ruolo       text not null check (ruolo in ('P', 'D', 'C', 'A')),
    club        text not null,
    quotazione  integer not null default 1
);

create table if not exists rose (
    squadra_id    bigint not null references squadre(id) on delete cascade,
    giocatore_id  bigint not null references giocatori(id) on delete cascade,
    prezzo        integer not null default 1,
    primary key (squadra_id, giocatore_id)
);

-- Un giocatore appartiene a una sola squadra della lega.
create unique index if not exists rose_giocatore_unico on rose (giocatore_id);

create table if not exists calendario (
    id              bigserial primary key,
    giornata        integer not null,
    casa_id         bigint not null references squadre(id) on delete cascade,
    trasferta_id    bigint not null references squadre(id) on delete cascade,
    gol_casa        integer,
    gol_trasferta   integer,
    punti_casa      numeric(6, 2),
    punti_trasferta numeric(6, 2),
    unique (giornata, casa_id, trasferta_id)
);

create table if not exists prestazioni (
    giornata          integer not null,
    giocatore_id      bigint not null references giocatori(id) on delete cascade,
    voto              numeric(4, 2),
    gol_segnati       integer not null default 0,
    gol_su_rigore     integer not null default 0,
    rigori_sbagliati  integer not null default 0,
    rigori_parati     integer not null default 0,
    gol_subiti        integer not null default 0,
    autogol           integer not null default 0,
    assist            integer not null default 0,
    ammonizioni       integer not null default 0,
    espulsioni        integer not null default 0,
    primary key (giornata, giocatore_id)
);

create table if not exists formazioni (
    giornata         integer not null,
    squadra_id       bigint not null references squadre(id) on delete cascade,
    giocatore_id     bigint not null references giocatori(id) on delete cascade,
    titolare         boolean not null default false,
    ordine_panchina  integer not null default 0,
    primary key (giornata, squadra_id, giocatore_id)
);

-- Regole della lega: una riga per chiave, lette da regole_da_dict().
create table if not exists regole (
    chiave  text primary key,
    valore  numeric not null
);

create index if not exists idx_calendario_giornata on calendario (giornata);
create index if not exists idx_prestazioni_giornata on prestazioni (giornata);
create index if not exists idx_formazioni_giornata on formazioni (giornata, squadra_id);

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
-- La lega e' pubblica in lettura (chiunque abbia il link vede classifica e
-- rose) ma scrivibile solo da chi e' autenticato come admin. La scrittura
-- dall'app avviene con la service key, che bypassa la RLS: tienila fuori dal
-- repo e mettila solo nei secret di Streamlit Cloud.

alter table squadre     enable row level security;
alter table giocatori   enable row level security;
alter table rose        enable row level security;
alter table calendario  enable row level security;
alter table prestazioni enable row level security;
alter table formazioni  enable row level security;
alter table regole      enable row level security;

do $$
declare
    t text;
begin
    foreach t in array array[
        'squadre', 'giocatori', 'rose', 'calendario',
        'prestazioni', 'formazioni', 'regole'
    ]
    loop
        execute format(
            'drop policy if exists "lettura pubblica" on %I', t
        );
        execute format(
            'create policy "lettura pubblica" on %I for select using (true)', t
        );
    end loop;
end $$;
