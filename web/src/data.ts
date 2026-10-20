/**
 * La data di nascita come si scrive su un telefono: solo cifre, e le barre le
 * mette il campo.
 *
 * Il tastierino numerico di iOS e di Android non ha lo slash, quindi chi
 * doveva scrivere `15/03/1990` non ci riusciva. Qui sta la parte che si può
 * ragionare senza un browser — la maschera, l'incolla, la validazione —
 * mentre `campoData.tsx` la collega a un input vero.
 *
 * **Il formato che va al server non cambia**: `gg/mm/aaaa`, quello che
 * `leggi_data_italiana` già legge. La maschera lo produce, non lo inventa.
 *
 * Cosa NON si controlla qui, di proposito: l'età minima e quella massima. Sono
 * regole del server (`ETA_MINIMA`, `ETA_MASSIMA` in `anagrafica.py`) e
 * riscriverle in TypeScript farebbe una seconda copia che prima o poi dice
 * una cosa diversa. Il server le applica e il suo messaggio arriva sotto il
 * modulo.
 */

export const LUNGHEZZA_DATA = 10; // gg/mm/aaaa
const CIFRE_DATA = 8;

const SEPARATORE = /[/\-. ]/;

const MESI = [
  "Gennaio",
  "Febbraio",
  "Marzo",
  "Aprile",
  "Maggio",
  "Giugno",
  "Luglio",
  "Agosto",
  "Settembre",
  "Ottobre",
  "Novembre",
  "Dicembre",
];

export function soloCifre(testo: string): string {
  return testo.replace(/\D/g, "");
}

/**
 * Dalle cifre alla data con le barre: `15` → `15/`, `1503` → `15/03/`.
 *
 * La barra dopo il gruppo completo si aggiunge solo **scrivendo in avanti**
 * (`conBarraFinale`). Cancellando no: se `15` tornasse subito `15/`, il
 * backspace non riuscirebbe mai a togliere la barra e il campo si
 * bloccherebbe lì.
 */
export function formattaData(cifre: string, conBarraFinale: boolean): string {
  const d = cifre.slice(0, CIFRE_DATA);
  let fuori = d.slice(0, 2);
  if (d.length > 2 || (conBarraFinale && d.length === 2)) {
    fuori += "/" + d.slice(2, 4);
  }
  if (d.length > 4 || (conBarraFinale && d.length === 4)) {
    fuori += "/" + d.slice(4, 8);
  }
  return fuori;
}

const COMPLETA = /^(\d{1,2})[/\-. ](\d{1,2})[/\-. ](\d{4})$/;
const ISO = /^(\d{4})[/\-. ](\d{1,2})[/\-. ](\d{1,2})$/;

const due = (n: string) => n.padStart(2, "0");

/**
 * Se il testo incollato è una data intera, la restituisce come `gg/mm/aaaa`.
 *
 * Accetta `15/03/1990`, `15-03-1990`, `15.03.1990`, `15031990`, ma anche
 * `5/3/1990` (giorno e mese a una cifra, con le barre non c'è ambiguità) e
 * `1990-03-15`: è come l'autocompilazione del telefono (`autocomplete=bday`)
 * scrive la data in certe lingue, e senza questo il campo la
 * rovinerebbe.
 *
 * Senza separatori servono otto cifre: `1531990` può voler dire `15/3/1990` o
 * `1/5/31990`, e non si indovina.
 */
export function daIncolla(testo: string): string | null {
  const pulito = testo.trim();
  const iso = ISO.exec(pulito);
  if (iso) return `${due(iso[3])}/${due(iso[2])}/${iso[1]}`;
  const intera = COMPLETA.exec(pulito);
  if (intera) return `${due(intera[1])}/${due(intera[2])}/${intera[3]}`;
  if (/^\d{8}$/.test(pulito)) return formattaData(pulito, false);
  return null;
}

export type Modifica = {
  valore: string;
  /** Dove rimettere il cursore, o `null` se sta in fondo e va lasciato dov'è. */
  cursore: number | null;
};

function posizioneDopoCifre(
  valore: string,
  quante: number,
  salta: boolean,
): number {
  if (quante <= 0) return 0;
  let viste = 0;
  for (let i = 0; i < valore.length; i += 1) {
    if (/\d/.test(valore[i])) {
      viste += 1;
      if (viste === quante) {
        const dopo = i + 1;
        // Scrivendo in avanti si scavalca la barra: la cifra successiva va
        // nel gruppo dopo, non attaccata a questo.
        return salta && valore[dopo] === "/" ? dopo + 1 : dopo;
      }
    }
  }
  return valore.length;
}

