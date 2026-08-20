---
description: Aggiorna MEMORIA.md con lo stato del progetto a fine sessione
---

Aggiorna `MEMORIA.md` perche' chi apre la prossima sessione — anche un'altra
persona — riprenda senza dover ricostruire il contesto.

Prima di scrivere:

1. Leggi `MEMORIA.md`, poi `git log --oneline -15` e `git status` per vedere
   cosa e' successo davvero in questa sessione.
2. Confronta con la sezione "Cosa manca": qualcosa e' stato completato?

Poi aggiorna, **modificando le sezioni esistenti invece di aggiungerne di
nuove**:

- **Ultimo aggiornamento**: data e una riga su cosa e' cambiato.
- **Decisioni prese**: aggiungi solo le decisioni che l'utente ha confermato
  esplicitamente, con il motivo. Non inventare decisioni non prese.
- **Cosa c'e'**: sposta qui cio' che ora funziona ed e' coperto da test.
- **Cosa manca**: togli il fatto, riordina per utilita' reale.
- **Trappole gia' pagate**: aggiungi ogni difetto che e' costato tempo a
  diagnosticare, con la soluzione. E' la sezione che fa risparmiare piu' tempo
  a chi viene dopo.

Regole di scrittura:

- Sii specifico: "manca X perche' serve Y" vale piu' di "migliorare X".
- Niente elenchi di file modificati: quelli stanno in `git log`.
- Tieni il file sotto le 120 righe. Se cresce, taglia le cose vecchie: e' una
  memoria di lavoro, non un diario.
- Non scrivere mai dati veri della lega o credenziali: il repository e'
  pubblico.

Alla fine mostra all'utente cosa hai cambiato e chiedi se vuole il commit.
