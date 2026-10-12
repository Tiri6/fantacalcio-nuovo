import { api } from "../api";
import { useCarica } from "../carica";

/**
 * Coppa Italia: tabellone, turni e regole.
 *
 * Esiste solo se la lega la gioca — la voce di menu non compare altrimenti, e
 * chi arriva all'indirizzo a mano trova un 404 con la sua spiegazione invece
 * di una pagina di caselle vuote.
 *
 * Il formato del V3 è a gironi: coi gironi i turni **non cadono a giornate
 * fisse** di campionato, vengono dopo, di fila. Mostrare «G5, G9, G13» sarebbe
 * un calendario inventato, quindi il tabellone dice «dopo il campionato».
 */

export function Coppa() {
  const { dato, errore, inCorso } = useCarica(() => api.coppa(), []);

  if (inCorso) return <div className="fantasma alto" />;
  if (errore)
    return (
      <div className="vuoto">
        <h1>🥇 Coppa Italia</h1>
        <p>{errore}</p>
      </div>
    );
  if (!dato) return null;

  return (
    <>
      <div className="intestazione-pagina">
        <h1>🥇 Coppa Italia</h1>
        <p>
          {dato.formato} · {dato.squadre_ammesse} squadre ammesse.
        </p>
      </div>

      {dato.a_gironi && (
        <p className="prosa">
          Formato del V3: <strong>{dato.gironi} gironi</strong> da{" "}
          {dato.squadre_per_girone} con andata e ritorno (
          {dato.giornate_di_girone} giornate), disputati{" "}
          <strong>a fine campionato</strong>, poi scontri diretti fra le{" "}
          {dato.squadre_a_eliminazione} qualificate.
        </p>
      )}

      <div className="numeri">
        <div className="numero">
          <span className="etichetta">Squadre ammesse</span>
          <span className="valore">{dato.squadre_ammesse}</span>
        </div>
        <div className="numero">
          <span className="etichetta">Scontri diretti</span>
          <span className="valore">{dato.turni}</span>
          <span className="nota">{dato.nomi_turni.join(", ")}</span>
        </div>
        <div className="numero">
          {dato.a_gironi ? (
            <>
              <span className="etichetta">Fase a gironi</span>
              <span className="valore">{dato.giornate_di_girone} giornate</span>
              <span className="nota">a fine campionato, andata e ritorno</span>
            </>
          ) : (
            <>
              <span className="etichetta">Primo turno</span>
              <span className="valore">G{dato.prima_giornata}</span>
              <span className="nota">
                poi ogni {dato.ogni_quante_giornate} giornate
              </span>
            </>
          )}
        </div>
      </div>

      <h2>Tabellone</h2>
      <div className="tabella-contenitore">
        <table className="tabella">
          <thead>
            <tr>
              <th>Fase</th>
              <th>Quando</th>
              {!dato.a_gironi && <th>Stato</th>}
            </tr>
          </thead>
          <tbody>
            {dato.tabellone.map((f) => (
              <tr key={f.fase + f.quando}>
                <td className="forte">{f.fase}</td>
                <td className="tenue">{f.quando}</td>
                {!dato.a_gironi && <td>{f.stato}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {dato.a_gironi && (
        <p className="didascalia">
          La <strong>classifica dei gironi</strong> non è ancora calcolata dal
          sito: la composizione dei gruppi e i risultati si caricano dalla
          pagina «Importa dati». La pagina Calendario mostra su quali weekend
          cadono.
        </p>
      )}

      <h2>Chi si qualifica</h2>
      {dato.a_gironi ? (
        <div className="riquadro">
          🥇 Entrano tutte e {dato.squadre_ammesse}: agli scontri diretti
          passano le prime {dato.qualificate_per_girone} di ogni girone,{" "}
          {dato.squadre_a_eliminazione} in tutto.
        </div>
      ) : dato.ammesse.length > 0 ? (
        <>
          <p className="didascalia">
            Teste di serie dalla classifica: passano le prime{" "}
            {dato.squadre_ammesse}. Ecco come sarebbero oggi.
          </p>
          <ol className="elenco-teste">
            {dato.ammesse.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
          {dato.accoppiamenti.length > 0 && (
            <>
              <h3>Accoppiamenti del {dato.nomi_turni[0]?.toLowerCase()}</h3>
              {dato.accoppiamenti.map(([alta, bassa]) => (
                <p key={alta} className="pastiglie">
                  <span className="pastiglia verde">{alta}</span>
                  <span className="didascalia">contro</span>
                  <span className="pastiglia azzurra">{bassa}</span>
                </p>
              ))}
            </>
          )}
        </>
      ) : dato.teste_di_serie ? (
        <div className="riquadro">
          🏁 Le teste di serie si assegnano dalla classifica: compariranno dopo
          le prime giornate.
        </div>
      ) : (
        <div className="riquadro">
          🎲 Sorteggio libero: gli accoppiamenti li fa chi amministra.
        </div>
      )}

      <h2>Le regole di questa coppa</h2>
      <ul className="prosa">
        <li>
          <strong>Formato</strong>: {dato.formato}
        </li>
        <li>
          <strong>Squadre ammesse</strong>: {dato.squadre_ammesse}
        </li>
        <li>
          <strong>Teste di serie</strong>:{" "}
          {dato.teste_di_serie ? "dalla classifica" : "no, sorteggio libero"}
        </li>
        <li>
          <strong>In caso di parità</strong>:{" "}
          {dato.spareggio_ai_fantapunti
            ? "passa chi ha totalizzato più fantapunti"
            : "si ripete la sfida"}
        </li>
        <li>
          <strong>Calendario</strong>:{" "}
          {dato.a_gironi
            ? `gironi e scontri diretti a fine campionato, ${dato.giornate_di_girone} giornate di girone più ${dato.turni} turni`
            : `primo turno alla ${dato.prima_giornata}ª giornata, poi uno ogni ${dato.ogni_quante_giornate}`}
        </li>
      </ul>

      <p className="didascalia">
        I risultati della coppa si importano come quelli di campionato, dalla
        pagina «Importa dati»: il gestionale non calcola i punteggi.
      </p>
    </>
  );
}
