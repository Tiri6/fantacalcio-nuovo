import { useState } from "react";
import { api, type Partita, type RigaClassifica } from "../api";
import { useCarica } from "../carica";
import { COLORI, GraficoLinee, MASSIME_SERIE, type Serie } from "../grafico";

/**
 * Risultati importati da Leghe Fantacalcio: qui non si gioca, si legge.
 *
 * La classifica però non è solo una tabella: è anche l'ingresso della Draft
 * Lottery, ed è il motivo per cui porta i punti fantacalcio accanto ai punti.
 */
function Classifica({ righe }: { righe: RigaClassifica[] }) {
  return (
    <>
      <div className="tabella-contenitore">
        <table className="tabella">
          <thead>
            <tr>
              <th>Pos</th>
              <th>Squadra</th>
              <th className="numerica">PG</th>
              <th className="numerica">V</th>
              <th className="numerica">N</th>
              <th className="numerica">P</th>
              <th className="numerica">GF</th>
              <th className="numerica">GS</th>
              <th className="numerica">DR</th>
              <th className="numerica">Punti</th>
              <th className="numerica">Punti fantacalcio</th>
            </tr>
          </thead>
          <tbody>
            {righe.map((r) => (
              <tr key={r.squadra}>
                <td className="numerica">{r.posizione}</td>
                <td className="forte">{r.squadra}</td>
                <td className="numerica">{r.giocate}</td>
                <td className="numerica">{r.vinte}</td>
                <td className="numerica">{r.pareggiate}</td>
                <td className="numerica">{r.perse}</td>
                <td className="numerica">{r.gol_fatti}</td>
                <td className="numerica">{r.gol_subiti}</td>
                <td className="numerica">
                  {r.differenza_reti > 0 ? `+${r.differenza_reti}` : r.differenza_reti}
                </td>
                <td className="numerica forte">{r.punti}</td>
                <td className="numerica tenue">{r.punti_fantacalcio.toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="didascalia">
        La classifica finale determina la Draft Lottery: le pick 1-5 si
        sorteggiano tra la seconda metà della classifica.
      </p>
    </>
  );
}

function Calendario({
  partite,
  disputate,
}: {
  partite: Partita[];
  disputate: number;
}) {
  const giornate = [...new Set(partite.map((p) => p.giornata))].sort((a, b) => a - b);
  const [scelta, setScelta] = useState(Math.max(disputate, giornate[0] ?? 1));

  if (giornate.length === 0) {
    return (
      <div className="vuoto">
        🗓️ Il calendario non è ancora stato importato. Si carica dalla pagina
        «Importa dati».
      </div>
    );
  }

  return (
    <>
      <div className="campo">
        <label htmlFor="c-giornata">
          Giornata <strong>{scelta}</strong>{" "}
          <span className="tenue">
            {scelta <= disputate ? "— disputata" : "— da giocare"}
          </span>
        </label>
        <input
          id="c-giornata"
          type="range"
          min={giornate[0]}
          max={giornate[giornate.length - 1]}
          value={scelta}
          onChange={(e) => setScelta(Number(e.target.value))}
        />
      </div>

      <div className="partite">
        {partite
          .filter((p) => p.giornata === scelta)
          .map((p) => (
            <div key={`${p.casa}-${p.trasferta}`} className="partita">
              <span className="squadra casa">{p.casa}</span>
              {p.gol_casa === null ? (
                <span className="risultato da-giocare">—</span>
              ) : (
                <span className="risultato">
                  {p.gol_casa} <span className="tenue">-</span> {p.gol_trasferta}
                </span>
              )}
              <span className="squadra">{p.trasferta}</span>
              {p.punti_casa !== null && (
                <span className="punti">
                  {p.punti_casa.toFixed(1)} — {p.punti_trasferta?.toFixed(1)}
                </span>
              )}
            </div>
          ))}
      </div>
    </>
  );
}

function Andamento({
  andamento,
  classifica,
}: {
  andamento: { squadra: string; punti: { giornata: number; punti: number }[] }[];
  classifica: RigaClassifica[];
}) {
  // Si parte dalle prime quattro: tutte e dieci insieme sono un gomitolo, e
  // sopra l'ottava le linee non si distinguono più comunque.
  const [scelte, setScelte] = useState<string[]>(
    classifica.slice(0, 4).map((r) => r.squadra),
  );

  if (andamento.length === 0) {
    return <div className="vuoto">I grafici compaiono dopo la prima giornata.</div>;
  }

  const pieno = scelte.length >= MASSIME_SERIE;

  function cambia(squadra: string) {
    setScelte((precedenti) =>
      precedenti.includes(squadra)
        ? precedenti.filter((s) => s !== squadra)
        : precedenti.length < MASSIME_SERIE
          ? [...precedenti, squadra]
          : precedenti,
    );
  }

  // Il colore segue la squadra, non la posizione nell'elenco: togliendone una
  // dal confronto, le altre non devono cambiare tinta sotto gli occhi.
  const ordinate = andamento.filter((a) => scelte.includes(a.squadra));
  const serie: Serie[] = ordinate.map((a) => ({
    nome: a.squadra,
    punti: a.punti.map((p) => ({ x: p.giornata, y: p.punti })),
  }));

  return (
    <>
      <div className="filtri scelta-squadre">
        {andamento.map((a) => {
          const scelta = scelte.includes(a.squadra);
          const indice = ordinate.findIndex((o) => o.squadra === a.squadra);
          return (
            <button
              key={a.squadra}
              className={scelta ? "filtro attiva" : "filtro"}
              disabled={!scelta && pieno}
              title={
                !scelta && pieno
                  ? `Più di ${MASSIME_SERIE} linee non si distinguono: togline una.`
                  : undefined
              }
              onClick={() => cambia(a.squadra)}
            >
              <span
                className="segno"
                style={{
                  background: scelta ? COLORI[indice % COLORI.length] : "transparent",
                }}
              />
              {a.squadra}
            </button>
          );
        })}
      </div>

      {serie.length === 0 ? (
        <div className="vuoto">Scegli almeno una squadra.</div>
      ) : (
        <GraficoLinee
          serie={serie}
          etichettaX="Giornata"
          formatoY={(v) => v.toFixed(1)}
        />
      )}
    </>
  );
}

const SCHEDE = ["Classifica", "Calendario", "Andamento"] as const;

export function Campionato() {
  const { dato, errore, inCorso } = useCarica(() => api.campionato(), []);
  const [scheda, setScheda] = useState<(typeof SCHEDE)[number]>("Classifica");

  if (inCorso) return <div className="fantasma alto" />;
  if (errore) return <div className="errore">{errore}</div>;
  if (!dato) return null;

  return (
    <>
      <div className="intestazione-pagina">
        <h1>🏆 Campionato</h1>
        <p>
          Risultati importati da Leghe Fantacalcio: qui servono per la classifica
          e per l'ordine del draft.
        </p>
      </div>

      {dato.giornate_disputate === 0 ? (
        <div className="vuoto">Ancora nessuna giornata disputata.</div>
      ) : (
        <>
          <div className="schede">
            {SCHEDE.map((s) => (
              <button
                key={s}
                className={scheda === s ? "scheda attiva" : "scheda"}
                onClick={() => setScheda(s)}
              >
                {s}
              </button>
            ))}
          </div>

          {scheda === "Classifica" && <Classifica righe={dato.classifica} />}
          {scheda === "Calendario" && (
            <Calendario
              partite={dato.partite}
              disputate={dato.giornate_disputate}
            />
          )}
          {scheda === "Andamento" && (
            <Andamento andamento={dato.andamento} classifica={dato.classifica} />
          )}

          <p className="didascalia">
            {dato.giornate_disputate} giornate disputate su {dato.giornate_totali}{" "}
            previste dalla lega.
            {/* I due numeri possono non coincidere: con 10 squadre andata e
                ritorno fanno 18 giornate, ma la lega ne ha impostate 27 (è un
                punto aperto del regolamento). Dirlo è meglio che lasciar
                credere che manchino partite mai programmate. */}
            {dato.giornate_in_calendario > 0 &&
              dato.giornate_in_calendario !== dato.giornate_totali && (
                <>
                  {" "}
                  Il calendario caricato però ne ha{" "}
                  <strong>{dato.giornate_in_calendario}</strong>: con{" "}
                  {dato.classifica.length} squadre andata e ritorno arrivano fin
                  lì.
                </>
              )}
          </p>
        </>
      )}
    </>
  );
}
