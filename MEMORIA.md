# Memoria del progetto

Stato corrente di FantaCalcio NuoVo. **Chi apre una sessione nuova legge questo
file per primo**: dice dove siamo, cosa e' gia' deciso e cosa non va rifatto.

Claude Code carica `CLAUDE.md` da solo a ogni avvio, e da li' arriva qui: non
serve chiedere "leggi la memoria", basta dire cosa si vuole fare.

> Aggiornare con `/memoria` a fine sessione, prima del push.

---

## In una riga

Gestionale della lega: contratti, monte anni, Salary Cap/Floor, draft, scambi.
Il gioco (voti, formazioni, risultati) resta su Leghe Fantacalcio.

**Ultimo aggiornamento:** 25 settembre 2026 — la giornata completa (formazioni, blocco, voti, calcolo), le regole Mantra ufficiali, il recupero password, le regole di lega modificabili dal presidente e la chat AI sul regolamento.

---

## Decisioni prese (non riaprirle senza motivo)

| Decisione | Quando | Nota |
|---|---|---|
| Fasce di gol: **primo gol a 66**, poi uno ogni 6 | confermata dalla lega | L'art. 1 cita anche 60: e' la formulazione del regolamento a essere imprecisa, non il codice |
| Il **draft si fa offline** e si carica via CSV | confermata | Il sito non conduce l'asta: serve l'import, che c'e' |
| Stack **Streamlit + Supabase** | scelta iniziale | La logica e' Python puro senza Streamlit: un cambio di frontend non la tocca |
| Il campo squadra si chiama **presidente** | rinominato da `fantallenatore` | |
| Maglie **disegnate dai colori sociali** in SVG | | Chi vuole carica un'immagine propria |
| **Registrazione autonoma**: ognuno si crea l'account | 21 ago | Il primo che si registra diventa presidente |
| Si entra in una lega con un **codice d'invito** di 8 caratteri | 21 ago | Alfabeto senza O/0 e I/1: si ricopia da uno screenshot |
| Gli **inviti per email non spediscono niente** | 21 ago | Registrano chi e' atteso. Un server di posta per dieci persone non si giustifica |
| Le **opzioni di lega** stanno in JSON, non in colonne | 21 ago | Cambiano ogni stagione: una migrazione per casella sarebbe un costo continuo |
| La **squadra si puo' rimandare** ("Lo faccio dopo") | 21 ago | Chi amministra e basta non deve restare chiuso fuori |
| **Si resta su Streamlit per la stagione di prova** | 22 ago | La migrazione a un'autenticazione vera si valuta l'anno prossimo, dopo aver visto cosa serve davvero giocando |
| Le cache si invalidano con **`ui.invalida_dati()`** | | Vedi le trappole sotto |
| Le **sostituzioni Mantra** si scelgono creando la lega: Easy / Basic / Master | set | Sono le tre della piattaforma. Cambiano *l'ordine delle priorita'*, non il numero di sostituzioni |
| Il **portiere non si adatta mai**, in nessuna delle due direzioni | set | Verificata sul regolamento: un giocatore di movimento non va in porta, e un portiere non gioca in campo. La tabella lo isola riga e colonna |
| La formazione si **blocca un minuto prima** del calcio d'inizio | set | Dopo il blocco quelle di tutti si vedono, non si cambiano |
| Le **regole di lega si cambiano anche dopo la creazione**, ma solo da chi la lega l'ha creata | 23 set | Serviva per non rifare la lega a ogni ripensamento. Il permesso si controlla nel dominio, non nascondendo il bottone |
| La **chat sul regolamento** legge un dossier generato dai parametri, mai il ricordo del modello | 24 set | Un test parametrizzato pretende che ogni campo di `ParametriLega` e `OpzioniLega` compaia nel dossier |

## Cosa c'e' (funziona e ha i test)

- **Motore di regole**: monte anni 66, rosa 30-33 (36 con Under 21), max 3
  portieri, regola "1/3", Salary Cap 100M, Salary Floor 80M, Dead Money al 50%.
