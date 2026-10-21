import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type PartitaInCalendario } from "../api";
import { useCarica } from "../carica";

/**
 * Calendario: tutti gli scontri diretti fra le squadre della lega.
 *
 * Quattro modi di guardare le stesse partite, perché le domande sono quattro:
 * «a cosa corrisponde questo weekend», «cosa si gioca questa giornata», «come
 * è finita fra me e lui», «che stagione ho davanti».
 *
 * La scheda **Weekend** non ha bisogno delle partite: si costruisce dalle
 * regole della lega. È per questo che la pagina resta utile proprio a inizio
 * stagione, quando il calendario è ancora vuoto ed è quando serve di più.
 */

type Scheda = "Weekend" | "Per giornata" | "Scontri diretti" | "Per squadra";

function risultato(p: PartitaInCalendario): string {
  if (p.gol_casa === null) return "da giocare";
  return `${p.gol_casa} – ${p.gol_trasferta} · ${p.punti_casa?.toFixed(1)} – ${p.punti_trasferta?.toFixed(1)} punti`;
}

function Riga({ p }: { p: PartitaInCalendario }) {
  return (
    <div className="partita-riga">
      <span className="chi">{p.casa}</span>
      <strong>
        {p.gol_casa === null ? "—" : `${p.gol_casa} – ${p.gol_trasferta}`}
      </strong>
      <span className="chi destra">{p.trasferta}</span>
      <span className="didascalia">
        {p.gol_casa === null
          ? "da giocare"
          : `${p.punti_casa?.toFixed(1)} – ${p.punti_trasferta?.toFixed(1)}`}
      </span>
    </div>
  );
}

function PerGiornata({
  partite,
  totali,
  disputate,
}: {
  partite: PartitaInCalendario[];
  totali: number;
  disputate: number;
}) {
  const [scelta, setScelta] = useState(Math.max(disputate, 1));
  const delTurno = partite.filter((p) => p.giornata === scelta);
  const giocata = delTurno.every((p) => p.gol_casa !== null);

  return (
    <>
      <div className="campo">
        <label htmlFor="giornata-scelta">Giornata {scelta}</label>
        <input
          id="giornata-scelta"
          type="range"
          min={1}
          max={totali}
          value={scelta}
          onChange={(e) => setScelta(Number(e.target.value))}
        />
      </div>
      <p className="didascalia">
        Giornata {scelta} — {giocata ? "disputata" : "da giocare"}
      </p>
      {delTurno.map((p) => (
        <Riga key={`${p.casa}-${p.trasferta}`} p={p} />
      ))}
    </>
  );
}

