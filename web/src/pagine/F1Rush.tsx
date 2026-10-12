import { useState } from "react";
import { ErroreApi, api, type PaginaF1 } from "../api";
import { useCarica } from "../carica";

/**
 * F1 Rush Finale: la classifica a tappe sulle ultime giornate di Serie A.
 *
 * Ha sostituito la Supercoppa nel V3, e non è un cambio di nome: la Supercoppa
 * era una gara fra due squadre, qui corrono tutte e dieci e si contano i punti
 * di tappa. Esiste solo se la lega la gioca.
 */

function Assegna({
  dato,
  onFatto,
}: {
  dato: PaginaF1;
  onFatto: (pagina: PaginaF1) => void;
}) {
  const [scelta, setScelta] = useState(dato.squadre[0] ?? "");
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  async function registra() {
    setErrore(null);
    setInCorso(true);
    try {
      onFatto(await api.assegnaF1(scelta));
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi
          ? guasto.message
          : "Non riesco a contattare il server.",
      );
    } finally {
      setInCorso(false);
    }
  }

  return (
    <div className="riquadro">
      <div className="campo">
        <label htmlFor="f1-vincitrice">Chi ha vinto</label>
        <select
          id="f1-vincitrice"
          value={scelta}
          onChange={(e) => setScelta(e.target.value)}
        >
          {dato.squadre.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>
      <p className="didascalia">
        In cima c'è chi guida la classifica: è quasi sempre la risposta, ma
        resta una proposta — i risultati possono non essere tutti caricati.
      </p>
      {errore && (
        <div className="errore" role="alert">
          {errore}
        </div>
      )}
      <button className="principale" onClick={registra} disabled={inCorso}>
        {inCorso ? "Registro…" : "Registra nell'albo d'oro"}
      </button>
    </div>
  );
}

export function F1Rush() {
  const [giro, setGiro] = useState(0);
  const { dato, errore, inCorso } = useCarica(() => api.f1Rush(), [giro]);
  const [appena, setAppena] = useState<string | null>(null);

  if (inCorso) return <div className="fantasma alto" />;
  if (errore)
    return (
      <div className="vuoto">
        <h1>🏁 F1 Rush Finale</h1>
        <p>{errore}</p>
      </div>
    );
  if (!dato) return null;

  return (
    <>
      <div className="intestazione-pagina">
        <h1>🏁 F1 Rush Finale</h1>
        <p>
          Ultime {dato.giornate_serie_a} giornate di Serie A (
          {dato.prima_giornata}ª–{dato.ultima_giornata}ª) · {dato.criterio}
        </p>
      </div>

      {appena && <div className="conferma">{appena}</div>}

      {dato.senza_giornate_serie_a && (
        <div className="riquadro avviso">
          ⚠️ Il calendario caricato non dice a quale giornata di{" "}
          <strong>Serie A</strong> corrisponde ogni turno, quindi qui si usano
          le ultime giornate di lega disputate. Compilando{" "}
          <code>giornata_serie_a</code> in fase di import, il conto diventa
          quello letterale dell'articolo 1.
        </div>
      )}

      {dato.classifica.length === 0 ? (
        <div className="riquadro avviso">
          🏁 Nessuna tappa disputata: la classifica compare quando i risultati
          delle ultime giornate sono caricati.
        </div>
      ) : (
        <>
          <div className="tabella-contenitore">
            <table className="tabella">
              <thead>
                <tr>
                  <th className="numerica">Pos</th>
                  <th>Squadra</th>
                  <th className="numerica">Punti</th>
                  <th className="numerica">Vittorie di tappa</th>
                  <th className="numerica">Fantapunti</th>
                </tr>
              </thead>
              <tbody>
                {dato.classifica.map((r) => (
                  <tr key={r.squadra}>
                    <td className="numerica tenue">{r.posizione}</td>
                    <td className="forte">{r.squadra}</td>
                    <td className="numerica">{r.punti}</td>
                    <td className="numerica">{r.vittorie_di_tappa}</td>
                    <td className="numerica">{r.fantapunti.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="didascalia">
            Ordine: punti, poi vittorie di tappa, poi fantapunti totali — i due
            spareggi della Formula 1, nel suo stesso ordine. A pari fantapunti
            nella stessa tappa valgono i pari merito, e prendono tutte i punti
            della posizione migliore.
          </p>
          {dato.punti_per_posizione.length > 0 && (
            <p className="didascalia">
              Punti di tappa:{" "}
              {dato.punti_per_posizione
                .map((p, i) => `${i + 1}º = ${p}`)
                .join(" · ")}
            </p>
          )}

          <details className="formato">
            <summary>Tappa per tappa</summary>
            <div className="elenco-tappe">
              {dato.tappe.map((t) => (
                <p key={t.titolo}>
                  <strong>{t.titolo}</strong> — {t.podio.join(" · ")}
                </p>
              ))}
            </div>
          </details>
        </>
      )}

      <h2>Vincitrice</h2>
      {dato.vincitrice ? (
        <div className="conferma">
          🏁 F1 Rush: <strong>{dato.vincitrice}</strong>.
        </div>
      ) : dato.posso_assegnare ? (
        <Assegna
          dato={dato}
          onFatto={(pagina) => {
            setAppena(`F1 Rush a ${pagina.vincitrice}.`);
            setGiro((g) => g + 1);
          }}
        />
      ) : (
        <div className="riquadro">🏁 Non ancora assegnata.</div>
      )}

      <p className="didascalia">
        Montepremi: i calzettoni di una squadra di Serie A (art. 1).
      </p>
    </>
  );
}