- **Draft Lottery** a due fasce, ordine di chiamata con la deroga dei round
  multipli di 3, probabilita' delle pick stimate per simulazione.
- **Import CSV** di rose e risultati, con anteprima di conformita' *prima* di
  scrivere.
- **Identita' squadre**: presidente, motto, stadio, colori, maglia, logo.
- **Login** con ruoli: il presidente ratifica e importa, gli altri gestiscono
  solo la propria squadra.
- **Registro scambi**: proposta → accettazione → ratifica, con ri-validazione
  al momento della ratifica e applicazione ai contratti.
- **Leghe multiple**: creazione con tutte le opzioni di gioco (modalita',
  formato, rosa, asta, moduli, bonus/malus, fasce di gol, modificatori di
  reparto), codice d'invito, inviti per email, pagina «La lega».
- **Tre cancelli all'ingresso**: accesso/registrazione → crea o unisciti a una
  lega → fonda la squadra (nome, citta', stadio, curva, colori, maglia).
- **Bacheca dei titoli** nella pagina Squadre: si popola da sola dall'albo
  d'oro, nessun dato da tenere allineato a mano.
- **Identita' modificabile da dove la si guarda**: l'editor sta in
  `schermate.modulo_identita` e lo usano sia «Squadre» sia «Identita'
  squadre». Prima esisteva solo nella seconda, e sembrava non ci fosse.
- **Bacheca**: notizie, comunicazioni e recap di giornata, con bozze e
  annunci in evidenza. Scrive chi amministra la lega, leggono tutti. E' la
  pagina d'ingresso.
- **Calendario**: tutti gli incroci in tre viste — per giornata, griglia
  degli scontri diretti squadra per squadra, e la stagione di una singola
  squadra con il bilancio.
- **Competizioni**: campionato sempre, Coppa Italia e Supercoppa a scelta
  creando la lega. Tabellone della coppa, finaliste di supercoppa dedotte
  dall'albo d'oro (a mano il primo anno), albo d'oro storicizzato.
- **Calendario dei weekend**: la corrispondenza fra giornata di Serie A e
  giornata di lega. Un turno di coppa occupa un weekend e fa **slittare**
  il campionato, non lo salta.
- **Lista giocatori** con proprietario o svincolato, flag Ita e U21.
- **Squadre**: identita', rosa con nazionalita'/eta'/U21, anni di
  contratto residui e budget cap residuo.
- **Assegnazioni**: draft giocatore per giocatore, o modello CSV.
- **Ruolo editor**: chi il presidente autorizza a scrivere in bacheca.
- **Diagnostica dello schema** (`diagnostica.py`): confronta il database con
  quello che il codice si aspetta e produce la query di riparazione. Un
  avviso solo nella barra laterale invece di errori rossi su ogni pagina.
- **Registrazione completa**: nome, cognome, data di nascita all'italiana,
  sesso, citta', squadra del cuore (Serie A dal listone + Serie B + le due
  voci «Altro»). Email **obbligatoria** e unica.
- **Password**: cambio autonomo da «Il mio profilo», e reimpostazione da
  parte del presidente che genera una temporanea mostrata una volta sola.
  Chi la riceve e' obbligato a sostituirla al primo accesso.
- **Tema grafico** (`tema.py`): fondo scuro, verde campo, testate, schede,
  riquadri numerici con barra, pastiglie nei colori sociali. Non importa
  Streamlit: produce stringhe, quindi si prova nei test.
- **Formazione**: si schiera e si salva fino a un minuto prima del calcio
  d'inizio; dopo il blocco si vedono quelle di tutti, disegnate sul campo
  secondo il modulo scelto. Cambiando modulo i giocatori restano dove il
  nuovo schema li ammette, e chi non ci sta va in panchina.
- **Giornata**: gli scontri diretti di campionato o coppa, le due formazioni
  una di fronte all'altra coi punti su ogni maglia, e il pulsante del
  presidente che carica i voti e calcola la giornata.
