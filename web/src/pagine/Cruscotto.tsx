import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type Conteggio, type RigaCruscotto } from "../api";
import { milioni, useCarica } from "../carica";

/**
 * Nessun conto si fa qui.
 *
 * I numeri arrivano già fatti da `conformita.verifica_rosa`, che è il codice
 * con i test. Questa pagina sceglie solo come mostrarli: se cominciasse a
 * ricavarne di nuovi, il regolamento tornerebbe a stare in due posti.
 */
function Riquadro({ conteggio }: { conteggio: Conteggio }) {
  return (
    <div className={`riquadro ${conteggio.stato}`}>
      <span className="etichetta">{conteggio.etichetta}</span>
      <span className="valore">{conteggio.valore}</span>
      {conteggio.nota && <span className="nota">{conteggio.nota}</span>}
      {conteggio.quota !== null && (
        <div className="barra">
          <div
            className="piena"
            style={{ width: `${Math.min(conteggio.quota, 1) * 100}%` }}
          />
        </div>
      )}
    </div>
  );
}

/** Una misura col suo limite: quanto, su quanto — non solo quanto. */
function Misura({
  valore,
  limite,
  sforato,
}: {
  valore: number | string;
  limite: number | string;
  sforato?: boolean;
}) {
  return (
    <span className={sforato ? "misura sforata" : "misura"}>
      {valore}
      <span className="tenue">/{limite}</span>
    </span>
  );
}

function Riga({ riga }: { riga: RigaCruscotto }) {
  const bloccanti = riga.violazioni.filter((v) => v.bloccante);
  const avvisi = riga.violazioni.filter((v) => !v.bloccante);

  return (
    <>
      <tr className={riga.conforme ? undefined : "da-sistemare"}>
        <td className="nome">
          <Link to={`/squadre/${riga.squadra_id}`}>{riga.squadra}</Link>
        </td>
        <td>
          <Misura
            valore={riga.dimensione}
            limite={riga.limite_dimensione}
            sforato={riga.dimensione > riga.limite_dimensione}
          />
        </td>
        <td>{riga.slot_u21}</td>
        <td>{riga.portieri}</td>
        <td>
          <Misura
            valore={riga.anni_impegnati}
            limite={riga.monte_anni}
            sforato={riga.anni_impegnati > riga.monte_anni}
          />
        </td>
        <td>
          <Misura
            valore={riga.contratti_annuali}
            limite={riga.annuali_richiesti}
            sforato={riga.contratti_annuali < riga.annuali_richiesti}
          />
        </td>
        <td className="numerica">{milioni(riga.monte_ingaggi)}</td>
        <td className="numerica">{milioni(riga.dead_money)}</td>
        <td className="numerica">{milioni(riga.spesa_salariale)}</td>
        <td className={riga.spazio_salariale < 0 ? "numerica rosso" : "numerica"}>
          {milioni(riga.spazio_salariale)}
        </td>
        <td>
          {riga.conforme ? (
            <span className="pastiglia verde">Conforme</span>
          ) : (
            <span className="pastiglia rossa">Da sistemare</span>
          )}
        </td>
      </tr>

      {/* La violazione non dice solo «sfori»: dice di quanto, e quale
          articolo. Senza questi due numeri l'avviso non aiuta nessuno. */}
      {riga.violazioni.length > 0 && (
        <tr className="violazioni">
          <td colSpan={11}>
            {[...bloccanti, ...avvisi].map((v) => (
              <div
                key={v.codice}
                className={v.bloccante ? "violazione blocca" : "violazione"}
              >
                <span className="articolo">{v.articolo}</span>
                <span>{v.messaggio}</span>
                {v.valore !== null && v.limite !== null && (
                  <span className="tenue">
                    ({milioni(v.valore)} contro {milioni(v.limite)})
                  </span>
                )}
              </div>
            ))}
          </td>
        </tr>
      )}
    </>
  );
}

export function Cruscotto() {
  const [momento, setMomento] = useState("STAGIONE");
  const { dato, errore, inCorso } = useCarica(
    () => api.cruscotto(momento),
    [momento],
  );

  if (inCorso) return <div className="fantasma alto" />;
  if (errore) return <div className="errore">{errore}</div>;
  if (!dato) return null;

  return (
    <>
      <div className="intestazione-pagina">
        <h1>🏠 Cruscotto della lega</h1>
        <p>Contratti, monte anni e vincoli salariali di tutte le squadre.</p>
      </div>

      <div className="riquadri">
        {dato.conteggi.map((c) => (
          <Riquadro key={c.etichetta} conteggio={c} />
        ))}
      </div>

      {dato.mercato_bloccato && (
        <div className="avviso">
          🔒 Trade deadline superata: il mercato è bloccato fino a fine stagione
          (art. 5).
        </div>
      )}

      <div className="lente">
        <span className="etichetta">Controlla le rose come se fosse:</span>
        <div className="filtri">
          {dato.momenti.map((m) => (
            <button
              key={m.nome}
              className={momento === m.nome ? "filtro attiva" : "filtro"}
              onClick={() => setMomento(m.nome)}
            >
              {m.etichetta}
            </button>
          ))}
        </div>
        <p className="tenue">
          In stagione lo sforamento del Salary Cap dovuto a uno scambio è
          tollerato (art. 8b) e il Salary Floor non si verifica. A fine asta
          tutto diventa vincolante.
        </p>
      </div>

      <div className="tabella-contenitore">
        <table className="tabella">
          <thead>
            <tr>
              <th>Squadra</th>
              <th>Rosa</th>
              <th>U21</th>
              <th>Portieri</th>
              <th>Anni</th>
              <th>Annuali</th>
              <th className="numerica">Ingaggi</th>
              <th className="numerica">Dead money</th>
              <th className="numerica">Spesa</th>
              <th className="numerica">Spazio cap</th>
              <th>Esito</th>
            </tr>
          </thead>
          <tbody>
            {dato.righe.map((r) => (
              <Riga key={r.squadra_id} riga={r} />
            ))}
          </tbody>
        </table>
      </div>

      <p className="didascalia">
        Monte anni {dato.monte_anni} · Salary Cap {milioni(dato.salary_cap)} ·
        Salary Floor {milioni(dato.salary_floor)} (fonte ingaggi: Capology)
      </p>
    </>
  );
}
