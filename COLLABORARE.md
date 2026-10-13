# Collaborare a FantaCalcio NuoVo

Benvenuto. Questo documento si legge una volta sola: dice cosa devi accettare,
come si modifica il progetto e cosa non fare mai.

**Cos'e':** il gestionale della nostra lega di fantacalcio manageriale.
Contratti, monte anni, Salary Cap, budget, draft, scambi e competizioni stanno
qui. Il gioco vero e proprio — voti, formazioni, risultati — resta su Leghe
Fantacalcio: questo sito non lo sostituisce, gestisce tutto il resto.

**Com'e' fatto:** Python per le regole e l'API (FastAPI), React per le pagine,
Supabase (PostgreSQL) per i dati. E' **un servizio solo**: la stessa app serve
le pagine e l'API che le alimenta. Il codice sta su GitHub, il sito gira su
Fly.io.

---

## I tre livelli di accesso

Non ti serve tutto subito.

| Vuoi... | Ti serve | Come |
|---|---|---|
| **Usare il sito** come partecipante | solo l'indirizzo | apri il link e registrati |
| **Modificare il codice** | account GitHub + invito | passo 1 |
| **Pubblicare** | un account Fly con accesso all'app | chiedi a Marco |

Pubblicare e' un passo a parte: il deploy si lancia da riga di comando
(`fly deploy`), non lo fa GitHub da solo.

---

## 1. Accetta l'invito su GitHub

Marco ti aggiunge come collaboratore con permesso **Write**. Ti arriva una mail
da GitHub, oppure trovi l'invito su
[github.com/notifications](https://github.com/notifications).

Accettalo. Da quel momento vedi `Tiri6/fantacalcio-nuovo`: e' privata, quindi
prima dell'invito ti risponde 404 come se non esistesse.

> **Perche' Write e non Admin.** Write copre tutto il lavoro quotidiano:
> creare branch, pushare, aprire pull request. Admin servirebbe solo per
> cancellare la repository o renderla pubblica — e nella cronologia c'e'
> ancora una vecchia chiave Supabase, quindi pubblica non deve diventarlo.

---

## 2. Il ciclo di lavoro

### Con Claude — il modo in cui lavoriamo

Apri Claude Code sulla repository e di' direttamente cosa vuoi fare. Nessun
preambolo: `CLAUDE.md` si carica da solo e rimanda a `MEMORIA.md`, che dice a
che punto siamo e quali trappole sono gia' costate tempo a qualcun altro.

Per capire il progetto per intero c'e' **`PROGETTO.md`**: decisioni prese,
regole applicate, com'e' fatto dentro e cosa manca.

A fine sessione, prima di pubblicare, lancia `/memoria`: aggiorna la memoria
per chi viene dopo. E' l'unica cosa che tiene allineate due persone che non
lavorano nello stesso momento.

### A mano

```bash
git clone https://github.com/Tiri6/fantacalcio-nuovo.git
cd fantacalcio-nuovo

python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cd web && npm ci && npm run build && cd ..

.venv/bin/pytest              # devono passare tutti
.venv/bin/python -m uvicorn api.main:app --reload
```

Poi `http://127.0.0.1:8000`. Chi lavora sulle pagine puo' tenere Vite a parte
(`cd web && npm run dev`), che ricarica a ogni salvataggio.

Senza credenziali parte in **modalita' demo**: dati inventati, database locale,
nessun rischio di toccare quelli veri. E' il modo giusto per provare.

### In ogni caso: un branch a testa

```bash
git pull                         # sempre, prima di iniziare
git checkout -b luca/svincoli    # un branch per ogni cosa che fai
# ... lavori ...
.venv/bin/pytest && .venv/bin/ruff check .
git push -u origin luca/svincoli
```

Poi su GitHub apri una **pull request** verso `main`. Marco la guarda e la
unisce, e poi lancia `fly deploy`. Se lavorate entrambi direttamente su `main`
vi pestate i piedi.

---

## Le sei regole

1. **Mai una chiave dentro un file pubblicato.** Le credenziali di Supabase
   si passano come variabili d'ambiente: `fly secrets set` in produzione,
   `export` nella shell in locale. Un test fallisce apposta se una chiave vera
   finisce in un file versionato — se si accende, non aggirarlo: ha ragione lui.

2. **Nessun numero del regolamento sparso nel codice.** Monte anni 66, Salary
   Cap 100M, rosa 30–33: stanno tutti in `ParametriLega` e solo li'. La lega
   cambia le regole per votazione, e devono restare modificabili in un punto
   solo.

3. **La logica non conosce il web.** `fantacalcio/` non importa FastAPI e non
   sa che esiste un browser: traducono le rotte in `api/`. E' quello che tiene
   i test veloci — ed e' il motivo per cui rifare il sito da zero, da Streamlit
   a React, non ha toccato una riga di regole.

4. **Prima di pubblicare, `pytest` e `ruff check .` devono passare.** Sono la
   rete che permette a due persone di toccare lo stesso codice senza rompersi a
   vicenda.

5. **Mai due sessioni Claude sullo stesso branch nello stesso momento.**

6. **Fuori dalla repository restano** il PDF del regolamento, il database con i
   dati veri e ogni credenziale. Anche se la repository e' privata.

---

## Tre cose che ti risparmiano un pomeriggio

**Provare in locale non basta.** SQLite (la demo) e PostgREST (Supabase)
rispondono diversamente quando una tabella e' vuota: il primo da' le colonne,
il secondo no. Del codice che funziona in locale puo' rompersi in produzione.
C'e' un finto backend apposta in `tests/test_backend_vuoto.py`: usalo.

**I tipi del sito si controllano con `npm run build`**, non con
`npx tsc --noEmit`: lo script fa `tsc -b`, che usa i tsconfig dell'app ed e'
piu' severo. Un array che nasce vuoto senza tipo passa il secondo e fa
fallire il primo — su `main`, dopo il merge.

**Se il sito locale da' un errore strano**, controlla di averlo riavviato: una
rotta aggiunta adesso non esiste finche' uvicorn non riparte, e i test passano
lo stesso perche' importano l'app da zero.

---

## Se qualcosa va storto

| Sintomo | Cos'e' successo |
|---|---|
| GitHub risponde **404** sulla repository | Invito non ancora accettato |
| Una rotta nuova risponde **405** nel browser ma i test passano | Il server locale non e' stato riavviato |
| *«Il database non ha le tabelle»* | Su Supabase non e' stato eseguito `db/schema.sql` |
| L'app non scrive, o il login non va | Nei secret c'e' la chiave `anon` invece della `service_role` |
| Il sito pubblicato e' indietro | Il deploy si lancia a mano: `git pull && fly deploy` |
| `git push` rifiutato | Qualcuno ha pubblicato prima di te: `git pull --rebase` |
| `/api/salute` dice **demo (SQLite)** | Nessuna credenziale Supabase. In locale e' normale |

---

Il resto sta nella repository, e si legge quando serve:

- **`PROGETTO.md`** — tutto il progetto: decisioni, regole, architettura, cosa manca
- **`CLAUDE.md`** — le regole per chi scrive codice, e dove mettere le mani
- **`MEMORIA.md`** — a che punto siamo e le trappole gia' pagate
- **`README.md`** — come si usa il sito, schermata per schermata
- **`PUNTI_APERTI.md`** — le ambiguita' del regolamento ancora da sciogliere