function ScontriDiretti({
  partite,
  squadre,
}: {
  partite: PartitaInCalendario[];
  squadre: string[];
}) {
  const [una, setUna] = useState(squadre[0] ?? "");
  const [due, setDue] = useState(squadre[1] ?? "");

  const incroci = partite
    .filter(
      (p) =>
        (p.casa === una && p.trasferta === due) ||
        (p.casa === due && p.trasferta === una),
    )
    .sort((a, b) => a.giornata - b.giornata);

  let vinteUna = 0;
  let vinteDue = 0;
  let pari = 0;
  for (const p of incroci) {
    if (p.gol_casa === null || p.gol_trasferta === null) continue;
    if (p.gol_casa === p.gol_trasferta) pari += 1;
    else if (p.gol_casa > p.gol_trasferta === (p.casa === una)) vinteUna += 1;
    else vinteDue += 1;
  }

  return (
    <>
      <h3>Chi ha giocato contro chi</h3>
      <p className="didascalia">
        Riga = squadra di casa, colonna = squadra in trasferta. Il numero è il
        risultato; <code>G7</code> vuol dire che l'incrocio si gioca alla
        settima giornata; una cella vuota che quell'incrocio non è in
        calendario.
      </p>
      <div className="tabella-contenitore">
        <table className="tabella griglia-incroci">
          <thead>
            <tr>
              <th />
              {squadre.map((s) => (
                <th key={s} className="centrata">
                  {s.slice(0, 3).toUpperCase()}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {squadre.map((casa) => (
              <tr key={casa}>
                <td className="forte">{casa}</td>
                {squadre.map((trasferta) => {
                  if (casa === trasferta)
                    return (
                      <td key={trasferta} className="centrata tenue">
                        —
                      </td>
                    );
                  const p = partite.find(
                    (x) => x.casa === casa && x.trasferta === trasferta,
                  );
                  return (
                    <td key={trasferta} className="centrata">
                      {!p
                        ? ""
                        : p.gol_casa === null
                          ? `G${p.giornata}`
                          : `${p.gol_casa}–${p.gol_trasferta}`}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>Faccia a faccia</h3>
      <div className="filtri">
        <div className="campo">
          <label htmlFor="h2h-a">Squadra</label>
          <select
            id="h2h-a"
            value={una}
            onChange={(e) => setUna(e.target.value)}
          >
            {squadre.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label htmlFor="h2h-b">contro</label>
          <select
            id="h2h-b"
            value={due}
            onChange={(e) => setDue(e.target.value)}
          >
            {squadre
              .filter((s) => s !== una)
              .map((s) => (
                <option key={s}>{s}</option>
              ))}
          </select>
        </div>
      </div>

      {incroci.length === 0 ? (
        <p className="didascalia">
          {una} e {due} non si incontrano in calendario.
        </p>
      ) : (
        <>
          {incroci.map((p) => (
            <p key={`${p.giornata}-${p.casa}`} className="didascalia">
              Giornata {p.giornata} · <strong>{p.casa}</strong> —{" "}
              <strong>{p.trasferta}</strong> · {risultato(p)}
            </p>
          ))}
          {vinteUna + vinteDue + pari > 0 && (
            <div className="pastiglie">
              <span className="pastiglia verde">
                {una}: {vinteUna}
              </span>
              <span className="pastiglia ambra">Pari: {pari}</span>
              <span className="pastiglia azzurra">
                {due}: {vinteDue}
              </span>
            </div>
          )}
        </>
      )}
    </>
  );
}

function PerSquadra({
  partite,
  squadre,
}: {
  partite: PartitaInCalendario[];
  squadre: string[];
}) {
  const [scelta, setScelta] = useState(squadre[0] ?? "");
  const sue = partite
    .filter((p) => p.casa === scelta || p.trasferta === scelta)
    .sort((a, b) => a.giornata - b.giornata);

  const righe = sue.map((p) => {
    const inCasa = p.casa === scelta;
    const miei = inCasa ? p.gol_casa : p.gol_trasferta;
    const suoi = inCasa ? p.gol_trasferta : p.gol_casa;
    return {
      giornata: p.giornata,
      dove: inCasa ? "Casa" : "Trasferta",
      avversaria: inCasa ? p.trasferta : p.casa,
      risultato: miei === null || suoi === null ? "" : `${miei} – ${suoi}`,
      esito:
        miei === null || suoi === null
          ? ""
          : miei > suoi
            ? "Vinta"
            : miei < suoi
              ? "Persa"
              : "Pari",
    };
  });

  const conta = (quale: string) =>
    righe.filter((r) => r.esito === quale).length;

  return (
    <>
      <div className="campo">
        <label htmlFor="cal-squadra">Squadra</label>
        <select
          id="cal-squadra"
          value={scelta}
          onChange={(e) => setScelta(e.target.value)}
        >
          {squadre.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>
      <div className="tabella-contenitore">
        <table className="tabella">
          <thead>
            <tr>
              <th className="numerica">G</th>
              <th>Dove</th>
              <th>Avversaria</th>
              <th>Risultato</th>
              <th>Esito</th>
            </tr>
          </thead>
          <tbody>
            {righe.map((r) => (
              <tr key={r.giornata}>
                <td className="numerica">{r.giornata}</td>
                <td className="tenue">{r.dove}</td>
                <td className="forte">{r.avversaria}</td>
                <td>{r.risultato || "—"}</td>
                <td>{r.esito}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {righe.some((r) => r.esito) && (
        <div className="pastiglie">
          <span className="pastiglia verde">Vinte: {conta("Vinta")}</span>
          <span className="pastiglia ambra">Pari: {conta("Pari")}</span>
          <span className="pastiglia rossa">Perse: {conta("Persa")}</span>
        </div>
      )}
    </>
  );
}

export function Calendario() {
  // `null` = fino all'ultima giornata di Serie A, che sa il server.
  const [finoA, setFinoA] = useState<number | null>(null);
  const { dato, errore, inCorso } = useCarica(
    () => api.calendario(finoA),
    [finoA],
  );
  const [scheda, setScheda] = useState<Scheda>("Weekend");

  if (inCorso) return <div className="fantasma alto" />;
  if (errore) return <div className="errore">{errore}</div>;
  if (!dato) return null;

  // Senza partite le altre schede non hanno niente da mostrare: non si creano
  // proprio. Una scheda che si apre su un messaggio di scuse è peggio di una
  // scheda che non c'è.
  const schede: Scheda[] = dato.senza_partite
    ? ["Weekend"]
    : ["Weekend", "Per giornata", "Scontri diretti", "Per squadra"];
  const attiva = schede.includes(scheda) ? scheda : "Weekend";

  return (
    <>
      <div className="intestazione-pagina">
        <h1>📅 Calendario</h1>
        <p>
          Tutti gli incroci della stagione: per giornata, faccia a faccia, o
          squadra per squadra.
        </p>
      </div>

      {dato.senza_partite ? (
        <div className="riquadro avviso" role="status">
          <strong>🗓️ Calendario non caricato.</strong> Le partite della lega
          non sono ancora state importate: qui sotto trovi comunque la
          corrispondenza fra i weekend di Serie A e le giornate della lega.
        </div>
      ) : (
        <div className="numeri">
          <div className="numero">
            <span className="etichetta">Squadre</span>
            <span className="valore">{dato.squadre.length}</span>
          </div>
          <div className="numero">
            <span className="etichetta">Giornate disputate</span>
            <span className="valore">
              {dato.giornate_disputate}/{dato.giornate_totali}
            </span>
          </div>
          <div className="numero">
            <span className="etichetta">Partite giocate</span>
            <span className="valore">
              {dato.partite_giocate}/{dato.partite.length}
            </span>
          </div>
        </div>
      )}

      <div className="schede">
        {schede.map((s) => (
          <button
            key={s}
            className={attiva === s ? "scheda attiva" : "scheda"}
            onClick={() => setScheda(s)}
          >
            {s}
          </button>
        ))}
      </div>

      {attiva === "Weekend" && (
        <div className="riquadro">
          <h2>A cosa corrisponde questo weekend</h2>
          <p className="prosa">
            Le due numerazioni non coincidono: la lega parte a stagione già
            iniziata, e un turno di coppa a eliminazione diretta fa slittare il
            campionato di una settimana. La coppa a gironi invece si accoda a
            fine campionato, e la F1 Rush corre sulle ultime giornate di Serie A
            senza spostare niente.
          </p>
          <div className="filtri">
            <div className="campo">
              <span className="etichetta-campo" id="prima-serie-a-etichetta">
                Il fantacampionato parte alla giornata di Serie A
              </span>
              <p className="valore-opzione" data-testid="prima-serie-a">
                <strong>{dato.prima_serie_a}ª</strong>{" "}
                {dato.posso_modificare ? (
                  <Link to="/lega">Cambia nelle regole della lega</Link>
                ) : (
                  <span className="didascalia">
                    La decide chi gestisce la lega.
                  </span>
                )}
              </p>
            </div>
            <div className="campo">
              <label htmlFor="fino-a">Fino alla giornata di Serie A</label>
              <input
                id="fino-a"
                type="number"
                min={dato.prima_serie_a}
                max={dato.serie_a_totali}
                value={finoA ?? dato.serie_a_totali}
                onChange={(e) => setFinoA(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="tabella-contenitore">
            <table className="tabella">
              <thead>
                <tr>
                  <th className="numerica">Weekend</th>
                  <th>Serie A</th>
                  <th>Nella lega</th>
                </tr>
              </thead>
              <tbody>
                {dato.weekend.map((w) => (
                  <tr key={w.numero}>
                    <td className="numerica tenue">{w.numero}</td>
                    <td>{w.serie_a}ª giornata</td>
                    <td className="forte">{w.nella_lega}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {!dato.gioca_coppa && (
            <p className="didascalia">
              La lega non gioca la Coppa Italia: campionato e Serie A restano
              allineati. Si attiva dalle impostazioni della lega.
            </p>
          )}
        </div>
      )}

      {attiva === "Per giornata" && (
        <div className="riquadro">
          <PerGiornata
            partite={dato.partite}
            totali={dato.giornate_totali}
            disputate={dato.giornate_disputate}
          />
        </div>
      )}

      {attiva === "Scontri diretti" && (
        <div className="riquadro">
          <ScontriDiretti partite={dato.partite} squadre={dato.squadre} />
        </div>
      )}

      {attiva === "Per squadra" && (
        <div className="riquadro">
          <PerSquadra partite={dato.partite} squadre={dato.squadre} />
        </div>
      )}
    </>
  );
}