- **Mantra per intero**: la tabella ufficiale delle sostituzioni (12 ruoli,
  righe = casella da coprire, colonne = chi entra), la legenda dei tre
  asterischi, le caselle di ogni modulo, il malus a chi gioca fuori
  posizione e le tre modalita' Easy/Basic/Master. Sta in `mantra.py`, che e'
  **dato trascritto a mano**: i test ne provano la *forma* (quadrata,
  diagonale libera, portiere isolato, asimmetria riga per riga) perche' un
  errore di battitura qui non alza nessuna eccezione, cambia in silenzio chi
  puo' entrare in campo.
- **Recupero password**: chi dimentica la password non resta fuori. Codice di
  recupero generato da «Il mio profilo», oppure richiesta che il presidente
  vede e approva. La migrazione e' `db/aggiornamento_recupero_password.sql`.
- **Regole di lega modificabili**: chi ha creato la lega le cambia anche dopo,
  senza rifarla. Stesso modulo che le crea, e prima di salvare mostra
  l'elenco di cosa cambia. Il permesso si controlla in `leghe.py`.
- **Chat sul regolamento** (`assistente.py` + `viste/regolamento_chat.py`):
  si chiede una norma a parole. Il modello riceve un dossier costruito dai
  parametri di *questa* lega, dalle tabelle Mantra e da `PUNTI_APERTI.md`, e
  ha istruzioni di non inventare numeri. Serve `ANTHROPIC_API_KEY`: senza,
  la pagina spiega come attivarla invece di rompersi.

## Cosa manca (in ordine di utilita')

1. **Assegnazioni, contratti e ingaggi**: il listone e' caricato (509 giocatori
   con ruoli Mantra e quotazioni) ma non dice chi appartiene a quale squadra,
   con quanti anni e con quale ingaggio. Gli ingaggi vanno da Capology
   (art. 4). Finche' mancano, Salary Cap e Floor sono a zero.
2. **Data di nascita e nazionalita'**: senza, lo status Under 21 non si puo'
   determinare e l'espansione rosa non si applica.
3. **Svincoli registrati**: oggi il Dead Money si calcola ma non si scrive.
   Serve un flusso come quello degli scambi.
4. **Registro dei lodi**: la tabella c'e' nello schema, manca la pagina.
5. **Tabellone del draft** da proiettare durante l'asta.
6. **I vincoli dichiarati ma non imposti**: minimo di italiani, minimo di
   Under 21 italiani e numero di scambi a stagione si scelgono creando la
   lega, si mostrano nel Regolamento, ma nessun controllo li fa rispettare.
7. **Coppa e supercoppa si importano insieme al campionato**: servirebbero
   import separati per competizione.

## In sospeso, con l'innesco

Cose decise ma non ancora eseguibili: manca un dato o un permesso. Quando
l'innesco scatta, si riprende da qui senza ricostruire il contesto.

### Eseguire `db/aggiornamento_giornata.sql` su Supabase

**Innesco:** subito. E' l'unica cosa in sospeso che oggi **rompe una pagina**.

La migrazione aggiunge `formazioni`, `voti` e la colonna `inizio_previsto` del
calendario. Finche' non gira, la pagina Formazione muore con un
`postgrest.exceptions.APIError` — la tabella non esiste. Si apre l'SQL Editor
di Supabase, si incolla il file, si esegue. E' rieseguibile.

Le altre migrazioni in `db/` sono gia' state eseguite. Se dovesse ricapitare
un dubbio, la barra laterale ha la diagnostica dello schema: dice quali
tabelle mancano e produce la query di riparazione.

### Accendere la chat sul regolamento

**Innesco:** Marco incolla una chiave dell'API di Anthropic nei secret.

Serve `ANTHROPIC_API_KEY` (console.anthropic.com → Settings → API keys), da
mettere nei Secrets di Streamlit Cloud o in `.streamlit/secrets.toml` in
locale. Senza, la pagina si apre lo stesso e spiega come attivarla: non e'
una rottura, e' una funzione spenta.

