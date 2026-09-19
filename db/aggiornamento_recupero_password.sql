-- Recupero della password
-- ---------------------------------------------------------------------------
-- Da incollare nel SQL Editor di Supabase e premere Run. E' gia' dentro
-- `db/schema.sql`: questo file serve solo a non dover rieseguire tutto lo
-- schema su un database che esiste gia'. Si puo' rieseguire senza danno.
--
-- Serve per le due strade che riportano dentro chi ha dimenticato la password:
-- il **codice di recupero**, che ognuno si salva dal proprio profilo, e la
-- **richiesta al presidente**, che ora resta scritta nel sito.

-- Il codice di recupero e' una seconda password, monouso: si conserva cifrata
-- esattamente come l'altra, quindi chi leggesse il database non se ne fa
-- niente. Vuoto = quell'utente non ne ha ancora generato uno.
alter table utenti add column if not exists hash_recupero text not null default '';
alter table utenti add column if not exists sale_recupero text not null default '';

-- Qui non ci sono segreti, solo il nome di chi non riesce a entrare.
create table if not exists richieste_password (
    id          bigserial primary key,
    lega_id     bigint references leghe(id) on delete cascade,
    utente_id   bigint references utenti(id) on delete cascade,
    nome_utente text not null,
    chiesta_il  text,
    stato       text not null default 'aperta',
    chiusa_il   text,
    chiusa_da   bigint references utenti(id) on delete set null,
    nota        text not null default ''
);

create index if not exists idx_richieste_password_stato
    on richieste_password (lega_id, stato);

-- Niente lettura pubblica: la tabella dice chi ha perso la password, e non e'
-- affare di chi passa di li' col solo link dell'app. Ci scrive e la legge
-- l'applicazione, con la chiave service_role.
alter table richieste_password enable row level security;
