# Note per Claude Code

> **Leggi prima [MEMORIA.md](MEMORIA.md)**: dice a che punto e' il progetto,
> cosa e' gia' stato deciso e quali trappole sono gia' costate tempo.
> A fine sessione aggiornalo con `/memoria`.

Gestionale di FantaCalcio NuoVo. Il gioco sta su Leghe Fantacalcio: qui si
gestiscono contratti, monte anni, Salary Cap/Floor, draft e scambi.
Riferimento normativo: regolamento **V3** (testo definitivo, Ottobre 2026).

## Comandi

```bash
.venv/bin/pytest          # i test del dominio restano sotto i 2 secondi
.venv/bin/ruff check .    # deve passare pulito
.venv/bin/ruff format .
.venv/bin/python -m fantacalcio.demo_data   # rigenera il DB di demo

# Il sito: API e pagine insieme, su http://127.0.0.1:8000
.venv/bin/python -m uvicorn api.main:app --reload
cd web && npm run build   # **questo**, non `npx tsc --noEmit`: il `tsc -b`
                          # dello script usa i tsconfig dell'app, piu' severi
```

Nelle sessioni web il virtualenv lo crea `.claude/hooks/session-start.sh`
all'avvio: non ricrearlo a mano.

## Regole del progetto

- **Nessun numero del regolamento fuori da `ParametriLega`.** Se scrivi `66`,
  `100_000_000`, `33` o `0.5` da qualche altra parte, e' un errore: la lega
  cambia le regole per votazione e devono restare modificabili in un punto solo.
- **Il dominio non conosce il web.** `fantacalcio/` non importa FastAPI ne'
  sa che esiste un browser: le rotte in `api/` traducono, e basta. E' quello
  che tiene i test veloci e la logica riutilizzabile — e il motivo per cui
  togliere Streamlit, che era l'unico frontend, non ha toccato una riga di
  regole.
- **Le regole stanno nel dominio anche quando servirebbe una riga sola nel
  browser.** Una somma rifatta in TypeScript e' una seconda copia della regola:
  il giorno che la lega vota, la pagina dice una cosa e il server ne applica
  un'altra. Se al browser serve un numero che discende da una regola, lo manda
  il server gia' calcolato.
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
- **Mai committare secret.** In produzione si passano come variabili
  d'ambiente (`fly secrets set`), in sviluppo si esportano nella shell. Un
  test (`test_segreti.py`) rilegge i file versionati e cerca chiavi vere.
- **Una tabella vuota deve avere comunque le sue colonne.** PostgREST non
  le dichiara quando non ci sono righe: `data.con_colonne()` le rimette, e
  l'elenco sta in `COLONNE_ATTESE`. Aggiungendo una tabella, aggiungila li'.
- **Provare solo su SQLite non dimostra niente sul vuoto.** SQLite e'
  piu' informativo di PostgREST: usa il finto backend di
  `tests/test_backend_vuoto.py`.
- **Nel sito React i colori sono token, mai valori scritti nelle regole.**
  Stanno in cima a `web/src/stile.css`, in due blocchi: tema scuro e tema
  chiaro. Un `#1a2b20` dentro una regola resta scuro anche sul tema chiaro, e
  si nota solo guardando — e' cosi' che testata e menu erano rimasti neri in
  mezzo a una pagina bianca. La scelta sta in `web/src/tema.ts`.
- **Le voci di menu delle competizioni sono condizionali.** Coppa e
  F1 Rush compaiono solo se la lega le gioca: una voce che parla di una
  competizione inesistente e' peggio di una voce mancante.
- **Under 21 si valuta al 31 agosto**, non alla data del draft: lo status
  si cristallizza li' e vale per tutta la stagione. Vedi
  `competizioni.data_riferimento_u21` e `Contesto.riferimento_u21`.
- **I cancelli d'ingresso li decide `ChiSono`.** Il sito guarda `lega_id` e
  `squadra_id` di chi e' entrato e manda all'onboarding finche' mancano: il
  server li rilegge a ogni richiesta, quindi non serve una chiamata in piu'
  per sapere a che punto si e'. Aggiungere un cancello vuol dire aggiungerlo
  li', in `App.tsx`, non dentro una pagina.
- **La sessione conserva il nome utente, non l'oggetto `Utente`.** Appena entri
  in una lega o fondi la squadra la riga cambia: un oggetto congelato al
  momento del login mostrerebbe ancora lo stato vecchio.
- **Il testo scritto dagli utenti non si inietta mai come HTML.** React scuda
  da solo quel che mette fra parentesi graffe: `dangerouslySetInnerHTML` non
  si usa su nome squadra, motto, curva o annunci, che li scrivono i
  partecipanti. Senza, chi mette `<script>` come motto lo fa eseguire agli
  altri.