**Mai provata con una chiave vera.** Il codice e' stato verificato fino al
401 (chiave finta: la richiesta arriva ad Anthropic e l'errore diventa una
frase in italiano). La prima risposta vera la vedra' Marco: se sbaglia un
numero, il difetto e' nel dossier di `assistente.scheda_regolamento()`, non
nel modello.

### Le sei tabelle di moduli non trascritte

**Innesco:** Marco rimanda l'immagine leggibile, o detta gli slot.

`CASELLE_PER_MODULO` in `mantra.py` copre cinque moduli su undici. Mancano
**3-4-2-1, 3-5-2, 3-5-1-1, 4-3-3, 4-4-2, 4-4-1-1**: nell'immagine ricevuta
non erano leggibili e non si indovinano. Resta anche aperta una domanda mai
risposta: `MODULI_MANTRA` elenca 16 moduli, la tabella ufficiale ne mostra
11 — vanno tolti quelli a cinque difensori?

### Aggiungere il secondo collaboratore

**Innesco:** scattato il 22 agosto — l'username e' `kakkaboom`
(github.com/kakkaboom). Resta da eseguire il punto 1: l'invito lo deve
mandare Marco, il token di sessione non ha il permesso di aggiungere
collaboratori.

Da fare, in quest'ordine:

1. `github.com/Tiri6/fantacalcio-nuovo` → **Settings** → **Collaborators** →
   *Add people* → username dell'amico → permesso **Write** (non Admin).
2. Girargli [COLLABORARE.md](COLLABORARE.md). Copre invito, collegamento a
   Streamlit, ciclo branch/pull request e le cinque regole.
3. Ricordargli il permesso sulle **repo private** quando Streamlit chiede
   l'autorizzazione a GitHub: senza, Streamlit risponde *"This repository does
   not exist"*, che e' fuorviante.

Perche' Write basta: su Streamlit Community Cloud i permessi dell'app non si
impostano su Streamlit, li decide l'accesso in scrittura al repository. Un
invito solo copre codice e deploy. Admin servirebbe solo per cancellare il
repository o renderlo pubblico — e la cronologia contiene ancora la vecchia
chiave Supabase al commit `ea2a62c`, quindi pubblico non va bene.

### Leggere le rose da Leghe Fantacalcio

**Innesco:** il dominio `fantacalcio.it` diventa raggiungibile, oppure arriva
un export del sito.

La lega vera sta su
`leghe.fantacalcio.it/nuovo-fanta-manageriale`. Dalle sessioni Claude Code su
cloud **non e' raggiungibile**: il gateway di rete rifiuta la CONNECT con 403
per policy, su `leghe.`, `www.` e `api.fantacalcio.it`. Non e' un errore
transitorio e non si aggira: o si allarga la policy dell'environment, o il
file lo esporta Marco a mano.

**Convenzione della lega da non dimenticare:** nel loro export la colonna
**`costo` contiene gli anni di contratto residui**, non un prezzo.
`importazione.py` la riconosce gia' come sinonimo di `anni`.

Quando sara' raggiungibile: creare una Routine settimanale (lunedi mattina)
che rilegge le rose e segnala le differenze. Lo strumento giusto e'
`create_trigger` del server MCP di Claude Code, non `CronCreate`: quest'ultimo
vive solo dentro la sessione e sparisce quando la sessione finisce.

---

## Punti aperti del regolamento

Stanno in `PUNTI_APERTI.md`. I due che contano: quando si **chiudono** le
finestre di mercato (il regolamento dice solo quando aprono) e se il campionato
sara' di 18 o 27 giornate.

## Trappole gia' pagate (non ripeterle)

- **`st.html` non renderizza l'SVG inline.** Passa da un data URI e `st.image`.
- **`st.cache_data.clear()` provoca un rerun** che cancella il messaggio di
  conferma appena mostrato. Usa `ui.invalida_dati()`.