/**
 * Cosa diventa il campo dopo una modifica.
 *
 * `nuovo` è il testo com'è subito dopo che il browser ha applicato la
 * modifica, `cursore` dove sta il cursore in quel momento. Si ricava tutto da
 * lì, senza guardare che tasto sia stato premuto: tastiere diverse mandano
 * eventi diversi, ma il testo risultante è lo stesso.
 *
 * - **Solo cifre.** Quel che non è una cifra sparisce.
 * - **Cancellare una barra toglie anche la cifra prima.** Il backspace subito
 *   dopo `15/` lascia `1`, non `15/` come prima: altrimenti ci si
 *   bloccherebbe sulla barra. Si riconosce perché il testo è più corto ma le
 *   cifre sono le stesse.
 * - **Una barra scritta a mano chiude il gruppo.** Con una tastiera fisica
 *   `5/3/1990` deve dare `05/03/1990`, non `53/19/90`.
 * - **Il cursore resta dove l'utente stava lavorando.** Correggere una cifra
 *   in mezzo non lo deve spedire in fondo, o il secondo backspace
 *   cancellerebbe l'ultima cifra invece di quella accanto.
 */
export function applicaModifica(
  precedente: string,
  nuovo: string,
  cursore: number,
  tipo: "digitazione" | "incolla" = "digitazione",
): Modifica {
  const posizione = Math.min(Math.max(cursore, 0), nuovo.length);
  const cancella = tipo === "digitazione" && nuovo.length < precedente.length;

  let cifre = soloCifre(nuovo);
  let prima = soloCifre(nuovo.slice(0, posizione)).length;

  // Una barra scritta dopo una cifra sola del giorno o del mese la completa.
  if (
    tipo === "digitazione" &&
    nuovo.length === precedente.length + 1 &&
    SEPARATORE.test(nuovo[posizione - 1] ?? "") &&
    prima === cifre.length &&
    (prima === 1 || prima === 3)
  ) {
    cifre = cifre.slice(0, prima - 1) + "0" + cifre.slice(prima - 1);
    prima += 1;
  }

  // Tolta una barra e nient'altro: porta via anche la cifra che la precede.
  if (cancella && cifre === soloCifre(precedente) && prima > 0) {
    cifre = cifre.slice(0, prima - 1) + cifre.slice(prima);
    prima -= 1;
  }

  cifre = cifre.slice(0, CIFRE_DATA);
  prima = Math.min(prima, cifre.length);

  const valore = formattaData(cifre, !cancella);
  const inFondo = prima >= cifre.length;
  return {
    valore,
    cursore: inFondo ? null : posizioneDopoCifre(valore, prima, !cancella),
  };
}

export type EsameData = {
  /** `gg/mm/aaaa` scritta per intero. */
  completa: boolean;
  /** Perché non va, quando è completa e non va. `null` se va (o se manca ancora). */
  errore: string | null;
};

function giorniDelMese(anno: number, mese: number): number {
  const d = new Date(2000, 0, 1);
  d.setFullYear(anno, mese, 0); // il giorno zero del mese dopo è l'ultimo di questo
  return d.getDate();
}

/**
 * Se la data scritta esiste e non è nel futuro.
 *
 * Non c'è alcun errore finché non è completa: dire «data non valida» a chi ha
 * scritto `15/0` è dirgli una cosa vera e inutile. `oggi` si può passare per
 * provarla con una data fissa.
 */
export function esaminaData(testo: string, oggi: Date = new Date()): EsameData {
  const lette = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(testo);
  if (!lette) return { completa: false, errore: null };

  const giorno = Number(lette[1]);
  const mese = Number(lette[2]);
  const anno = Number(lette[3]);

  if (mese < 1 || mese > 12) {
    return { completa: true, errore: "Il mese va da 01 a 12." };
  }
  if (giorno < 1) {
    return { completa: true, errore: "Il giorno va da 01 in su." };
  }
  const massimo = giorniDelMese(anno, mese);
  if (giorno > massimo) {
    return {
      completa: true,
      errore: `${MESI[mese - 1]} ${anno} ha ${massimo} giorni: il ${giorno} non c'è.`,
    };
  }

  // `new Date(anno, ...)` legge gli anni 0-99 come 1900-1999: `setFullYear` no.
  const nascita = new Date(2000, 0, 1);
  nascita.setFullYear(anno, mese - 1, giorno);
  const mezzanotte = new Date(
    oggi.getFullYear(),
    oggi.getMonth(),
    oggi.getDate(),
  );
  if (nascita > mezzanotte) {
    return {
      completa: true,
      errore: "La data di nascita non può essere nel futuro.",
    };
  }
  return { completa: true, errore: null };
}
