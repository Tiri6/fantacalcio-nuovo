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

**Ultimo aggiornamento:** 21 agosto 2026 — leghe multiple con codice d'invito, registrazione autonoma, creazione squadra, tema grafico.

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

## Cosa manca (in ordine di utilita')

1. **Assegnazioni, contratti e ingaggi**: il listone e' caricato (509 giocatori
   con ruoli Mantra e quotazioni) ma non dice chi appartiene a quale squadra,
   con quanti anni e con quale ingaggio. Gli ingaggi vanno da Capology
   (art. 4). Finche' mancano, Salary Cap e Floor sono a zero.
2. **Data di nascita e nazionalita'**: senza, lo status Under 21 non si puo'
   determinare e l'espansione rosa non si applica.
3. **Svincoli registrati**: oggi il Dead Money si calcola ma non si scrive.
   Serve un flusso come quello degli scambi.
4. **Reimpostare le password** dall'interfaccia. Registrazione e ingresso in
   lega ora sono autonomi, ma chi dimentica la password resta fuori: serve che
   il presidente possa azzerarla.
5. **Registro dei lodi**: la tabella c'e' nello schema, manca la pagina.
6. **Tabellone del draft** da proiettare durante l'asta.

## In sospeso, con l'innesco

Cose decise ma non ancora eseguibili: manca un dato o un permesso. Quando
l'innesco scatta, si riprende da qui senza ricostruire il contesto.

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

## I documenti del progetto

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
- Un branch per ogni lavoro, mai due sessioni Claude sullo stesso branch.
- Prima di ogni push: `.venv/bin/pytest` e `.venv/bin/ruff check .` devono
  passare puliti.
- Le regole del progetto stanno in `CLAUDE.md`: leggile prima di toccare il
  codice.

## Attenzione

Il repository e' privato, ma restano fuori comunque: il PDF del regolamento,
il database con i dati veri e ogni credenziale. `.streamlit/secrets.toml` e'
in `.gitignore`.