- **I messaggi prima di `st.rerun()` non si vedono.** Mettili nel
  `session_state` e mostrali in cima alla pagina al giro dopo.
- **Il contatore di versione deve essere globale**, non nel session_state: le
  cache di Streamlit sono condivise fra sessioni, e con dieci persone collegate
  chi entra dopo leggerebbe dati vecchi.
- **Il ruolo Mantra `B` (braccetto) esisteva nel listone vero e non nel mio
  modello.** Trovato solo caricando il file ufficiale: i dati veri scoprono
  buchi che i dati inventati non mostrano.
- **Nei CSV separati da `;` i ruoli non vanno scritti `M;C`** ma `M/C`. Il
  lettore ora lo riconosce e lo spiega.
- **La `service_role` bypassa la RLS ma non sostituisce i GRANT.** Sono due
  controlli distinti: senza i privilegi di tabella, PostgreSQL rifiuta con
  «permission denied for table utenti» (42501) prima ancora di guardare le
  policy. La cura sta in `db/permessi.sql`, che chiude anche gli
  `alter default privileges` perche' la prossima tabella non ricada nel
  problema.
- **Streamlit ricarica `app.py` e le pagine in `viste/`, non i moduli gia'
  importati.** Dopo un aggiornamento senza riavvio, `app.py` e' nuovo e
  `fantacalcio/` e' vecchio: il primo campo aggiunto di recente alza un
  AttributeError che uccide il sito. L'unico rimedio e' *Reboot app*, e la
  guardia in `app.py` lo dice invece di mostrare un traceback.
- **Una guardia contro il codice disallineato non puo' stare nel modulo che
  protegge.** Prima versione: `ui.spiega_codice_disallineato()`, che nel
  modulo vecchio non esisteva — l'errore si spostava dentro il gestore
  dell'errore. Ora vive in `app.py` e usa solo `streamlit`.
- **Ricostruire una dataclass per salvarla perde i campi che non nomini.**
  Salvando l'identita' si costruiva una `Squadra` senza `lega_id`, che
  quindi tornava a None: la squadra si scollegava dalla lega a ogni
  salvataggio, senza errori.
- **SQLite e PostgREST rispondono diversamente al «non c'e' niente».**
  SQLite da' una tabella vuota **con le colonne**, PostgREST una lista
  vuota da cui pandas costruisce un DataFrame **senza colonne**: chi fa
  `contratti["squadra_id"]` funziona in locale e alza KeyError in
  produzione. `data.con_colonne()` normalizza, e `tests/test_backend_vuoto.py`
  simula la forma di PostgREST — provare su SQLite non basta mai.
- **Con le squadre create e il draft non ancora fatto, mezzo sito lavora su
  tabelle vuote.** E' lo stato normale di una lega appena nata, non un caso
  limite: ogni pagina va provata anche cosi'.
- **Nelle cache di Streamlit vanno solo DataFrame, mai oggetti di dominio.**
  Un oggetto in cache conserva la forma che aveva quando e' entrato.
  `tests/test_cache.py` lo verifica staticamente.
- **Un turno di coppa non cancella una giornata di campionato**: la fa
  slittare. Il contatore del campionato non avanza nei weekend di coppa,
  altrimenti una giornata sparisce dal calendario senza che nessuno se ne
  accorga.
- **Una colonna mancante su Supabase si vede come errore su piu' pagine.**
  PostgREST e' severo dove SQLite e' indulgente: provare una migrazione sul
  demo SQLite non dimostra niente. La diagnostica esiste per questo.
- **Una regola di validazione non scritta nel modulo e' una trappola.** La
  password minima di 8 caratteri non era dichiarata da nessuna parte:
  scrivendone una corta la registrazione falliva *prima* della scrittura,
  quindi nessun utente nel database e nessuna idea del perche'. Le regole
  vanno scritte accanto al campo, non solo nell'errore.
