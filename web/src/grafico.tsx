import { useId, useState } from "react";

/**
 * Un grafico a linee, disegnato a mano in SVG.
 *
 * Senza libreria: ne servirebbe una da un centinaio di kilobyte per fare una
 * cosa che qui sono due `path`, e il sito lo aprono dieci persone anche dal
 * telefono.
 *
 * I colori sono una scala categoriale **verificata** per fondo scuro: ogni
 * coppia vicina resta distinguibile anche a chi non vede bene i colori. Non
 * si aggiungono tinte a piacere e non si riciclano in cerchio — oltre l'ottava
 * squadra il grafico smette di accettarne, perché a quel punto nessuno
 * distinguerebbe più le linee.
 *
 * E il colore segue la **squadra**, non la sua posizione nell'elenco: togliere
 * una squadra dal confronto non deve ridipingere le altre.
 */
export const COLORI = [
  "#3987e5",
  "#d95926",
  "#199e70",
  "#c98500",
  "#d55181",
  "#008300",
  "#9085e9",
  "#e66767",
];

export const MASSIME_SERIE = COLORI.length;

export type Serie = {
  nome: string;
  punti: { x: number; y: number }[];
};

const LARGHEZZA = 820;
const ALTEZZA = 300;
const MARGINE = { su: 14, giu: 28, sinistra: 42, destra: 108 };

function arrotonda(valore: number, verso: "su" | "giu", passo: number) {
  return verso === "su"
    ? Math.ceil(valore / passo) * passo
    : Math.floor(valore / passo) * passo;
}

