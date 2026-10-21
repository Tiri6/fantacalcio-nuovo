# Dati pronti da caricare

File da scaricare e dare in pasto alla pagina **Listone giocatori →
Consolida e carica**. Sono qui, nel repository, perche' cosi' si scaricano da
qualsiasi dispositivo senza dover ripescare un allegato in chat.

| File | Cos'e' |
|---|---|
| `listone-2026_27.csv` | I 518 giocatori del listone ufficiale 2026/27, con ruolo Classic e Mantra, piu' stipendio lordo annuo e nazionalita' per 402 di loro (fonte Capology, colonna *Lordo annuo EUR*). |
| `listone-2026_27-senza-stipendio.csv` | I 116 rimasti senza importo, squadra per squadra. Di questi, 64 non compaiono affatto nella fonte e 52 ci sono con la casella vuota. |

**La data di nascita e' vuota per tutti**: la fonte degli stipendi porta
l'eta', non la data. Non serve: lo status Under 21 italiano non si ricava piu'
da una data, lo segna la lega con la colonna `italiano_u21` del CSV delle rose
(vedi sotto).

Per completare: si apre il CSV in un foglio di calcolo, si riempiono le
caselle mancanti e si ricarica lo stesso file. Chi ha gia' lo stipendio non
lo perde, e gli id non cambiano mai — quindi le rose restano attaccate ai
loro giocatori.

## Il CSV delle rose

Lo si carica da **Importa dati → Rose**. L'ordine delle colonne non conta.

| Colonna | Obbligatoria | Cosa |
|---|---|---|
| `squadra` | si | La squadra della lega |
| `giocatore` | si | Il nome, come nel listone |
| `anni` | si | Anni di contratto |
| `ingaggio` | si | Stipendio lordo annuo |
| `ruoli`, `club` | solo senza listone | Si ricavano dal nome se il listone e' caricato |
| `nazionalita` | no | Vuota vale Italia |
| `italiano_u21` | no | `SI` / `NO` (anche sì/no, 1/0, true/false). Vuoto vale NO per i giocatori nuovi |

**`italiano_u21`**: e' lo status Under 21 italiano, da segnare al 31 agosto
(vale per tutta la stagione). Chi e' SI deve avere nazionalita' Italia. Se la
colonna manca dal file, i giocatori gia' presenti **tengono il valore che
avevano**.

**Non si caricano da qui**: `datanascita` e `prolungato`. Un file che le ha
ancora entra lo stesso, e il sito le elenca fra le *intestazioni ignorate*. La
data di nascita resta nel database, e lo stato del prolungamento (Lodo Corti)
non viene mai toccato da un import: si cambia solo con uno scambio.