- **Streamlit rende le tendine come `input[type=text]`**: contare gli input
  per posizione in un test sfalsa gli indici. Selezionare per placeholder.
- **Oltre la decina di pagine `st.navigation` tronca il menu** e nasconde
  le ultime dietro un «altro»: le voci in fondo sembrano non esistere. Le
  sezioni non bastano, serve `expanded=True`.
- **Un'app Streamlit pubblicata da una repo privata e' privata**: la vedono
  solo i collaboratori del repository. In incognito risponde "l'app non
  esiste", e i partecipanti vedrebbero lo stesso. Si apre da *Settings ->
  Sharing -> Who can view this app*.
- **Streamlit non ridispiega sempre da solo.** Se dopo un push il sito mostra
  ancora la versione vecchia, e' il deploy fermo, non il codice: *Reboot app*.
  Prima di cercare un bug, verificare quale versione sta girando davvero.
- **La schermata col codice d'invito va mostrata da *ogni* pagina che puo'
  venire dopo la creazione.** Appena la lega esiste, il cancello successivo
  scatta: metterla solo dentro `scegli_lega` significa non mostrarla mai.
- **`pkill -f "streamlit run app.py"` uccide la propria shell**, perche' il
  pattern combacia con la riga di comando del comando stesso. Costa un giro di
  diagnosi su un bug che non esiste.
