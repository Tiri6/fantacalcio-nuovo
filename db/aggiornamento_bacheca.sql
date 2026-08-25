-- FantaCalcio NuoVo — aggiunge la bacheca a un database gia' esistente.
--
-- Da eseguire nel SQL Editor di Supabase dopo aver aggiornato il sito.
-- Rieseguibile: non cancella e non duplica niente.

create table if not exists annunci (
    id            bigserial primary key,
    lega_id       bigint not null references leghe(id) on delete cascade,
    titolo        text not null,
    -- Markdown. Non viene mai reso con unsafe_allow_html.
    testo         text not null,
    tipo          text not null default 'NOTIZIA',
    autore_id     bigint,
    autore_nome   text not null default '',
    giornata      integer,
    pubblicato    boolean not null default true,
    in_evidenza   boolean not null default false,
    creato_il     timestamptz not null default now(),
    aggiornato_il timestamptz
);

create index if not exists idx_annunci_lega on annunci (lega_id, pubblicato);

alter table annunci enable row level security;

drop policy if exists "lettura pubblica" on annunci;
create policy "lettura pubblica" on annunci for select using (true);

-- I privilegi: la service_role bypassa la RLS ma non i GRANT, e senza quello
-- sulla sequenza ogni inserimento fallirebbe.
grant all privileges on annunci to service_role;
grant usage, select on sequence annunci_id_seq to service_role;
grant select on annunci to anon, authenticated;
