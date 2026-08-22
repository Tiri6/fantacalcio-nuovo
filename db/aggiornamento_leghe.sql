-- FantaCalcio NuoVo — aggiornamento di un database gia' esistente.
--
-- Fa la stessa cosa di `schema.sql` ma solo per la parte nuova (leghe,
-- inviti, identita' estesa della squadra): serve a chi ha gia' il database
-- della versione precedente e non vuole incollare l'intero schema — per
-- esempio dal telefono. Su un database vuoto usa `schema.sql`, non questo.
--
-- Rieseguibile: non cancella e non duplica niente.
-- Dopo questo, esegui `migrazione_lega_unica.sql`, altrimenti gli utenti
-- esistenti restano senza lega e all'accesso finiscono sull'onboarding.

create table if not exists leghe (
    id             bigserial primary key,
    nome           text not null,
    codice_invito  text not null unique,
    admin_id       bigint,
    stagione       text not null default '2026/27',
    opzioni        text not null default '{}',
    creata_il      timestamptz not null default now()
);

create table if not exists inviti (
    id         bigserial primary key,
    lega_id    bigint not null references leghe(id) on delete cascade,
    email      text not null,
    codice     text not null,
    stato      text not null default 'in_attesa',
    creato_da  bigint,
    creato_il  timestamptz not null default now(),
    unique (lega_id, email)
);

alter table squadre add column if not exists citta   text not null default '';
alter table squadre add column if not exists curva   text not null default '';
alter table squadre add column if not exists lega_id bigint references leghe(id) on delete cascade;

alter table utenti  add column if not exists email   text;
alter table utenti  add column if not exists lega_id bigint references leghe(id) on delete set null;

create index if not exists idx_leghe_codice on leghe (codice_invito);
create index if not exists idx_inviti_lega  on inviti (lega_id);
create index if not exists idx_squadre_lega on squadre (lega_id);
create index if not exists idx_utenti_lega  on utenti (lega_id);

alter table leghe  enable row level security;
alter table inviti enable row level security;

drop policy if exists "lettura pubblica" on leghe;
create policy "lettura pubblica" on leghe for select using (true);