export function GraficoLinee({
  serie,
  etichettaX,
  formatoY = (v: number) => String(v),
}: {
  serie: Serie[];
  etichettaX: string;
  formatoY?: (valore: number) => string;
}) {
  const id = useId();
  const [sopra, setSopra] = useState<number | null>(null);
  const [tabella, setTabella] = useState(false);

  const tutti = serie.flatMap((s) => s.punti);
  if (tutti.length === 0) return null;

  const xs = [...new Set(tutti.map((p) => p.x))].sort((a, b) => a - b);
  const minX = xs[0];
  const maxX = xs[xs.length - 1];
  const minY = arrotonda(Math.min(...tutti.map((p) => p.y)), "giu", 10);
  const maxY = arrotonda(Math.max(...tutti.map((p) => p.y)), "su", 10);

  const larghezzaUtile = LARGHEZZA - MARGINE.sinistra - MARGINE.destra;
  const altezzaUtile = ALTEZZA - MARGINE.su - MARGINE.giu;
  const perX = (x: number) =>
    MARGINE.sinistra +
    (maxX === minX ? larghezzaUtile / 2 : ((x - minX) / (maxX - minX)) * larghezzaUtile);
  const perY = (y: number) =>
    MARGINE.su +
    (maxY === minY ? altezzaUtile / 2 : (1 - (y - minY) / (maxY - minY)) * altezzaUtile);

  const tacche = [minY, (minY + maxY) / 2, maxY];
  // Le etichette in fondo alla linea bastano fino a quattro: oltre si
  // accavallano, e da lì in poi è la legenda a dire chi è chi.
  const etichetteInLinea = serie.length <= 4;

  // Due squadre che chiudono vicine scriverebbero una sopra l'altra: si
  // ordinano per altezza e si spingono via finché non stanno comode. Serve
  // davvero — con quattro linee che si incrociano capita quasi sempre.
  const ALTEZZA_RIGA = 15;
  const etichette = etichetteInLinea
    ? (() => {
        const posti = serie
          .map((s, indice) => {
            const ordinati = [...s.punti].sort((a, b) => a.x - b.x);
            const ultimo = ordinati[ordinati.length - 1];
            return { indice, nome: s.nome, y: ultimo ? perY(ultimo.y) : 0 };
          })
          .sort((a, b) => a.y - b.y);
        for (let i = 1; i < posti.length; i += 1) {
          const minimo = posti[i - 1].y + ALTEZZA_RIGA;
          if (posti[i].y < minimo) posti[i].y = minimo;
        }
        return new Map(posti.map((p) => [p.indice, p.y]));
      })()
    : new Map<number, number>();

  const vicino = (clientX: number, rettangolo: DOMRect) => {
    const dentro = ((clientX - rettangolo.left) / rettangolo.width) * LARGHEZZA;
    let scelto = xs[0];
    for (const x of xs) {
      if (Math.abs(perX(x) - dentro) < Math.abs(perX(scelto) - dentro)) scelto = x;
    }
    return scelto;
  };

  return (
    <div className="grafico">
      <div className="grafico-testata">
        <div className="legenda">
          {serie.map((s, indice) => (
            <span key={s.nome} className="voce-legenda">
              <span
                className="segno"
                style={{ background: COLORI[indice % COLORI.length] }}
              />
              {s.nome}
            </span>
          ))}
        </div>
        <button className="secondario" onClick={() => setTabella((v) => !v)}>
          {tabella ? "Mostra il grafico" : "Mostra la tabella"}
        </button>
      </div>

      {tabella ? (
        <div className="tabella-contenitore">
          <table className="tabella">
            <thead>
              <tr>
                <th>{etichettaX}</th>
                {serie.map((s) => (
                  <th key={s.nome} className="numerica">
                    {s.nome}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {xs.map((x) => (
                <tr key={x}>
                  <td>{x}</td>
                  {serie.map((s) => {
                    const punto = s.punti.find((p) => p.x === x);
                    return (
                      <td key={s.nome} className="numerica">
                        {punto ? formatoY(punto.y) : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <svg
          viewBox={`0 0 ${LARGHEZZA} ${ALTEZZA}`}
          className="tela"
          role="img"
          aria-labelledby={`${id}-titolo`}
          onMouseMove={(e) =>
            setSopra(vicino(e.clientX, e.currentTarget.getBoundingClientRect()))
          }
          onMouseLeave={() => setSopra(null)}
        >
          <title id={`${id}-titolo`}>
            Andamento di {serie.map((s) => s.nome).join(", ")}. La stessa cosa in
            numeri sta nella tabella qui sopra.
          </title>

          {/* Griglia e assi stanno indietro: servono a leggere i dati, non a
              farsi guardare. */}
          {tacche.map((y) => (
            <g key={y}>
              <line
                x1={MARGINE.sinistra}
                x2={LARGHEZZA - MARGINE.destra}
                y1={perY(y)}
                y2={perY(y)}
                className="griglia"
              />
              <text x={MARGINE.sinistra - 8} y={perY(y) + 4} className="tacca fine">
                {Math.round(y)}
              </text>
            </g>
          ))}

          {xs
            .filter((x, i) => i === 0 || i === xs.length - 1 || x % 5 === 0)
            .map((x) => (
              <text key={x} x={perX(x)} y={ALTEZZA - 8} className="tacca">
                {x}
              </text>
            ))}

          {sopra !== null && (
            <line
              x1={perX(sopra)}
              x2={perX(sopra)}
              y1={MARGINE.su}
              y2={ALTEZZA - MARGINE.giu}
              className="mirino"
            />
          )}

          {serie.map((s, indice) => {
            const colore = COLORI[indice % COLORI.length];
            const ordinati = [...s.punti].sort((a, b) => a.x - b.x);
            const tracciato = ordinati
              .map((p, i) => `${i === 0 ? "M" : "L"}${perX(p.x)},${perY(p.y)}`)
              .join(" ");
            const ultimo = ordinati[ordinati.length - 1];
            const puntato = sopra === null ? null : ordinati.find((p) => p.x === sopra);

            return (
              <g key={s.nome}>
                <path d={tracciato} fill="none" stroke={colore} strokeWidth={2} />
                {puntato && (
                  <circle
                    cx={perX(puntato.x)}
                    cy={perY(puntato.y)}
                    r={4.5}
                    fill={colore}
                    className="pallino"
                  />
                )}
                {etichetteInLinea && ultimo && (
                  <>
                    {/* Spostando l'etichetta per non accavallarla, una
                        guidina sottile dice ancora a quale linea appartiene. */}
                    <line
                      x1={perX(ultimo.x)}
                      y1={perY(ultimo.y)}
                      x2={perX(ultimo.x) + 7}
                      y2={etichette.get(indice) ?? perY(ultimo.y)}
                      stroke={colore}
                      strokeWidth={1}
                      opacity={0.5}
                    />
                    <text
                      x={perX(ultimo.x) + 10}
                      y={(etichette.get(indice) ?? perY(ultimo.y)) + 4}
                      className="etichetta-linea"
                    >
                      {s.nome.length > 15 ? `${s.nome.slice(0, 14)}…` : s.nome}
                    </text>
                  </>
                )}
              </g>
            );
          })}
        </svg>
      )}

      {!tabella && sopra !== null && (
        <div className="suggerimento">
          <strong>
            {etichettaX} {sopra}
          </strong>
          {serie.map((s, indice) => {
            const punto = s.punti.find((p) => p.x === sopra);
            if (!punto) return null;
            return (
              <span key={s.nome}>
                <span
                  className="segno"
                  style={{ background: COLORI[indice % COLORI.length] }}
                />
                {s.nome} <b>{formatoY(punto.y)}</b>
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