- **Ogni regola di validazione va scritta nel modulo, accanto al campo.**
  Una regola che l'utente scopre solo dall'errore fa fallire l'operazione
  senza lasciare traccia: chi la subisce crede che il sito sia rotto.
- **I permessi si controllano nel dominio, non solo nell'interfaccia.**
  `Utente.puo_gestire()` e le transizioni in `scambi.py` sollevano
  `TransizioneNonAmmessa`: nascondere un bottone non e' un controllo.
- **La chat sul regolamento legge un dossier generato, non scritto a mano.**
  `assistente.scheda_regolamento()` chiude con un elenco costruito scorrendo i
  campi di `ParametriLega` e `OpzioniLega`: un parametro nuovo arriva alla chat
  da solo, e un test parametrizzato lo pretende. Non aggiungere numeri a mano
  nel prompt — sarebbe la copia che diverge. Nel dossier non entrano rose,
  contratti o utenti: la chat parla di regole.

## Dove mettere le mani

| Cosa vuoi fare | Dove |
|---|---|
| Applicare un lodo che cambia una soglia | `ParametriLega` in `regole.py` |
| Aggiungere un vincolo di rosa | `conformita.py` + un test in `test_conformita.py` |
| Cambiare una regola di scambio | `mercato.valida_scambio` + `test_mercato.py` |
| Toccare l'ordine del draft | `draft.ordine_round` + `test_draft.py` |
| Aggiungere una schermata | nuovo file in `web/src/pagine/`, registrato in `App.tsx`, con la sua rotta in `api/rotte/` |
| Toccare la chat sul regolamento | `assistente.py` + `test_assistente.py` |
| Nuova tabella o colonna | `db/schema.sql` **e** `SCHEMA_SQLITE`, poi `data.py` |
| Toccare colori o maglia | `identita.py` + `test_identita.py` |
| Cambiare il formato del CSV | `importazione.py` (i sinonimi stanno in `COLONNE_ROSE`) |
| Toccare il calendario ufficiale di Leghe | `importa_calendario`/`applica_calendario` in `importazione.py` + `test_importazione.py` |
| Toccare chi puo' rivendicare una squadra | `autenticazione.rivendica_squadra` + `api/rotte/onboarding.py` |
| Toccare il tabellino di giornata di Leghe | `leggi_formazioni_leghe`/`applica_formazioni_leghe` in `giornata.py` + `test_formazioni_leghe.py` |
| Toccare chi entra dalla panchina o il cambio modulo | `_chi_entra` in `formazioni.py` + `test_formazioni.py` |
| Aggiungere un'opzione di lega | `OpzioniLega` in `leghe.py` **e** un gruppo in `GRUPPI_OPZIONI` (o un motivo in `FUORI_MODULO`): il modulo del sito si disegna da li' |
| Toccare colori, schede o testate | i token in cima a `web/src/stile.css` |
| Toccare la bacheca o i permessi di scrittura | `bacheca.py` + `test_bacheca.py` |
| Toccare i dati anagrafici o la squadra del cuore | `anagrafica.py` + `test_anagrafica.py` |
| Aggiungere una tabella o colonna che l'app scrive | anche `ATTESO` in `diagnostica.py` |
| Toccare coppa, F1 Rush o albo d'oro | `competizioni.py` + `test_competizioni.py` |
| Toccare il portiere d'emergenza (Lodo Messina) | `emergenza.py` + `test_emergenza.py` |
| Cambiare la corrispondenza Serie A ↔ giornate | `costruisci_weekend` in `competizioni.py` |
| Cambiare le viste del calendario | `web/src/pagine/Calendario.tsx` |
| Cambiare accesso, registrazione o onboarding | `api/rotte/accesso.py` e `registrazione.py` + `web/src/pagine/Accesso.tsx` |
| Toccare la Draft Room | `sala.py` + `api/rotte/sala.py` + `web/src/pagine/Sala.tsx` |
| Toccare login o permessi | `autenticazione.py` + `test_autenticazione.py` |
| Cambiare il ciclo di uno scambio | `scambi.py` + `test_scambi.py` |

Il sito e' **un servizio solo**: la stessa app FastAPI serve le pagine React
gia' costruite (`web/dist`) e l'API che le alimenta. In sviluppo si puo'
tenere Vite a parte, ma in produzione c'e' un contenitore e un indirizzo.

## Prima di dare per buona una regola

Il regolamento e' un PDF con redline: alcune frasi hanno una versione vecchia
barrata e una nuova. Vale **sempre la nuova**. I punti ambigui sono elencati in
`PUNTI_APERTI.md`: se ne incontri uno, non indovinare — aggiungilo li' e
implementa l'ipotesi piu' vicina a Leghe Fantacalcio, rendendola un parametro.
