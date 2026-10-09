/**
 * Caricare qualcosa dall'API, con lo stesso comportamento ovunque.
 *
 * Senza, ogni pagina riscrive lo stesso `useEffect` — e la riscrittura
 * numero tre dimentica la guardia contro il componente smontato, che e'
 * proprio il caso in cui React avverte di un aggiornamento su niente.
 */

import { useEffect, useState } from "react";

export type Caricamento<T> = {
  dato: T | null;
  errore: string | null;
  /** Vero finché la prima risposta non è arrivata. */
  inCorso: boolean;
};

export function useCarica<T>(
  prendi: () => Promise<T>,
  dipendenze: unknown[] = [],
): Caricamento<T> {
  const [dato, setDato] = useState<T | null>(null);
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(true);

  useEffect(() => {
    let vivo = true;
    setInCorso(true);
    setErrore(null);
    prendi()
      .then((risultato) => vivo && setDato(risultato))
      .catch((guasto) => vivo && setErrore(String(guasto?.message ?? guasto)))
      .finally(() => vivo && setInCorso(false));
    return () => {
      vivo = false;
    };
    // `prendi` e' una lambda nuova a ogni render: le dipendenze vere le
    // dichiara chi chiama, come farebbe con useEffect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dipendenze);

  return { dato, errore, inCorso };
}

/** In milioni, come li legge la lega: 3_330_000 -> «3.3M». */
export function milioni(valore: number, decimali = 1): string {
  return `${(valore / 1_000_000).toFixed(decimali)}M`;
}
