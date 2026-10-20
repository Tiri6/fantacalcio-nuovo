# Memoria del progetto

Stato corrente di FantaCalcio NuoVo: **chi apre una sessione nuova legge questo file per primo** (`CLAUDE.md`
rimanda qui, `PROGETTO.md` spiega il perche' delle scelte). Si aggiorna con `/memoria` prima del push. E' una
memoria di lavoro, non un diario: **sotto le 120 righe**, il vecchio si taglia (resta in `git log -p MEMORIA.md`).
La chat di progetto su claude.ai lo legge dall'URL raw del repository: una decisione presa in chat entra nella
tabella qui sotto.

## In una riga

Gestionale della lega (10 squadre, Mantra, regolamento V3): contratti, monte anni, Cap/Floor, draft, scambi,
calendario, risultati. Il gioco vero (voti, formazioni) resta su Leghe Fantacalcio: il sito ne importa i file.

**Ultimo aggiornamento:** 20 ottobre 2026 — la data di nascita ha una maschera `gg/mm/aaaa` per il tastierino di
iOS/Android (ramo `campo-data-nascita`, da unire). Dal 14 ottobre il sito importa calendario e tabellino di Leghe e
il calcolo della giornata torna su 9 squadre su 10. Il 18 e' emerso che **il repository e' pubblico** con una
vecchia chiave a pieni poteri nella cronologia: *Cosa manca*, punto 1.

## Decisioni prese (non riaprirle senza motivo)

| Decisione | Quando | Perche' |
|---|---|---|
| Stack **React + FastAPI + Supabase**, un servizio solo su **Fly.io**; Streamlit dismesso (app cancellata) | 13 ott | Draft Room in tempo reale e uso da telefono. La logica era Python puro e non si e' toccata |
| Il **draft si fa offline (CSV) e anche nella Draft Room**, che si aggiorna interrogando ogni 2,5 s | 12 ott | Per dieci persone il polling costa meno da mantenere di un canale aperto |
| Gli **anni di contratto si correggono solo dopo la draft room**, sui giocatori presi li', fino al calcio d'inizio della giornata dopo | 12 ott | Dettata dal presidente. Il calcio d'inizio e' l'istante del blocco formazioni |
| **Regole di gioco**: primo gol a 66 e uno ogni 6; modificatore difesa mezzo punto ogni quarto di media da 6, con l'esterno che conta come difensore; moduli Mantra **undici**, difesa a cinque esclusa | 14 ott | Dettate dalla lega; il modificatore e' verificato su tabellini veri (9 casi su 10). Dettagli in `PUNTI_APERTI.md` |
| **Anno zero**: il calendario si importa dall'xlsx di Leghe una volta e le squadre gia' create non si toccano. Dall'anno prossimo le squadre stanno nella lega prima del calendario, che si genera da data d'inizio e di fine | 14 ott | Detto dal presidente |
| **Coppa e F1 Rush le genera il presidente dal sito** quando le 10 squadre sono dentro. **Rose e anni**: il primo anno a mano via Excel, poi automatici dopo la Draft Room | 14 ott | Detto dal presidente: la coppa non e' ancora partita |
| La giornata entra col **tabellino di Leghe** che il presidente carica a ogni giornata | 14 ott | Richiesto dal presidente. Lo scraping non e' praticabile: il CDN di Leghe risponde 403 ai server |
| **Data di nascita con maschera**: solo cifre, barre automatiche, errore accanto al campo; il formato al server resta `gg/mm/aaaa` | 20 ott | Il tastierino numerico di iOS/Android non ha lo slash |
| **Impianto** (ago-set): registrazione autonoma e codice d'invito di 8 caratteri; inviti per email che *non spediscono*; opzioni di lega in JSON, modificabili solo dal creatore; sostituzioni Easy/Basic/Master; portiere mai adattato; formazione bloccata un minuto prima; chat sul regolamento da un dossier generato | 21 ago-24 set | Un server di posta per dieci persone non si giustifica; le opzioni cambiano ogni stagione; la chat non cita mai a memoria |

## Cosa c'e' (funziona e ha i test: 1822, due `xfail` che misurano il calcolo)

- **Base**: regole (monte anni 66, rosa 30-33, Cap 100M, Floor 80M), accesso con ruoli, lega con opzioni
  modificabili, scambi con ratifica, squadre, Lottery e Draft Room (il turno si ricava *contando le chiamate*),
  Under 21 al 31 agosto.
- **Importa dati**: listone, rose, risultati, **calendario ufficiale** (crea le squadre mancanti, senza presidente;
  chi entra col codice sceglie la sua) e **tabellino di giornata** (formazioni, voti, risultati della piattaforma).
- **Calcolo giornata**: 9 squadre su 10 col totale esatto sul tabellino vero (`tests/dati/`); sceglie le caselle,
  **cambia modulo**. Coppa e F1 Rush sono *viste calcolate*, non partite vere.
- **Altro**: `mantra.py` e' dato trascritto a mano (i test ne provano la *forma*); data di nascita in
  `web/src/data.ts` + `campoData.tsx` (eta' minima e massima solo al server; «Il mio profilo» la mostra soltanto);
  chat sul regolamento; diagnostica dello schema.

## Cosa manca (in ordine di utilita')

1. **Sicurezza** (report del 18 ott). Il repo e' **pubblico** e le prime commit hanno una chiave Supabase a pieni
   poteri: **ruotarla** (`fly secrets set SUPABASE_KEY=...`) e decidere se privatizzare, sapendo che la chat legge
   il file raw. **Il login non ha limite ai tentativi** (il contatore era di Streamlit). Mancano header di
   sicurezza, `/docs` spento e un backup documentato.
2. **Dati veri**: stipendi, nascite, nazionalita' (senza, Cap/Floor/U21 lavorano su zeri). Le `fasce_difesa` della
   lega vera hanno ancora i valori vecchi.
3. **Coppa e F1 Rush** generate dal sito, e **calendario da data d'inizio e fine** per l'anno prossimo.
4. **Calcolo 10 su 10**: caselle di 3-5-1-1, 4-3-3, 4-4-2, 4-3-2-1; un caso di modificatore; servono altre giornate
   di tabellino.
5. Svincoli registrati (il Dead Money si calcola, non si scrive); registro dei lodi; minimi italiani/U21 e scambi a
   stagione non imposti.
6. Pulizia: `render.yaml`, 22 branch remoti da verificare, nessun lockfile Python, listone con stipendi di fonti
   terze in `dati/` (ora pubblico).

## In sospeso, con l'innesco

- **Deploy**: dopo ogni merge `git pull` e `fly deploy` (Fly non ridispiega da solo). Da confermare l'ultimo, col
  fix dei moduli (PR #21).
- **Chat**: serve `ANTHROPIC_API_KEY` in `fly secrets`; mai provata con una chiave vera. Se sbaglia un numero, il
  difetto e' nel dossier.
- **Tabelle dei moduli**: innesco, lo schema ufficiale o altri tabellini. Il 3-4-2-1 e il 3-5-2 sono *dedotti* dai
  dati, non letti.
- **Leghe Fantacalcio** non e' raggiungibile dai container (403): export a mano; nel loro file `costo` e' gli
  **anni residui**.

## Punti aperti del regolamento

In `PUNTI_APERTI.md` (21 voci). Contano: la chiusura delle finestre di mercato, e il campionato (il calendario
ufficiale ha **27 giornate**: da riflettere nel punto 5).

## Trappole gia' pagate (non ripeterle)

- **Un default che cambia sta gia' scritto nelle leghe salvate.** `OpzioniLega` salva *tutte* le opzioni: il 14 ott
  `MODULI_MANTRA` e' passato da 16 a 11 e la lega vera e' diventata illeggibile (`carica_leghe` salta le righe che
  non legge: «non sei in nessuna lega»). Quando si tocca un default o un elenco, si scrive come si legge quello
  vecchio (`_deserializza`) e un test con la riga com'era.
- **Un motore coerente puo' essere sbagliato.** Solo un tabellino vero ha mostrato 9 squadre su 10 errate: caselle
  dedotte, un attaccante a zero, esterni fuori dalla media.
- **Cambiare ramo con modifiche non committate** e poi `git checkout ramo -- file` le cancella. Commit o stash
  prima; uno stash si ritrova con `git fsck --lost-found`.
- **Il presidente lancia i comandi dalla home**: `git` e `fly` cercano `.git` e `fly.toml` nella cartella corrente.
  Dare prima un `cd`, poi `git status`. In zsh un commento in riga non e' un commento.
- **Server locale**: non si accorge del codice nuovo (riavviare). `pkill -f` uccide la propria shell: il PID si
  prende con `ss -ltnp`. Due comandi Bash in parallelo con `cd` diversi si pestano la cartella.
- **`insert or replace` annulla un `unique`**: per scrivere in sola aggiunta c'e' `Archivio.aggiungi`. **scrypt nei
  test** costa piu' del resto: fixture `scrypt_da_test`.
- **SQLite e PostgREST rispondono diversamente**: tabella vuota senza colonne, colonna mancante, GRANT. Provare col
  finto backend di `test_backend_vuoto.py` e con la diagnostica. `create table if not exists` non aggiunge colonne:
  serve l'`alter table`.
- **Ricostruire una dataclass** perde i campi che non nomini. Un `except` largo che torna un valore vuoto nasconde
  i guasti. I dati inventati non mostrano i buchi (il ruolo `B` c'era solo nel listone vero).
- **Le regole di validazione vanno scritte accanto al campo**: se le scopre l'errore del server, sembra che il sito
  sia rotto. **Chi guida una squadra** lo dice `Utente.squadra_id`, mai il campo `presidente`.
- **Il demo si costruisce una volta** (fixture `db_demo`). **Il container si ricicla**: si ri-clona, non si
  riscrive a memoria.

## Come si lavora

- Repository `Tiri6/fantacalcio-nuovo`; un ramo per lavoro, mai due sessioni sullo stesso. Letture: `CLAUDE.md`
  (regole), `README.md`, `COLLABORARE.md`.
- Prima di ogni push: `.venv/bin/pytest` (~2 minuti), `.venv/bin/ruff check .` e `cd web && npm run build` (non
  `npx tsc --noEmit`: e' meno severo e lascia passare errori che rompono `main`).
- **Le pagine si provano nel browser**: i difetti peggiori li ha trovati lui, non i test. Playwright: `pip install
  playwright` e `executable_path` su `/opt/pw-browsers/chromium-*/chrome-linux/chrome` (mai `playwright install`).

## Attenzione

Il repository e' **pubblico**: chiunque legge file, cronologia e messaggi. Non ci vanno mai dati veri della lega
(nomi di squadre e utenti, email, stipendi), il PDF del regolamento, il database, credenziali o indizi per
trovarle. I segreti stanno in `fly secrets`; `test_segreti.py` cerca chiavi nei file versionati.
