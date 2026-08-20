# Note per Claude Code

Gestionale di FantaCalcio NuoVo. Il gioco sta su Leghe Fantacalcio: qui si
gestiscono contratti, monte anni, Salary Cap/Floor, draft e scambi.
Riferimento normativo: regolamento V2.1 (Agosto 2026), post-redline.

## Comandi

```bash
.venv/bin/pytest          # test: devono restare sotto i 2 secondi
.venv/bin/ruff check .    # deve passare pulito
.venv/bin/ruff format .
.venv/bin/streamlit run app.py
.venv/bin/python -m fantacalcio.demo_data   # rigenera il DB di demo
```

Nelle sessioni web il virtualenv lo crea `.claude/hooks/session-start.sh`
all'avvio: non ricrearlo a mano.

## Regole del progetto

- **Nessun numero del regolamento fuori da `ParametriLega`.** Se scrivi `66`,
  `100_000_000`, `33` o `0.5` da qualche altra parte, e' un errore: la lega
  cambia le regole per votazione e devono restare modificabili in un punto solo.
- **La logica non importa Streamlit.** Solo `ui.py` e i file in `viste/`
  possono importare `streamlit`. E' quello che tiene i test veloci e la logica
  riutilizzabile.
- **Le verifiche restituiscono violazioni, non booleani.** Ogni controllo nuovo
  produce una `Violazione` con articolo, gravita', valore e limite: l'utente
  deve sapere *di quanto* sfora, non solo *che* sfora.
- **Blocco o avviso dipende dal `Momento`.** Prima di aggiungere un controllo,
  chiediti se e' vincolante anche in stagione (vedi la tabella nel README).
- **Lo schema vive in due posti** e vanno tenuti allineati: `db/schema.sql`
  (Postgres) e `SCHEMA_SQLITE` in `demo_data.py`.
- **La demo deve restare conforme.** `test_ogni_squadra_ha_una_rosa_conforme`
  lo verifica: se aggiungi un vincolo, aggiorna il generatore.
- **Mai committare secret.** `.streamlit/secrets.toml` e' in `.gitignore`.

## Dove mettere le mani

| Cosa vuoi fare | Dove |
|---|---|
| Applicare un lodo che cambia una soglia | `ParametriLega` in `regole.py` |
| Aggiungere un vincolo di rosa | `conformita.py` + un test in `test_conformita.py` |
| Cambiare una regola di scambio | `mercato.valida_scambio` + `test_mercato.py` |
| Toccare l'ordine del draft | `draft.ordine_round` + `test_draft.py` |
| Aggiungere una schermata | nuovo file in `viste/`, registrato in `app.py` |
| Nuova tabella o colonna | `db/schema.sql` **e** `SCHEMA_SQLITE`, poi `data.py` |

Le viste sono script eseguiti da `st.navigation`: il codice a livello di
modulo e' normale, non e' un errore di stile.

## Prima di dare per buona una regola

Il regolamento e' un PDF con redline: alcune frasi hanno una versione vecchia
barrata e una nuova. Vale **sempre la nuova**. I punti ambigui sono elencati in
`PUNTI_APERTI.md`: se ne incontri uno, non indovinare — aggiungilo li' e
implementa l'ipotesi piu' vicina a Leghe Fantacalcio, rendendola un parametro.
