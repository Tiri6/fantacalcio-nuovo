# Draft Room — materiale di riferimento

Due file, tutti e due **fonte di verità** per la pagina Mercato › Draft.

| File | Cos'è |
|---|---|
| `draft-room-reference.html` | L'implementazione di riferimento, funzionante. Pagina singola con dati incorporati e stato in `localStorage`. Lo script sta in fondo, dopo il blocco `<script id="data">` (che è una riga sola, lunghissima). |
| `draft-seed-2026-27.json` | I dati veri del draft 2026/27: rose pre-draft, ordine delle 222 chiamate, 400 giocatori liberi, 72 target di Tiri Team, e il draft concluso (`baked`). |

**Quando il prompt e il riferimento divergono, vince il riferimento.**

## Cosa contiene il seed

```
teams    10 squadre, rose pre-draft (contratti in corso)
order    222 chiamate, schema "dritto, dritto, inverso" e poi a esaurimento
players  400 giocatori liberi
buckets  72 target di Tiri Team, con priorità e il "perché"
baked    il draft 2026/27 concluso: 222 chiamate, 34 saltate, 1 giocatore fuori lista
```

## La tabella di accettazione, già verificata

Riproducendo `baked` sulle rose iniziali si deve ottenere questo. L'ho
verificato prima di progettare qualunque cosa, e **combacia riga per riga**
(giocatori, portieri, movimento, U21 e cap residuo al centesimo di milione).

Il controllo **non è ancora un test del progetto**: diventerà
`tests/test_draft_room.py`, ed è il primo da scrivere quando si implementa il
motore — se un giorno smette di combaciare, il motore è cambiato sotto.

| Squadra | Giocatori | Por | Movimento | U21 | Cap residuo |
|---|---:|---:|---:|---:|---:|
| Puglia Pelicans | 30 | 3 | 27 | 0 | 9.63 M |
| Partizan Degrado | 32 | 3 | 29 | 1 | 18.65 M |
| ASD Boca Seniors | 32 | 3 | 29 | 1 | 2.10 M |
| SkoReggina | 31 | 3 | 28 | 2 | 18.16 M |
| A.S. Fregio | 34 | 3 | 31 | 1 | 21.37 M |
| AS Bronzi | 33 | 3 | 30 | 1 | 12.03 M |
| Tiri Team | 31 | 3 | 28 | 4 | 1.03 M |
| Cristoiese | 35 | 3 | 32 | 4 | 7.93 M |
| MaGuardaCheRoba | 34 | 3 | 31 | 3 | 8.16 M |
| FC Scrotone | 31 | 3 | 28 | 0 | 1.27 M |

## Attenzione: nomi veri

Le squadre e i giocatori qui dentro sono quelli **veri** della lega, non la
demo. Importarli significa creare o riconoscere squadre e giocatori esistenti:
l'import va fatto con un'anteprima che dice cosa creerebbe, prima di scrivere.
