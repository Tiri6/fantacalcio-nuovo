import { Link } from "react-router-dom";
import { api } from "../api";
import { useCarica } from "../carica";

/**
 * I parametri del regolamento che il gestionale applica davvero.
 *
 * I gruppi arrivano da `leghe.prospetto_regolamento`, la stessa funzione che
 * disegna la pagina Streamlit: scritti qui, un lodo avrebbe aggiornato una
 * pagina e lasciato l'altra a dire il numero vecchio.
 */

export function Regolamento() {
  const { dato, errore, inCorso } = useCarica(() => api.regolamento(), []);

  if (inCorso) return <div className="fantasma alto" />;
  if (errore) return <div className="errore">{errore}</div>;
  if (!dato) return null;

  return (
    <>
      <div className="intestazione-pagina">
        <h1>📖 Regolamento applicato</h1>
        <p>
          Questi sono i valori che il gestionale usa per validare rose, scambi e
          formazioni.
        </p>
      </div>

      <Link className="bottone-principale" to="/regolamento/chat">
        💬 Chiedi una norma a parole
      </Link>

      {dato.gruppi.map((gruppo) => (
        <section key={gruppo.titolo} className="gruppo-regole">
          <h2>{gruppo.titolo}</h2>
          {gruppo.nota && <p className="didascalia">{gruppo.nota}</p>}
          <div className="tabella-contenitore">
            <table className="tabella">
              <tbody>
                {gruppo.voci.map((v) => (
                  <tr key={v.voce}>
                    <td>{v.voce}</td>
                    <td className="forte">{v.valore}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      {dato.coppa && (
        <p className="prosa">
          <strong>Coppa Italia</strong> — {dato.coppa}
        </p>
      )}
      {dato.f1_rush && (
        <p className="prosa">
          <strong>F1 Rush Finale</strong> — {dato.f1_rush}
        </p>
      )}

      <section className="gruppo-regole">
        <h2>Ruoli Mantra</h2>
        <div className="tabella-contenitore">
          <table className="tabella">
            <tbody>
              {dato.ruoli_mantra.map((r) => (
                <tr key={r.sigla}>
                  <td className="forte">{r.sigla}</td>
                  <td>{r.nome}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="riquadro avviso">
        ❓ Alcuni punti del regolamento restano da decidere o sono ambigui: sono
        elencati in <code>PUNTI_APERTI.md</code> nel repository, con l'ipotesi
        che il codice applica oggi.
      </div>
    </>
  );
}
