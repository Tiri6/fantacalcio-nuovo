# Fantacalcio della Lega

Sito della lega: classifica, calendario con i tabellini di ogni giornata, rose
delle squadre e statistiche. Stack identico a quello che usi gia' sul progetto
nutrizionista — **Streamlit + Supabase + Plotly** — cosi' non devi imparare
niente di nuovo.

Il progetto parte **senza credenziali**: se non trova Supabase genera una lega
di demo in SQLite. Questo e' voluto, ed e' il pezzo che rende comodo lavorare
dal browser: in una sessione cloud puoi aprire, modificare e vedere il sito
funzionante senza avere in mano nessun segreto.

---

## Avvio rapido

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/streamlit run app.py
```

Si apre su <http://localhost:8501> con 8 squadre, 200 giocatori e 6 giornate
gia' giocate. I dati di demo sono generati con un seme fisso, quindi sono
identici a ogni riavvio.

Test e lint:

```bash
.venv/bin/pytest        # 54 test
.venv/bin/ruff check .
```

---

## Com'e' fatto

```
app.py                    router: st.navigation, monta le viste
viste/                    una schermata per file (home, classifica, ...)
fantacalcio/              logica, senza Streamlit dentro (tranne ui.py)
  scoring.py              fantavoto, bonus/malus, sostituzioni, punti -> gol
  standings.py            calendario round robin e classifica
  data.py                 accesso ai dati: Supabase o SQLite demo
  vista.py                dai dati grezzi alle tabelle a schermo
  ui.py                   helper Streamlit (cache, intestazioni, sidebar)
  demo_data.py            genera la lega di demo
  config.py               legge i secret, sceglie il backend
db/schema.sql             schema Postgres da incollare in Supabase
tests/                    test di scoring, classifica, dati e viste
.claude/hooks/            hook di avvio per le sessioni Claude Code sul web
```

La regola che tiene insieme tutto: **la logica non sa che esiste Streamlit**.
`scoring.py` e `standings.py` sono Python puro, quindi sono testabili senza
avviare l'app — ed e' il motivo per cui i test girano in mezzo secondo.

### Le regole della lega sono configurabili

Bonus, malus, soglia del primo gol e modificatore difesa stanno tutti in
`RegoleLega` (`fantacalcio/scoring.py`). I default sono quelli classici:

| Voce | Default |
|---|---|
| Gol segnato | +3 |
| Assist | +1 |
| Rigore parato | +3 / sbagliato −3 |
| Gol subito (portiere) | −1 |
| Autogol | −2 |
| Ammonizione / espulsione | −0.5 / −1 |
| Primo gol a | 66 punti, poi uno ogni 6 |
| Modificatore difesa | disattivato |

Se la tua lega gioca diverso, si cambia in un punto solo.

---

## Passare ai dati veri (Supabase)

1. Crea il progetto su [supabase.com](https://supabase.com) (piano free).
2. SQL Editor → incolla `db/schema.sql` → Run. Crea tabelle, indici e le
   policy di lettura pubblica.
3. Settings → API: copia URL e chiave `anon`.
4. `cp .streamlit/secrets.toml.example .streamlit/secrets.toml` e compila.

Al riavvio la sidebar passa da "Modalita' demo" a "Dati live da Supabase":
nessuna modifica al codice, `config.py` sceglie da solo il backend.

> La chiave `anon` legge soltanto (la RLS in `schema.sql` blocca le scritture).
> La `service_role` bypassa la RLS: non metterla mai nel sito pubblico.
> `.streamlit/secrets.toml` e' in `.gitignore` — non finira' mai su GitHub.

---

## Pubblicare il sito

[Streamlit Community Cloud](https://share.streamlit.io) e' gratis e si collega
direttamente a GitHub: scegli il repo, come main file `app.py`, e incolla i
secret in Settings → Secrets. Ogni push sul branch collegato ridispiega da solo.

---

## Come lavorare: dal lavoro e da casa

Il punto della richiesta iniziale. Alcune cose richiedono permessi che una
sessione cloud non ha, altre no. Ecco la divisione reale.

### Dal lavoro, via Claude web — tutto il codice

Una sessione cloud clona il repo, ha Python e la rete, e all'avvio esegue
`.claude/hooks/session-start.sh`, che crea il virtualenv e installa tutto.
Quindi da li' puoi fare, senza installare niente sul PC del lavoro:

- scrivere e modificare pagine, logica, query;
- far girare test e lint;
- avviare l'app e guardarla in funzione;
- commit e push sul branch;
- aprire e rivedere pull request.

Nessun segreto passa da qui: le sessioni cloud lavorano in modalita' demo.

### Da casa — solo le cose con permessi

Queste operazioni richiedono il tuo account con permessi pieni, e in questa
sessione infatti sono fallite con un 403:

- **creare il repository** su GitHub (vedi sotto);
- **creare il progetto Supabase** e lanciare `db/schema.sql`;
- **inserire i secret** su Streamlit Cloud e collegare il repo;
- **caricare i dati veri** della lega (rose, voti di giornata).

Sono tutte operazioni una tantum, tranne il caricamento dei voti.

### Perche' funziona

Il segreto e' che l'app parte senza credenziali. Se il codice pretendesse
Supabase per avviarsi, ogni sessione cloud sarebbe cieca e dovresti lavorare
solo da casa. Cosi' invece la separazione e' netta: **il codice sta nel cloud,
i segreti stanno a casa tua.**

---

## Spostare il progetto nel suo repository

Adesso questa cartella vive dentro il repo `virtual-nutritionist`, perche' la
sessione cloud non aveva il permesso di crearne uno nuovo. Per darle il repo che
merita, da casa:

1. Crea su GitHub un repo vuoto `fantacalcio-lega` (senza README).
2. Poi:

```bash
git clone https://github.com/Tiri6/virtual-nutritionist.git /tmp/vn
cd /tmp/vn && git checkout claude/fantacalcio-github-setup-j3e4ly

cp -r fantacalcio /percorso/dove/vuoi/fantacalcio-lega
cd /percorso/dove/vuoi/fantacalcio-lega

git init -b main
git add .
git commit -m "Primo commit: sito della lega di fantacalcio"
git remote add origin https://github.com/Tiri6/fantacalcio-lega.git
git push -u origin main
```

Nel nuovo repo `.claude/`, `.github/` e `.gitignore` finiscono alla radice, dove
devono stare: hook di avvio e CI funzionano subito, senza modifiche.

---

## Cosa manca (prossimi passi)

Il sito oggi **legge**. Per gestire la lega servono le scritture:

- inserimento voti di giornata (upload CSV dai voti ufficiali);
- schieramento formazioni con scadenza;
- area admin protetta da password per correggere i risultati;
- asta e mercato di riparazione;
- storico delle stagioni passate.
