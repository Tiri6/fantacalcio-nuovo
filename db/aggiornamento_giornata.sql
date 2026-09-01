-- Formazioni, voti e orario di inizio giornata
-- ---------------------------------------------------------------------------
-- Da incollare nel SQL Editor di Supabase e premere Run. E' gia' dentro
-- `db/schema.sql`: questo file serve solo a non dover rieseguire tutto lo
-- schema su un database che esiste gia'. Si puo' rieseguire senza danno.
--
-- Serve per la pagina «Formazione» (si schiera e si salva, fino a un minuto
-- prima del calcio d'inizio) e per la pagina «Giornata» (gli scontri diretti
-- e il pulsante «Calcola» del presidente).

-- Quando comincia la giornata: e' l'orario su cui si chiudono le formazioni.
-- Se resta vuoto non si blocca niente, e le formazioni restano modificabili.
alter table calendario add column if not exists inizio_previsto timestamptz;

-- `titolari` e `panchina` sono liste di id separate da virgola, **in ordine**:
-- l'ordine della panchina decide chi entra nelle sostituzioni automatiche, e
-- una tabella di righe lo perderebbe se qualcuno non ci mettesse una colonna
-- di posizione. Una stringa ordinata e' piu' onesta di una finta relazione.
create table if not exists formazioni (
    id            bigserial primary key,
    squadra_id    bigint not null references squadre(id) on delete cascade,
    giornata      integer not null,
    competizione  text not null default 'CAMPIONATO',
    modulo        text not null,
    titolari      text not null default '',
    panchina      text not null default '',
    aggiornata_il text,
    unique (squadra_id, giornata, competizione)
);

-- Un voto per giocatore per giornata. `voto` nullo = senza voto: e' diverso
-- da zero, ed e' quel che fa scattare la sostituzione.
create table if not exists voti (
    id               bigserial primary key,
    giocatore_id     bigint not null references giocatori(id) on delete cascade,
    giornata         integer not null,
    voto             numeric(4, 2),
    gol              integer not null default 0,
    gol_su_rigore    integer not null default 0,
    rigori_sbagliati integer not null default 0,
    rigori_parati    integer not null default 0,
    autogol          integer not null default 0,
    assist           integer not null default 0,
    ammonizioni      integer not null default 0,
    espulsioni       integer not null default 0,
    gol_subiti       integer not null default 0,
    imbattuto        boolean not null default false,
    unique (giocatore_id, giornata)
);

create index if not exists idx_formazioni_giornata on formazioni (giornata, competizione);
create index if not exists idx_voti_giornata on voti (giornata);

alter table formazioni enable row level security;
alter table voti       enable row level security;

-- La formazione degli altri, nel fantacalcio, si guarda: la lettura e'
-- pubblica come per il calendario. A scrivere ci pensa l'app con la chiave
-- service_role, e chi puo' salvare cosa lo decide fantacalcio/autenticazione.py.
do $$
declare
    t text;
begin
    foreach t in array array['formazioni', 'voti']
    loop
        execute format('drop policy if exists "lettura pubblica" on %I', t);
        execute format(
            'create policy "lettura pubblica" on %I for select using (true)', t
        );
    end loop;
end $$;
