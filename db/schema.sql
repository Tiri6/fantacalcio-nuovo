-- FantaCalcio NuoVo - schema Postgres per Supabase.
-- Da eseguire nel SQL Editor. Lo stesso schema in versione SQLite sta in
-- fantacalcio/demo_data.py (SCHEMA_SQLITE): se aggiungi una colonna qui,
-- aggiungila anche li'.

create table if not exists squadre (
    id                  bigserial primary key,
    nome                text not null unique,
    presidente          text not null,
    -- Identita' della squadra: motto, stadio e colori sociali.
    motto               text not null default '',
    stadio              text not null default '',
    colore_primario     text not null default '#2e7d32',
    colore_secondario   text not null default '#ffffff',
    -- Nome del membro di StileMaglia (TINTA_UNITA, STRISCE, BANDE, ...).
    stile_maglia        text not null default 'TINTA_UNITA',
    -- Logo e maglia personalizzata come data URI: sono dieci immagini piccole,
    -- tenerle qui evita di dipendere da uno storage esterno.
    logo                text,
    maglia_caricata     text,
    anno_fondazione     integer,
    creata_il           timestamptz not null default now()
);

create table if not exists giocatori (
    id            bigserial primary key,
    -- Id del listone ufficiale Fantacalcio: aggancia il giocatore alle
    -- quotazioni anche se il nome viene scritto diversamente.
    id_ufficiale  integer unique,
    nome          text not null,
    club          text not null,
    -- Ruoli Mantra separati da ';' (es. 'Dd;E'). Un giocatore puo' averne piu' di uno.
    ruoli         text not null,
    -- Stipendio annuo lordo, fonte ufficiale Capology (art. 4).
    ingaggio      numeric(12, 2) not null default 0,
    nazionalita   text not null default 'Italia',
    data_nascita  date,
    -- Dal listone: quotazione Mantra e valore di mercato. Non c'entrano con il
    -- Salary Cap (che usa gli ingaggi Capology) ma servono al draft.
    quotazione    numeric(6, 2),
    fvm           numeric(8, 2)
);

-- Un giocatore ha al massimo un contratto: la chiave primaria lo garantisce.
create table if not exists contratti (
    giocatore_id            bigint primary key references giocatori(id) on delete cascade,
    squadra_id              bigint not null references squadre(id) on delete cascade,
    anni_residui            integer not null check (anni_residui between 1 and 5),
    -- Lodo Corti: un giocatore puo' essere prolungato una sola volta in lega.
    prolungato              boolean not null default false,
    stagione_prolungamento  text
);

-- Lodo Origi: 50% del valore contrattuale residuo, addebitato in un'unica
-- soluzione alla prima sessione di mercato utile. Non concorre al Salary Floor.
create table if not exists dead_money (
    id              bigserial primary key,
    squadra_id      bigint not null references squadre(id) on delete cascade,
    giocatore_id    bigint references giocatori(id) on delete set null,
    nome_giocatore  text not null,
    importo         numeric(12, 2) not null,
    stagione        text not null,
    addebitato      boolean not null default false
);

-- Risultati importati da Leghe Fantacalcio: il gestionale non li calcola.
create table if not exists calendario (
    id               bigserial primary key,
    giornata         integer not null,
    casa_id          bigint not null references squadre(id) on delete cascade,
    trasferta_id     bigint not null references squadre(id) on delete cascade,
    gol_casa         integer,
    gol_trasferta    integer,
    punti_casa       numeric(6, 2),
    punti_trasferta  numeric(6, 2),
    unique (giornata, casa_id, trasferta_id)
);

-- Parametri del regolamento: permette di applicare un lodo senza rideployare.
-- Le chiavi corrispondono ai campi di ParametriLega (fantacalcio/regole.py).
create table if not exists parametri (
    chiave  text primary key,
    valore  numeric not null
);

-- Registro dei lodi: le decisioni prese a maggioranza entrano nel regolamento
-- (principio di tassativita', art. 1).
create table if not exists lodi (
    id           bigserial primary key,
    codice       text not null unique,
    titolo       text not null,
    testo        text not null,
    articolo     text,
    approvato_il date,
    stagione     text
);


-- Partecipanti alla lega. La password si conserva come hash scrypt con sale
-- per utente: vedi fantacalcio/autenticazione.py.
create table if not exists utenti (
    id             bigserial primary key,
    nome_utente    text not null unique,
    nome           text not null,
    hash_password  text not null,
    sale           text not null,
    ruolo          text not null default 'fantallenatore',
    squadra_id     bigint references squadre(id) on delete set null,
    attivo         boolean not null default true,
    creato_il      timestamptz not null default now()
);

-- Registro degli scambi (art. 8): proposta, accettazione, ratifica.
create table if not exists scambi (
    id                  bigserial primary key,
    squadra_a_id        bigint not null references squadre(id) on delete cascade,
    squadra_b_id        bigint not null references squadre(id) on delete cascade,
    proposto_da         bigint not null references utenti(id),
    stato               text not null default 'proposto',
    note                text not null default '',
    creato_il           timestamptz not null default now(),
    aggiornato_il       timestamptz,
    deciso_da           bigint references utenti(id),
    ratificato_da       bigint references utenti(id),
    -- Art. 8: senza 24 ore di preavviso lo scambio vale dalla giornata dopo.
    giornata_efficacia  integer
);

create table if not exists scambi_movimenti (
    id              bigserial primary key,
    scambio_id      bigint not null references scambi(id) on delete cascade,
    giocatore_id    bigint not null references giocatori(id) on delete cascade,
    nome_giocatore  text not null,
    da_squadra_id   bigint not null references squadre(id) on delete cascade,
    a_squadra_id    bigint not null references squadre(id) on delete cascade,
    anni_prima      integer not null,
    anni_dopo       integer not null
);

create index if not exists idx_scambi_stato on scambi (stato);
create index if not exists idx_scambi_movimenti on scambi_movimenti (scambio_id);

create index if not exists idx_contratti_squadra on contratti (squadra_id);
create index if not exists idx_dead_money_squadra on dead_money (squadra_id);
create index if not exists idx_calendario_giornata on calendario (giornata);

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
-- Le policy qui sotto aprono la lettura, ma l'app usa comunque la chiave
-- service_role (che bypassa la RLS) perche' deve anche scrivere: creare utenti,
-- importare rose, ratificare scambi. Streamlit gira sul server, quindi quella
-- chiave non raggiunge mai il browser; a proteggere le scritture ci pensa il
-- sistema di permessi in fantacalcio/autenticazione.py.
-- Tieni la service_role solo nei secret del deploy, mai nel repository.
--
-- Nota: `utenti` NON ha lettura pubblica, perche' contiene gli hash delle
-- password. Con la sola chiave anon il login non funzionerebbe.

alter table squadre     enable row level security;
alter table giocatori   enable row level security;
alter table contratti   enable row level security;
alter table dead_money  enable row level security;
alter table calendario  enable row level security;
alter table parametri   enable row level security;
alter table lodi        enable row level security;
alter table scambi      enable row level security;
alter table scambi_movimenti enable row level security;
-- `utenti` NON ha lettura pubblica: contiene gli hash delle password.
alter table utenti      enable row level security;

do $$
declare
    t text;
begin
    foreach t in array array[
        'squadre', 'giocatori', 'contratti', 'dead_money',
        'calendario', 'parametri', 'lodi', 'scambi', 'scambi_movimenti'
    ]
    loop
        execute format('drop policy if exists "lettura pubblica" on %I', t);
        execute format(
            'create policy "lettura pubblica" on %I for select using (true)', t
        );
    end loop;
end $$;