- **`create table if not exists` non aggiunge colonne** a una tabella che c'e'
  gia'. Ogni colonna nuova vuole anche un `alter table ... add column if not
  exists` in fondo a `schema.sql`.
- **Ricaricare la pagina fa uscire dal login** (session_state di Streamlit).
  Navigando col menu non succede. Scelta consapevole: un token in cookie
  aggiungerebbe superficie d'attacco per poco guadagno.
- **Un import sotto `TYPE_CHECKING` non esiste a runtime.**
  `carica_richieste_password` costruiva una `RichiestaPassword` importata solo
  per i tipi: NameError a ogni chiamata. Non si e' visto per settimane perche'
  un `except` largo in `ui.py` lo inghiottiva e il presidente vedeva
  semplicemente «nessuna richiesta». Due lezioni in una: il `TYPE_CHECKING`
  vale solo per le annotazioni, e **un `except Exception` che restituisce un
  valore vuoto e' un modo per non sapere mai che qualcosa e' rotto.**
- **La degradazione elegante acceca la diagnostica.** Quando una tabella
  mancante ha smesso di sollevare ed e' diventata «tabella vuota», la
  `verifica()` — che si basava proprio sull'eccezione — ha smesso di
  accorgersene. Ora consulta `arch.assenti`. Se rendi morbido un errore,
  controlla chi su quell'errore ci contava.
- **Un registro globale di modulo inquina i test.** L'elenco delle tabelle
  assenti stava in una variabile di modulo: un test che apriva un database
  rotto lasciava la traccia al test dopo. Ora e' una proprieta' pigra
  sull'istanza dell'archivio.
- **`ArchivioSQLite(percorso)` ricostruisce il database di demo** se il file
  non c'e' — e costruirlo vuol dire cifrare con scrypt dieci password. La
  suite ci passava 33 secondi su 46 senza che nessun singolo test sembrasse
  lento: erano 67 ricostruzioni dello stesso database. Le fixture
  `modello_demo`/`db_demo`/`archivio_demo` in `tests/conftest.py` lo
  costruiscono una volta e ne copiano il file (0,08 ms). **Non tornare a
  costruirlo dentro un test**: i soli tre che devono farlo sono quelli che
  provano la costruzione, in `test_data.py`.
- **Gli hash delle password non registrano con quali parametri scrypt sono
  nati.** `verifica_password` ri-deriva coi costi correnti: cambiare
  `COSTO_N` invaliderebbe in silenzio ogni password gia' salvata. Non e' un
  problema oggi, lo diventa il giorno in cui si vorra' alzare il costo.
- **Cambiando modulo si poteva schierare due volte lo stesso giocatore.**
  La tendina rioffriva il giocatore gia' scelto altrove. Trovato **nel
  browser**, non dai test: le combinazioni di tendine che si influenzano a
  vicenda non si coprono a tavolino. Provare le pagine davvero, non solo le
  funzioni.
- **Uno script `python3 - <<PY` che verifica in fondo perde tutte le
  modifiche fatte prima**, se l'assert scatta. Applicare una modifica per
  script, oppure verificare prima di scrivere.
- **Il container si ricicla.** Due volte in una sessione
  `/home/user/fantacalcio-nuovo` e' sparito. La cura e' ri-clonare da GitHub
  e reinstallare le dipendenze, **non** riscrivere i file a memoria: quello
  che non e' stato spinto e' perso, e ricostruirlo a occhio introduce
  differenze invisibili.

## I documenti del progetto

**In che ordine leggerli, aprendo una sessione:** `CLAUDE.md` lo carica
Claude Code da solo, e rimanda qui; questo file dice a che punto siamo;
`PROGETTO.md` spiega il perche' di ogni scelta. Gli altri si aprono quando
servono.

| File | A cosa serve |
|---|---|
| `PROGETTO.md` | Tutto il progetto: decisioni, regole, architettura, cosa manca |
| `MEMORIA.md` | Questo: stato corrente e trappole gia' pagate |
| `CLAUDE.md` | Le regole per chi scrive codice |
| `COLLABORARE.md` | Come entrare nel progetto, per chi arriva |
| `README.md` | Come si usa il sito, schermata per schermata |
| `PUNTI_APERTI.md` | Le ambiguita' del regolamento da sciogliere |

Il documento Word per chi entra si rigenera con
`node scripts/genera_doc_collaboratore.js`: stesso contenuto di
`COLLABORARE.md`, in un formato che si gira a chi su GitHub non e' ancora
entrato. Se cambia uno, cambia l'altro.

## Come si lavora

- Repository: **`Tiri6/fantacalcio-nuovo`** (privato). Il progetto e' alla
  radice: la migrazione da `virtual-nutritionist` e' fatta, conservando i
  commit con `git subtree split`.
- **Aprire la sessione su questo repository**, non su `virtual-nutritionist`.
  Fino al 25 settembre 2026 si e' lavorato da una sessione nata su
  `virtual-nutritionist` con `fantacalcio-nuovo` aggiunto come seconda
  fonte: funzionava, ma l'app etichettava tutto col nome sbagliato e il ramo
  di destinazione indicato puntava al repository sbagliato. Il repository si
  sceglie creando la sessione e non si cambia dopo.
- Un branch per ogni lavoro, mai due sessioni Claude sullo stesso branch.
- Prima di ogni push: `.venv/bin/pytest` e `.venv/bin/ruff check .` devono
  passare puliti. Sono **1088 test in una decina di secondi**: se ci mettono
  una quarantina di secondi, qualcuno e' tornato a ricostruire il database di
  demo dentro i test (vedi le trappole).
- **Le pagine si provano nel browser**, non solo con i test: i difetti
  peggiori di questo progetto — doppioni nelle tendine, un'ala mandata in
  porta, un limite di rosa inventato — li ha trovati il browser, non la
  suite. Chromium e' gia' nell'immagine, il pacchetto no:
  `pip install playwright` e poi `executable_path=` su
  `/opt/pw-browsers/chromium-*/chrome-linux/chrome` (**non** lanciare
  `playwright install`). Si entra con `marco` / `fantanuovo26`, e i campi si
  cercano dentro `[data-testid='stForm']`, perche' fuori ce ne sono cinque
  con la stessa etichetta.
- Le regole del progetto stanno in `CLAUDE.md`: leggile prima di toccare il
  codice.

## Attenzione

Il repository e' privato, ma restano fuori comunque: il PDF del regolamento,
il database con i dati veri e ogni credenziale. `.streamlit/secrets.toml` e'
in `.gitignore`.
