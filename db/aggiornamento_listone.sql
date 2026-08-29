-- Ruolo Classic nel listone
-- ---------------------------------------------------------------------------
-- Da incollare nel SQL Editor di Supabase e premere Run. Una riga sola: e'
-- gia' dentro `db/schema.sql`, questo file serve solo a non dover rieseguire
-- tutto lo schema.
--
-- Perche' una colonna nuova e non un calcolo: il ruolo Classic (P/D/C/A) non
-- si ricava da quelli Mantra. Un esterno «E» in Classic puo' essere difensore
-- o centrocampista, e a deciderlo e' il listone, non una regola.

alter table giocatori add column if not exists ruolo_classic text not null default '';
