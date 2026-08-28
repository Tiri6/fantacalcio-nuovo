# Collaborare a FantaCalcio NuoVo

Benvenuto. Questo documento si legge una volta sola: dice cosa devi accettare,
come si modifica il progetto e cosa non fare mai.

**Cos'e':** il gestionale della nostra lega di fantacalcio manageriale.
Contratti, monte anni, Salary Cap, budget, draft, scambi e competizioni stanno
qui. Il gioco vero e proprio — voti, formazioni, risultati — resta su Leghe
Fantacalcio: questo sito non lo sostituisce, gestisce tutto il resto.

**Com'e' fatto:** Python + Streamlit per l'interfaccia, Supabase (PostgreSQL)
per i dati. Il codice sta su GitHub e il sito si aggiorna a ogni modifica
accettata.

---

## I tre livelli di accesso

Non ti serve tutto subito.

| Vuoi... | Ti serve | Come |
|---|---|---|
| **Usare il sito** come partecipante | solo l'indirizzo | apri il link e registrati |
| **Modificare il codice** | account GitHub + invito | passi 1 e 2 |
| **Gestire il deploy** | lo stesso invito | passi 1 e 2 |

Il secondo e il terzo arrivano **insieme**: su Streamlit Community Cloud i
permessi dell'app non si impostano su Streamlit, li decide l'accesso in
scrittura alla repository. Un invito solo copre entrambi.

---

## 1. Accetta l'invito su GitHub

Marco ti aggiunge come collaboratore con permesso **Write**. Ti arriva una mail
da GitHub, oppure trovi l'invito su
[github.com/notifications](https://github.com/notifications).

Accettalo. Da quel momento vedi `Tiri6/fantacalcio-nuovo`: e' privata, quindi
prima dell'invito ti risponde 404 come se non esistesse.

> **Perche' Write e non Admin.** Write copre tutto il lavoro quotidiano: creare
> branch, pushare, aprire pull request, amministrare l'app su Streamlit. Admin
> servirebbe solo per cancellare la repository o renderla pubblica — e nella
> cronologia c'e' ancora una vecchia chiave Supabase, quindi pubblica non deve
> diventarlo.

## 2. Collega Streamlit

Vai su [share.streamlit.io](https://share.streamlit.io) e fai **Sign in with
GitHub**.

Quando GitHub ti chiede l'autorizzazione, **concedi anche l'accesso alle
repository private**. Se salti quel permesso Streamlit non vede il progetto e
risponde *«This repository does not exist»*: un messaggio bugiardo, la
repository esiste ed e' lui a non vederla.

Fatto questo, nella dashboard compare l'app. Non devi ripubblicarla: e' gia'
online, tu ne diventi amministratore.

---

## 3. Il ciclo di lavoro

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
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

.venv/bin/pytest              # devono passare tutti, in una decina di secondi
.venv/bin/streamlit run app.py
```

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
unisce; un paio di minuti dopo il sito e' aggiornato. Se lavorate entrambi
direttamente su `main` vi pestate i piedi.

---

## Le sei regole

1. **Mai una chiave dentro un file pubblicato.** Le credenziali di Supabase
   vanno solo nei secret di Streamlit, o nel file locale
   `.streamlit/secrets.toml` che git ignora. Il file `secrets.toml.example` e'
   un modello e finisce su GitHub: contiene segnaposto, non toccarlo. Un test
   fallisce apposta se ci finisce una chiave vera — se si accende, non
   aggirarlo: ha ragione lui.

2. **Nessun numero del regolamento sparso nel codice.** Monte anni 66, Salary
   Cap 100M, rosa 30–33: stanno tutti in `ParametriLega` e solo li'. La lega
   cambia le regole per votazione, e devono restare modificabili in un punto
   solo.

3. **La logica non importa Streamlit.** Solo `ui.py`, `schermate.py` e i file in
   `viste/`. E' quello che tiene i test veloci e la logica riutilizzabile.

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

**Nelle cache di Streamlit vanno solo DataFrame**, mai oggetti di dominio. Un
oggetto in cache conserva la forma che aveva quando ci e' entrato, e dopo un
aggiornamento rompe l'app. C'e' un test che lo verifica staticamente.

**Se il sito da' un errore strano dopo un aggiornamento**, prima di cercare il
bug prova a riavviarlo: ⋮ → *Reboot app*. Streamlit ricarica `app.py` e le
viste, ma non i moduli gia' importati, e per un po' gira codice misto.

---

## Se qualcosa va storto

| Sintomo | Cos'e' successo |
|---|---|
| GitHub risponde **404** sulla repository | Invito non ancora accettato |
| *«This repository does not exist»* su Streamlit | Manca il permesso sulle repository private (passo 2) |
| *«Il database non ha le tabelle»* | Su Supabase non e' stato eseguito `db/schema.sql` |
| L'app non scrive, o il login non va | Nei secret c'e' la chiave `anon` invece della `service_role` |
| *«Il sito sta ancora usando il codice precedente»* | Riavvia l'app: ⋮ → Reboot app |
| `git push` rifiutato | Qualcuno ha pubblicato prima di te: `git pull --rebase` |
| La sidebar dice **Modalita' demo** | Nessuna credenziale. In locale e' normale |

---

Il resto sta nella repository, e si legge quando serve:

- **`PROGETTO.md`** — tutto il progetto: decisioni, regole, architettura, cosa manca
- **`CLAUDE.md`** — le regole per chi scrive codice, e dove mettere le mani
- **`MEMORIA.md`** — a che punto siamo e le trappole gia' pagate
- **`README.md`** — come si usa il sito, schermata per schermata
- **`PUNTI_APERTI.md`** — le ambiguita' del regolamento ancora da sciogliere
