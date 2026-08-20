# Note per Claude Code

## Comandi

```bash
.venv/bin/pytest          # test (devono restare veloci: < 2s)
.venv/bin/ruff check .    # lint, deve passare pulito
.venv/bin/streamlit run app.py
.venv/bin/python -m fantacalcio.demo_data   # rigenera il DB di demo
```

Nelle sessioni web il virtualenv lo crea `.claude/hooks/session-start.sh`
all'avvio: non ricrearlo a mano.

## Regole del progetto

- **La logica non importa Streamlit.** `scoring.py`, `standings.py`, `vista.py`
  e `demo_data.py` sono Python puro. Solo `ui.py` e i file in `viste/` possono
  importare `streamlit`. E' quello che tiene i test veloci e senza mock.
- **Niente parametri di regolamento sparsi nel codice.** Ogni bonus, malus e
  soglia sta in `RegoleLega`. Se serve un valore nuovo, si aggiunge li'.
- **Il codice deve funzionare senza credenziali.** `crea_archivio()` cade sul
  backend SQLite quando mancano i secret: non introdurre percorsi che
  richiedono Supabase per avviarsi, o le sessioni cloud diventano inutili.
- **Lo schema vive in due posti** e vanno tenuti allineati: `db/schema.sql`
  (Postgres/Supabase) e `SCHEMA_SQLITE` in `demo_data.py`. Se aggiungi una
  colonna, toccali entrambi.
- **Mai committare secret.** `.streamlit/secrets.toml` e' in `.gitignore`.

## Modifiche tipiche

| Cosa vuoi fare | Dove mettere le mani |
|---|---|
| Cambiare un bonus/malus | `RegoleLega` in `scoring.py` |
| Aggiungere una schermata | nuovo file in `viste/`, poi registralo in `app.py` |
| Nuova tabella o colonna | `db/schema.sql` **e** `SCHEMA_SQLITE`, poi `data.py` |
| Nuova tabella a schermo | funzione pura in `vista.py`, wrapper in cache in `ui.py` |

Le viste sono script eseguiti da `st.navigation`: il codice a livello di modulo
e' normale, non e' un errore di stile.

## Test

Ogni funzione nuova in `scoring.py`, `standings.py` o `vista.py` vuole il suo
test. I test dei dati usano `ArchivioSQLite` su una tmp_path, mai il DB in
`data/`.
