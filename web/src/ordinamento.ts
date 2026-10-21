import { useMemo, useState } from "react";

/**
 * Ordinare una tabella cliccando sull'intestazione. Solo nel browser: le righe
 * sono già tutte qui, e riordinarle non è una regola ma una vista.
 *
 * Primo clic ordina in modo crescente, il secondo inverte, il terzo torna
 * all'ordine di partenza. Chi non ha il dato (`null`) sta sempre in fondo,
 * qualunque sia la direzione: un trattino non è «il più piccolo».
 */

export type Direzione = "crescente" | "decrescente";
type Valore = string | number | boolean | null | undefined;

export function useOrdinamento<T>(
  righe: T[],
  chiavi: Record<string, (riga: T) => Valore>,
) {
  const [colonna, setColonna] = useState<string | null>(null);
  const [direzione, setDirezione] = useState<Direzione>("crescente");

  function imposta(nome: string) {
    if (colonna !== nome) {
      setColonna(nome);
      setDirezione("crescente");
    } else if (direzione === "crescente") {
      setDirezione("decrescente");
    } else {
      setColonna(null);
      setDirezione("crescente");
    }
  }

  const ordinate = useMemo(() => {
    const chiave = colonna ? chiavi[colonna] : undefined;
    if (!chiave) return righe;
    const segno = direzione === "crescente" ? 1 : -1;
    return righe
      .map((riga, posto) => ({ riga, posto, valore: chiave(riga) }))
      .sort((a, b) => {
        const vuotoA = a.valore === null || a.valore === undefined;
        const vuotoB = b.valore === null || b.valore === undefined;
        if (vuotoA || vuotoB) return vuotoA === vuotoB ? a.posto - b.posto : vuotoA ? 1 : -1;
        const da = a.valore as string | number | boolean;
        const db = b.valore as string | number | boolean;
        const confronto =
          typeof da === "string" && typeof db === "string"
            ? da.localeCompare(db, "it", { sensitivity: "base" })
            : Number(da) - Number(db);
        return confronto !== 0 ? segno * confronto : a.posto - b.posto;
      })
      .map((x) => x.riga);
    // `chiavi` è un oggetto nuovo a ogni rendering: conta solo cosa si ordina.
  }, [righe, colonna, direzione]);

  return { ordinate, colonna, direzione, imposta };
}
