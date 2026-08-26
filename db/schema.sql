-- FantaCalcio NuoVo - schema Postgres per Supabase.
-- Da eseguire nel SQL Editor. Lo stesso schema in versione SQLite sta in
-- fantacalcio/demo_data.py (SCHEMA_SQLITE): se aggiungi una colonna qui,
-- aggiungila anche li'.

-- Una lega e i suoi partecipanti. Il codice d'invito e' cio' che si gira agli
-- amici perche' possano entrare senza che l'admin li crei a mano.
create table if not exists leghe (
    id             bigserial primary key,
    nome           text not null,
    -- Formato XXXX-XXXX, alfabeto senza caratteri confondibili (fantacalcio/leghe.py).
    codice_invito  text not null unique,
    admin_id       bigint,
    stagione       text not null default '2026/27',
    -- Opzioni di gioco (modalita', moduli, bonus, modificatori) come JSON.
    -- Sono decine di caselle e cambiano ogni stagione: una colonna per ognuna
    -- vorrebbe dire una migrazione di schema a ogni casella nuova. I vincoli
    -- *del regolamento* restano invece tipizzati in ParametriLega.
    opzioni        text not null default '{}',
    creata_il      timestamptz not null default now()
);

-- Posti riservati a un indirizzo email. L'app non spedisce mail: registra chi
-- e' atteso, cosi' chi arriva con quell'email trova il posto gia' pronto.
create table if not exists inviti (
    id          bigserial primary key,
    lega_id     bigint not null references leghe(id) on delete cascade,
    email       text not null,
    codice      text not null,
    stato       text not null default 'in_attesa',
    creato_da   bigint,
    creato_il   timestamptz not null default now(),
    unique (lega_id, email)
);

create table if not exists squadre (
    id                  bigserial primary key,
    nome                text not null unique,
    presidente          text not null,
    -- Identita' della squadra: motto, stadio e colori sociali.
    motto               text not null default '',
    stadio              text not null default '',
    -- Citta' e curva: identita' che i partecipanti scrivono creando la squadra.
    citta               text not null default '',
    curva               text not null default '',
    colore_primario     text not null default '#2e7d32',
    colore_secondario   text not null default '#ffffff',
    -- Nome del membro di StileMaglia (TINTA_UNITA, STRISCE, BANDE, ...).
    stile_maglia        text not null default 'TINTA_UNITA',
    -- Logo e maglia personalizzata come data URI: sono dieci immagini piccole,
    -- tenerle qui evita di dipendere da uno storage esterno.
    logo                text,
    maglia_caricata     text,
    anno_fondazione     integer,
    lega_id             bigint references leghe(id) on delete cascade,
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

-- Albo d'oro: chi ha vinto cosa. Si scrive a fine competizione e resta.
create table if not exists albo (
    id             bigserial primary key,
    lega_id        bigint not null references leghe(id) on delete cascade,
    -- Nome del membro di TipoCompetizione (CAMPIONATO, COPPA_ITALIA, SUPERCOPPA).
    competizione   text not null,
    stagione       text not null,
    squadra_id     bigint references squadre(id) on delete set null,
    -- Il nome si copia: una squadra puo' sparire, il titolo resta suo.
    squadra_nome   text not null,
    note           text not null default '',
    registrato_il  timestamptz not null default now(),
    unique (lega_id, competizione, stagione)
);

-- Risultati importati da Leghe Fantacalcio: il gestionale non li calcola.
create table if not exists calendario (
    id               bigserial primary key,
    giornata         integer not null,
    -- A quale competizione appartiene la partita.
    competizione     text not null default 'CAMPIONATO',
    -- La giornata di Serie A vera a cui corrisponde questo turno: e' cio' che
    -- permette di dire «6º weekend: 1ª di campionato, 7º: Coppa Italia».
    giornata_serie_a integer,
    data_prevista    date,
    turno            text not null default '',
    casa_id          bigint not null references squadre(id) on delete cascade,
    trasferta_id     bigint not null references squadre(id) on delete cascade,
    gol_casa         integer,
    gol_trasferta    integer,
    punti_casa       numeric(6, 2),
    punti_trasferta  numeric(6, 2),
    unique (giornata, competizione, casa_id, trasferta_id)
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
    -- Obbligatoria in registrazione: e' l'unico dato che lega un account a una
    -- persona reale, e fa combaciare chi si iscrive con l'invito che lo attende.
    email          text,
    cognome        text not null default '',
    data_nascita   date,
    -- Nome del membro di Sesso (MASCHIO, FEMMINA, ALTRO, NON_DICHIARATO).
    sesso          text not null default 'NON_DICHIARATO',
    citta          text not null default '',
    squadra_preferita text not null default '',
    squadra_id     bigint references squadre(id) on delete set null,
    -- NULL = registrato ma non ancora dentro nessuna lega: vede l'onboarding.
    lega_id        bigint references leghe(id) on delete set null,
    -- Alzato da una reimpostazione: al primo accesso il sito obbliga a
    -- sostituire la password scelta da qualcun altro.
    deve_cambiare_password boolean not null default false,
    attivo         boolean not null default true,
    creato_il      timestamptz not null default now()
);

-- Bacheca della lega: notizie, comunicazioni e recap di giornata.
-- Scrive chi amministra, leggono tutti. `pubblicato` a false = bozza.
create table if not exists annunci (
    id            bigserial primary key,
    lega_id       bigint not null references leghe(id) on delete cascade,
    titolo        text not null,
    -- Markdown. Non viene mai reso con unsafe_allow_html: lo rende Streamlit,
    -- che scuda l'HTML, quindi un annuncio non puo' iniettare markup.
    testo         text not null,
    tipo          text not null default 'NOTIZIA',
    autore_id     bigint,
    autore_nome   text not null default '',
    -- Valorizzata sui recap: dice a quale giornata si riferisce l'annuncio.
    giornata      integer,
    pubblicato    boolean not null default true,
    in_evidenza   boolean not null default false,
    creato_il     timestamptz not null default now(),
    aggiornato_il timestamptz
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

-- ---------------------------------------------------------------------------
-- Aggiornamento di un database gia' esistente
-- ---------------------------------------------------------------------------
-- `create table if not exists` non tocca una tabella che c'e' gia': su un
-- database creato prima delle leghe multiple le colonne nuove non
-- comparirebbero, e l'app fallirebbe alla prima scrittura. Questi ALTER sono
-- idempotenti, quindi rilanciare l'intero file e' sempre sicuro.
--
-- Vanno PRIMA degli indici: `create index ... on squadre (lega_id)` su un
-- database vecchio fallirebbe, perche' la colonna non c'e' ancora.

alter table squadre add column if not exists citta   text not null default '';
alter table squadre add column if not exists curva   text not null default '';
alter table squadre add column if not exists lega_id bigint references leghe(id) on delete cascade;

alter table utenti  add column if not exists email   text;
alter table utenti  add column if not exists deve_cambiare_password boolean not null default false;
alter table utenti  add column if not exists cognome text not null default '';
alter table utenti  add column if not exists data_nascita date;
alter table utenti  add column if not exists sesso text not null default 'NON_DICHIARATO';
alter table utenti  add column if not exists citta text not null default '';
alter table utenti  add column if not exists squadra_preferita text not null default '';

alter table calendario add column if not exists competizione text not null default 'CAMPIONATO';
alter table calendario add column if not exists giornata_serie_a integer;
alter table calendario add column if not exists data_prevista date;
alter table calendario add column if not exists turno text not null default '';
alter table utenti  add column if not exists lega_id bigint references leghe(id) on delete set null;

create index if not exists idx_scambi_stato on scambi (stato);
create index if not exists idx_scambi_movimenti on scambi_movimenti (scambio_id);

create index if not exists idx_leghe_codice on leghe (codice_invito);
create index if not exists idx_inviti_lega on inviti (lega_id);
create index if not exists idx_annunci_lega on annunci (lega_id, pubblicato);
create index if not exists idx_albo_lega on albo (lega_id, stagione);
create index if not exists idx_calendario_competizione on calendario (competizione, giornata);
create index if not exists idx_squadre_lega on squadre (lega_id);
create index if not exists idx_utenti_lega on utenti (lega_id);

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

alter table leghe       enable row level security;
-- `inviti` NON ha lettura pubblica: contiene gli indirizzi email dei partecipanti.
alter table inviti      enable row level security;
alter table annunci     enable row level security;
alter table albo        enable row level security;
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
        'leghe', 'annunci', 'albo', 'squadre', 'giocatori', 'contratti', 'dead_money',
        'calendario', 'parametri', 'lodi', 'scambi', 'scambi_movimenti'
    ]
    loop
        execute format('drop policy if exists "lettura pubblica" on %I', t);
        execute format(
            'create policy "lettura pubblica" on %I for select using (true)', t
        );
    end loop;
end $$;
