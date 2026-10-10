/**
 * Chiaro o scuro, e chi lo decide.
 *
 * Tre possibilità e non due: **Sistema** è quella di partenza, perché chi non
 * ha mai aperto le impostazioni si aspetta il sito nello stesso tema di tutto
 * il resto del telefono. Chiaro e Scuro sono una scelta esplicita, e vincono
 * sul sistema finché non la si cambia.
 *
 * La scelta vive in `localStorage`: è una preferenza di chi guarda, non un
 * dato della lega. Non ha senso portarla sul server — lo stesso utente può
 * volere il sito scuro sul telefono la sera e chiaro sul portatile la
 * mattina, ed è il browser a sapere quale dei due sta usando.
 *
 * Si applica scrivendo `data-tema` su `<html>`: i colori sono tutti token
 * CSS, e il foglio di stile li ridefinisce in blocco per il tema chiaro.
 */

export type Tema = "sistema" | "chiaro" | "scuro";

const CHIAVE = "fanta-tema";

export const TEMI: { nome: Tema; etichetta: string; icona: string }[] = [
  { nome: "sistema", etichetta: "Come il sistema", icona: "🖥️" },
  { nome: "chiaro", etichetta: "Chiaro", icona: "☀️" },
  { nome: "scuro", etichetta: "Scuro", icona: "🌙" },
];

/**
 * Il tema scelto, o «sistema» se non ce n'è uno.
 *
 * In lettura privata, con i dati del sito bloccati o durante un'anteprima,
 * `localStorage` può lanciare invece di rispondere: in quel caso si parte dal
 * sistema, che è esattamente il comportamento giusto.
 */
export function temaScelto(): Tema {
  try {
    const salvato = localStorage.getItem(CHIAVE);
    if (salvato === "chiaro" || salvato === "scuro" || salvato === "sistema") {
      return salvato;
    }
  } catch {
    // Niente da fare: si usa il default.
  }
  return "sistema";
}

/** Scrive la scelta su `<html>`. Con «sistema» si toglie l'attributo e
 *  comanda `prefers-color-scheme`, che il CSS gestisce da sé. */
export function applicaTema(tema: Tema): void {
  const radice = document.documentElement;
  if (tema === "sistema") {
    radice.removeAttribute("data-tema");
  } else {
    radice.setAttribute("data-tema", tema);
  }
}

export function salvaTema(tema: Tema): void {
  try {
    localStorage.setItem(CHIAVE, tema);
  } catch {
    // Se il browser non lo lascia scrivere, il tema vale per questa
    // schermata e basta: meglio di un errore in faccia a chi ha solo
    // premuto un bottone.
  }
  applicaTema(tema);
}

/** Da chiamare una volta sola, prima del primo disegno: senza, la pagina
 *  comparirebbe scura e diventerebbe chiara un istante dopo. */
export function avviaTema(): void {
  applicaTema(temaScelto());
}
