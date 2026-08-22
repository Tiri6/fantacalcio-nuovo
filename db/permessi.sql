-- Ridai al ruolo `service_role` i privilegi sulle tabelle di FantaCalcio NuoVo.
--
-- Sintomo che cura:
--     permission denied for table utenti   (SQLSTATE 42501)
--
-- Perche' serve. La `service_role` bypassa la Row Level Security, ma la RLS e
-- i privilegi di tabella (GRANT) sono due controlli distinti: saltare il primo
-- non da' il secondo. Se i GRANT mancano, PostgreSQL rifiuta prima ancora di
-- guardare le policy — ed e' esattamente cio' che dice l'hint dell'errore.
--
-- Rieseguibile: concedere due volte non fa niente.

grant usage on schema public to anon, authenticated, service_role;

-- Le tabelle esistenti.
grant all privileges on all tables in schema public
    to service_role;

-- Le sequenze: senza, ogni insert su una colonna `bigserial` fallirebbe con
-- «permission denied for sequence», che e' lo stesso problema con un altro nome.
grant all privileges on all sequences in schema public
    to service_role;

grant all privileges on all functions in schema public
    to service_role;

-- Lettura pubblica per chi arriva con la chiave anonima. `utenti` e `inviti`
-- restano fuori: la prima contiene gli hash delle password, la seconda gli
-- indirizzi email dei partecipanti.
grant select on
    leghe, squadre, giocatori, contratti, dead_money,
    calendario, parametri, lodi, scambi, scambi_movimenti
    to anon, authenticated;

-- Le tabelle create da qui in avanti: senza questo, la prossima tabella
-- nascerebbe di nuovo senza privilegi e il guasto tornerebbe.
alter default privileges in schema public
    grant all privileges on tables to service_role;
alter default privileges in schema public
    grant all privileges on sequences to service_role;
