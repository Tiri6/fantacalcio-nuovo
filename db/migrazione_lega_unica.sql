-- Aggancia a una lega i dati creati PRIMA che il sito gestisse piu' leghe.
--
-- Quando serve: hai gia' un database con utenti e squadre, e dopo aver
-- rilanciato `schema.sql` le colonne `lega_id` sono vuote. Senza questo
-- passaggio ogni partecipante, entrando, si ritroverebbe sulla schermata
-- "non sei ancora in una lega" e ne creerebbe una per conto suo.
--
-- Da eseguire UNA VOLTA nel SQL Editor di Supabase, dopo `db/schema.sql`.
-- Rieseguirlo non fa danni: se una lega esiste gia', si ferma senza toccare
-- niente.

do $$
declare
    alfabeto  text := 'ABCDEFGHJKMNPQRSTWXYZ23456789';
    grezzo    text := '';
    codice    text;
    lega_id_nuova bigint;
    capo      bigint;
begin
    if exists (select 1 from leghe) then
        raise notice 'Esiste gia'' almeno una lega: non tocco niente.';
        return;
    end if;

    if not exists (select 1 from utenti) then
        raise notice 'Nessun utente ancora: la lega la creerai dal sito.';
        return;
    end if;

    -- Stesso alfabeto di fantacalcio/leghe.py: niente O/0 e I/1, perche' il
    -- codice viene ricopiato a mano da uno screenshot.
    for i in 1..8 loop
        grezzo := grezzo
            || substr(alfabeto, floor(random() * length(alfabeto))::int + 1, 1);
    end loop;
    codice := substr(grezzo, 1, 4) || '-' || substr(grezzo, 5, 4);

    -- L'admin e' il presidente se c'e', altrimenti il primo utente registrato.
    select id into capo from utenti where ruolo = 'presidente' order by id limit 1;
    if capo is null then
        select id into capo from utenti order by id limit 1;
        update utenti set ruolo = 'presidente' where id = capo;
    end if;

    insert into leghe (nome, codice_invito, admin_id, stagione, opzioni)
    values ('FantaCalcio NuoVo', codice, capo, '2026/27', '{}')
    returning id into lega_id_nuova;

    update utenti  set lega_id = lega_id_nuova where lega_id is null;
    update squadre set lega_id = lega_id_nuova where lega_id is null;

    raise notice 'Lega creata con codice d''invito %', codice;
end $$;

-- Il codice d'invito da girare ai partecipanti:
select nome as lega, codice_invito as "codice da girare", stagione from leghe;
