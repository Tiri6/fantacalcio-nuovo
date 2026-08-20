# FantaCalcio NuoVo — il gestionale della lega

Il gioco (voti, formazioni, risultati) si svolge su **Leghe Fantacalcio**.
Questo progetto governa tutto quello che la piattaforma non sa fare, ed e' cio'
che rende "gestionale" la vostra lega:

- contratti pluriennali e **monte anni** (66 anni da distribuire);
- **Salary Cap** (100M) e **Salary Floor** (80M) su ingaggi reali da Capology;
- **Dead Money** da svincolo (Lodo Origi);
- **regola "1/3"** sui contratti in scadenza;
- **espansione Under 21** che allarga la rosa;
- **draft con lottery** a due fasce e ordine di chiamata variabile per round;
- **scambi** validati contro i lodi Bono, Corti e Longoni.

Base: regolamento **V2.1 di Agosto 2026**, versione post-redline.

> I punti del regolamento che ho dovuto interpretare sono elencati in
> [PUNTI_APERTI.md](PUNTI_APERTI.md), con l'ipotesi che il codice applica oggi.
> Le fasce di gol sono chiuse: **primo gol a 66**, poi uno ogni 6.

---

## Avvio rapido

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/streamlit run app.py
```

Parte **senza credenziali**: se non trova Supabase genera una lega di demo in
SQLite, con 10 squadre, rose contrattualizzate e 11 giornate disputate. Tutte
le rose della demo sono conformi al regolamento, quindi sono un banco di prova
valido per le regole.

```bash
.venv/bin/pytest        # 143 test
.venv/bin/ruff check .
```

---

## Le schermate

| Pagina | A cosa serve |
|---|---|
| **Cruscotto** | Chi e' in regola e chi no: rosa, monte anni, annuali, cap e floor di tutte e 10 le squadre in una tabella. |
| **Rose e contratti** | La rosa di una squadra con anni residui, ingaggi, status U21 e quanto costerebbe tagliare ciascun giocatore. |
| **Mercato** | Simulatore di scambi validato contro i lodi, e calcolo del Dead Money prima di svincolare. |
| **Identita' squadre** | Presidente, motto, stadio, colori sociali, maglia e logo. La maglia si disegna dai colori: nessuno resta senza. |
| **Importa dati** | Il CSV del draft e i risultati di giornata, con anteprima ed errori riga per riga prima di scrivere. |
| **Draft** | Draft Lottery riproducibile, ordine di chiamata round per round, probabilita' delle pick, draft list delle scadenze. |
| **Campionato** | Classifica e risultati importati da Leghe: servono a determinare l'ordine del draft. |
| **Regolamento** | I valori che il gestionale applica davvero, articolo per articolo. |

---

## Com'e' fatto

```
app.py                    router: st.navigation, monta le viste
viste/                    una schermata per file
fantacalcio/
  regole.py               TUTTI i numeri del regolamento (ParametriLega)
  modelli.py              Giocatore, Contratto, Rosa, Dead Money
  identita.py             colori sociali, maglia disegnata in SVG, logo
  conformita.py           verifica una rosa -> elenco di violazioni
  draft.py                Draft Lottery e ordine di chiamata (art. 3)
  mercato.py              finestre, svincoli, scambi e lodi (art. 5-8)
  importazione.py         lettura e validazione dei CSV
  standings.py            calendario e classifica
  data.py                 accesso ai dati: Supabase o SQLite demo
  vista.py                dai dati grezzi alle tabelle a schermo
  ui.py                   helper Streamlit (l'unico modulo che importa st)
  demo_data.py            genera la lega di demo
db/schema.sql             schema Postgres da incollare in Supabase
tests/                    143 test sulle regole, i dati e le viste
```

Due regole tengono insieme il progetto:

**Il regolamento sta in un posto solo.** Ogni soglia — 66 anni, 100M, 33
giocatori, 3 portieri, 50% di Dead Money — e' un campo di `ParametriLega`.
Quando la lega vota un lodo si cambia quel valore, non la logica. E' anche il
motivo per cui la pagina Regolamento puo' stampare i parametri veri invece di
una copia scritta a mano che prima o poi diverge.

**La logica non conosce Streamlit.** `regole`, `modelli`, `conformita`,
`draft`, `mercato` e `vista` sono Python puro. I 143 test girano in poco piu'
di un secondo senza avviare nulla — ed e' il motivo per cui questa parte
sopravvivrebbe intatta a un cambio di tecnologia del sito.

### La verifica non e' un si'/no

`verifica_rosa()` restituisce sempre **l'elenco completo** delle violazioni,
ciascuna con l'articolo, la gravita', il valore attuale e il limite. A un
fantallenatore non serve sapere che la rosa e' irregolare: serve sapere che gli
mancano 2 contratti annuali e che sfora il cap di 1,4M.

Le stesse regole non sono vincolanti sempre allo stesso modo, e il codice lo
rispecchia con il parametro `Momento`:

| | Asta di Settembre / riparazione | Stagione in corso |
|---|---|---|
| Salary Cap | blocca | avviso (art. 8b: si sana prima dell'asta) |
| Salary Floor | blocca | non si verifica |
| Rosa minima, regola 1/3 | blocca | avviso |
| Rosa massima, portieri, monte anni | blocca | blocca |

---

## Caricare i dati dopo il draft

Il draft si fa di persona e poi si carica il risultato dalla pagina **Importa
dati**. Il CSV vuole una riga per giocatore:

```csv
squadra;giocatore;club;ruoli;ingaggio;anni;nazionalita;data_nascita
Tiri Team;Rossi Marco;Juventus;Dc;2.500.000;3;Italia;17/04/2001
Padel United;Silva Joao;Napoli;W/T;4,2M;2;Brasile;30/06/1999
```

Il lettore e' volutamente tollerante, perche' i fogli veri non arrivano mai
puliti:

- **intestazioni**: riconosce i sinonimi piu' comuni (`Fantasquadra`,
  `Calciatore`, `Stipendio`, `Durata`, `RM`, `Nazionalità`...), senza badare a
  maiuscole e accenti;
- **separatore**: `;` o `,`, riconosciuto da solo;
- **importi**: `3.500.000`, `1500000`, `3,5M`, `4 mln`, `€ 2.100.000`;
- **date**: `17/04/2001`, `2001-04-17`, `17-04-2001`;
- **ruoli multipli**: separali con `/` — per esempio `Dc/Dd`. Non usare `;`
  dentro la cella se il CSV e' separato da `;`: e' l'errore piu' comune, e il
  programma lo riconosce e te lo dice.

Le colonne obbligatorie sono `squadra`, `giocatore`, `ruoli`, `ingaggio` e
`anni`. Le altre migliorano i controlli: senza `data_nascita`, per esempio, non
si puo' stabilire chi e' Under 21.

**Niente viene scritto finche' non confermi.** Prima vedi gli errori riga per
riga, l'anteprima delle rose e — la parte utile — la verifica di conformita':
se il draft ha lasciato qualcuno oltre il Salary Cap o sotto i 30 giocatori, lo
scopri prima di importare, non dopo.

Stessa cosa per i **risultati di giornata**: carichi giornata, squadre e punti,
e i gol vengono calcolati dalle fasce della lega.

---

## Passare ai dati veri (Supabase)

1. Crea il progetto su [supabase.com](https://supabase.com) (piano free).
2. SQL Editor → incolla `db/schema.sql` → Run.
3. Settings → API: copia URL e chiave `anon`.
4. `cp .streamlit/secrets.toml.example .streamlit/secrets.toml` e compila.

Al riavvio la sidebar passa da "Modalita' demo" a "Dati live da Supabase":
`config.py` sceglie da solo il backend, il codice non cambia.

> La chiave `anon` legge soltanto (la RLS in `schema.sql` blocca le scritture).
> `.streamlit/secrets.toml` e' in `.gitignore` e non finira' mai su GitHub.

---

## Cosa manca per essere "la piattaforma vera"

Il gestionale ora **legge, valida e scrive** (identita' squadre e import CSV).
Perche' i tuoi amici lo usino davvero manca, nell'ordine in cui lo farei:

1. **Login dei 10 partecipanti** e permessi: ognuno vede tutto, modifica solo
   la propria squadra, il presidente ratifica.
2. **Proposta e ratifica degli scambi** dentro il sito, con il vincolo delle
   24 ore e lo storico di chi ha proposto cosa. Oggi lo scambio si simula ma
   non si registra.
3. **Svincoli registrati**, che scrivano davvero il Dead Money invece di
   limitarsi a calcolarlo.
4. **Registro dei lodi**, collegato all'articolo che modificano.
5. **Tabellone del draft** da proiettare durante l'asta al Centro Padel.

Il punto 1 e' anche il momento in cui va deciso se restare su Streamlit: per
dieci persone che consultano e propongono scambi puo' bastare, ma per un'asta
in tempo reale e per l'uso quotidiano da telefono un frontend vero renderebbe
molto meglio. La logica di regole non andrebbe comunque riscritta.

---

## Spostare il progetto nel suo repository

Questa cartella vive dentro il repo `virtual-nutritionist` perche' la sessione
cloud non aveva il permesso di crearne uno nuovo. Da casa:

1. Crea su GitHub un repo vuoto `fantacalcio-nuovo` (senza README).
2. Poi:

```bash
git clone https://github.com/Tiri6/virtual-nutritionist.git /tmp/vn
cd /tmp/vn && git checkout claude/fantacalcio-github-setup-j3e4ly

cp -r fantacalcio /percorso/dove/vuoi/fantacalcio-nuovo
cd /percorso/dove/vuoi/fantacalcio-nuovo

git init -b main
git add .
git commit -m "Primo commit: gestionale FantaCalcio NuoVo"
git remote add origin https://github.com/Tiri6/fantacalcio-nuovo.git
git push -u origin main
```

Nel nuovo repo `.claude/`, `.github/` e `.gitignore` finiscono alla radice,
dove devono stare: hook di avvio e CI funzionano subito, senza modifiche.
