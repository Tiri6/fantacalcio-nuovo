# Note per Claude Code

> **Leggi prima [MEMORIA.md](MEMORIA.md)**: dice a che punto e' il progetto,
> cosa e' gia' stato deciso e quali trappole sono gia' costate tempo.
> A fine sessione aggiornalo con `/memoria`.

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
- **La logica non importa Streamlit.** Possono farlo solo `ui.py`,
  `schermate.py` e i file in `viste/`. E' quello che tiene i test veloci e la
  logica riutilizzabile. Nota che `tema.py` **non** importa Streamlit: produce
  stringhe di CSS e HTML, e' `ui.py` a iniettarle. Cosi' l'aspetto grafico si
  prova senza far girare un server.
- **Le verifiche restituiscono violazioni, non booleani.** Ogni controllo nuovo
  produce una `Violazione` con articolo, gravita', valore e limite: l'utente
  deve sapere *di quanto* sfora, non solo *che* sfora.
- **Blocco o avviso dipende dal `Momento`.** Prima di aggiungere un controllo,
  chiediti se e' vincolante anche in stagione (vedi la tabella nel README).
- **Lo schema vive in due posti** e vanno tenuti allineati: `db/schema.sql`
  (Postgres) e `SCHEMA_SQLITE` in `demo_data.py`. Una colonna nuova va aggiunta
  in tre punti: le due copie dello schema, **piu'** un `alter table ... add
  column if not exists` in fondo a `schema.sql`, altrimenti chi ha gia' un
  database non la vedra' mai. Nel demo SQLite ci pensa `_schema_aggiornato()`,
  che ricostruisce il file quando manca qualcosa.
- **La demo deve restare conforme.** `test_ogni_squadra_ha_una_rosa_conforme`
  lo verifica: se aggiungi un vincolo, aggiorna il generatore.
- **Mai committare secret.** `.streamlit/secrets.toml` e' in `.gitignore`.
- **Dopo una scrittura chiama `ui.invalida_dati()`**, non `st.cache_data.clear()`:
  svuotare una cache provoca un rerun immediato che cancella il messaggio di
  conferma appena mostrato. Le cache sono indicizzate su un numero di versione.
- **I messaggi che precedono un `st.rerun()` non si vedono.** Mettili nel
  `session_state` e mostrali in cima alla pagina al giro successivo.
- **Il contatore di versione delle cache e' globale**, non nel session_state:
  le cache di Streamlit sono condivise fra tutte le sessioni, quindi con dieci
  persone collegate un contatore per sessione farebbe leggere dati vecchi a chi
  entra dopo.
- **Una tabella vuota deve avere comunque le sue colonne.** PostgREST non
  le dichiara quando non ci sono righe: `data.con_colonne()` le rimette, e
  l'elenco sta in `COLONNE_ATTESE`. Aggiungendo una tabella, aggiungila li'.
- **Provare solo su SQLite non dimostra niente sul vuoto.** SQLite e'
  piu' informativo di PostgREST: usa il finto backend di
  `tests/test_backend_vuoto.py`.
- **Nelle cache di Streamlit vanno solo DataFrame.** Mai oggetti di dominio:
  un oggetto in cache conserva la forma che aveva quando e' entrato, e dopo
  un aggiornamento del codice rompe l'app con un AttributeError. Si mette in
  cache la tabella grezza (`ui.dati()`) e si ricostruisce a ogni giro.
- **Le voci di menu delle competizioni sono condizionali.** Coppa e
  Supercoppa compaiono solo se la lega le gioca: una voce che parla di una
  competizione inesistente e' peggio di una voce mancante.
- **Under 21 si valuta al 31 agosto**, non alla data del draft: lo status
  si cristallizza li' e vale per tutta la stagione. Vedi
  `competizioni.data_riferimento_u21` e `ui.data_u21()`.
- **`st.stop()` dentro una scheda ferma tutto lo script**, quindi le schede
  successive non si disegnano. Se una scheda non ha niente da mostrare, non
  crearla proprio.
- **I tre cancelli hanno un ordine.** `app.py` chiama in sequenza `richiedi_login` →
  `richiedi_password_nuova` → `richiedi_lega` → `richiedi_squadra`. Ognuno ferma la
  pagina finche' non e' superato: da li' in giu' c'e' sempre un utente dentro
  una lega. Aggiungere un cancello vuol dire aggiungerlo li', non dentro una
  vista.
- **La sessione conserva il nome utente, non l'oggetto `Utente`.** Appena entri
  in una lega o fondi la squadra la riga cambia: un oggetto congelato al
  momento del login mostrerebbe ancora lo stato vecchio.
- **Il testo degli annunci si rende con `st.markdown` senza
  `unsafe_allow_html`.** Lo scrive una persona: Streamlit gli scuda l'HTML
  da solo, e passarlo a `unsafe_allow_html` renderebbe la bacheca un modo
  per iniettare markup nella pagina di tutti gli altri.
- **Il testo scritto dagli utenti passa da `tema._scudo()`** prima di finire in
  un `unsafe_allow_html`. Nome squadra, motto e curva li scrivono i
  partecipanti: senza, chi mette `<script>` come motto lo fa eseguire agli altri.
- **Ogni regola di validazione va scritta nel modulo, accanto al campo.**
  Una regola che l'utente scopre solo dall'errore fa fallire l'operazione
  senza lasciare traccia: chi la subisce crede che il sito sia rotto.
- **I permessi si controllano nel dominio, non solo nell'interfaccia.**
  `Utente.puo_gestire()` e le transizioni in `scambi.py` sollevano
  `TransizioneNonAmmessa`: nascondere un bottone non e' un controllo.

## Dove mettere le mani

| Cosa vuoi fare | Dove |
|---|---|
| Applicare un lodo che cambia una soglia | `ParametriLega` in `regole.py` |
| Aggiungere un vincolo di rosa | `conformita.py` + un test in `test_conformita.py` |
| Cambiare una regola di scambio | `mercato.valida_scambio` + `test_mercato.py` |
| Toccare l'ordine del draft | `draft.ordine_round` + `test_draft.py` |
| Aggiungere una schermata | nuovo file in `viste/`, registrato in `app.py` |
| Nuova tabella o colonna | `db/schema.sql` **e** `SCHEMA_SQLITE`, poi `data.py` |
| Toccare colori o maglia | `identita.py` + `test_identita.py` |
| Cambiare il formato del CSV | `importazione.py` (i sinonimi stanno in `COLONNE_ROSE`) |
| Aggiungere un'opzione di lega | `OpzioniLega` in `leghe.py` + il modulo in `schermate.py` |
| Toccare colori, schede o testate | `tema.py` + `test_tema.py` |
| Toccare la bacheca o i permessi di scrittura | `bacheca.py` + `test_bacheca.py` |
| Toccare i dati anagrafici o la squadra del cuore | `anagrafica.py` + `test_anagrafica.py` |
| Aggiungere una tabella o colonna che l'app scrive | anche `ATTESO` in `diagnostica.py` |
| Toccare coppa, supercoppa o albo d'oro | `competizioni.py` + `test_competizioni.py` |
| Cambiare la corrispondenza Serie A ↔ giornate | `costruisci_weekend` in `competizioni.py` |
| Cambiare le viste del calendario | `viste/calendario.py` |
| Cambiare accesso, registrazione o onboarding | `schermate.py` + `ui.py` |
| Toccare login o permessi | `autenticazione.py` + `test_autenticazione.py` |
| Cambiare il ciclo di uno scambio | `scambi.py` + `test_scambi.py` |

Le viste sono script eseguiti da `st.navigation`: il codice a livello di
modulo e' normale, non e' un errore di stile.

## Prima di dare per buona una regola

Il regolamento e' un PDF con redline: alcune frasi hanno una versione vecchia
barrata e una nuova. Vale **sempre la nuova**. I punti ambigui sono elencati in
`PUNTI_APERTI.md`: se ne incontri uno, non indovinare — aggiungilo li' e
implementa l'ipotesi piu' vicina a Leghe Fantacalcio, rendendola un parametro.
