import type { ReactNode } from "react";
import type { Direzione } from "./ordinamento";

/** L'intestazione cliccabile: freccia visibile e `aria-sort` per chi non vede. */
export function IntestazioneOrdinabile({
  nome,
  attiva,
  direzione,
  onOrdina,
  className,
  children,
}: {
  nome: string;
  attiva: string | null;
  direzione: Direzione;
  onOrdina: (nome: string) => void;
  className?: string;
  children: ReactNode;
}) {
  const e_questa = attiva === nome;
  return (
    <th
      className={className}
      aria-sort={
        e_questa
          ? direzione === "crescente"
            ? "ascending"
            : "descending"
          : "none"
      }
    >
      <button
        type="button"
        className="ordina"
        onClick={() => onOrdina(nome)}
      >
        {children}
        <span className="freccia" aria-hidden="true">
          {e_questa ? (direzione === "crescente" ? "▲" : "▼") : "↕"}
        </span>
        <span className="solo-lettori">
          {e_questa
            ? `, ordinata in modo ${direzione}. Premi per cambiare`
            : ", premi per ordinare"}
        </span>
      </button>
    </th>
  );
}
