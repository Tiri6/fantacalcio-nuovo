import { Link, useParams } from "react-router-dom";
import { api, type GiocatoreInRosa, type Violazione } from "../api";
import { milioni, useCarica } from "../carica";

function Numero({
  etichetta,
  valore,
  nota,
  sfora,
  quota,
}: {
  etichetta: string;
  valore: string;
  nota?: string;
  sfora?: boolean;
  quota?: number;
}) {
  return (
    <div className="riquadro">
      <span className="etichetta">{etichetta}</span>
      <span className={`valore${sfora ? " sfora" : ""}`}>{valore}</span>
      {nota && <span className="nota">{nota}</span>}
      {quota !== undefined && (
        <div className="barra">
          <div
            className={sfora ? "piena sfora" : "piena"}
            style={{ width: `${Math.min(100, Math.max(0, quota * 100))}%` }}
          />
        </div>
      )}
    </div>
  );
}

function RigaViolazione({ v }: { v: Violazione }) {
  return (
    <li className={v.bloccante ? "blocco" : "avviso"}>
      <strong>{v.articolo}</strong> {v.messaggio}
      {/* Di quanto sfora, non solo che sfora: e' la regola del progetto. */}
      {v.valore !== null && v.limite !== null && (
        <span className="scarto">
          {v.valore} su {v.limite}
        </span>
      )}
    </li>
  );
}

function Rosa({
  rosa,
  riferimento,
}: {
  rosa: GiocatoreInRosa[];
  riferimento: string;
}) {
  if (rosa.length === 0) {
    return (
      <p className="vuoto">
        Rosa vuota. I giocatori si assegnano dalla pagina «Draft».
      </p>
    );
  }
  const giorno = new Date(riferimento).toLocaleDateString("it-IT");
  return (
    <>
      <div className="tabella-contenitore">
        <table className="tabella">
          <thead>
            <tr>
              <th>Giocatore</th>
              <th>Club</th>
              <th>Ruoli</th>
              <th>Nazionalità</th>
              <th className="numerica">Età</th>
              <th className="centrata">U21</th>
              <th className="numerica">Anni</th>
              <th className="numerica">Ingaggio</th>
            </tr>
          </thead>
          <tbody>
            {rosa.map((g) => (
              <tr key={g.id}>
                <td className="forte">
                  {g.nome}
                  {g.prolungato && (
                    <span className="segno" title="Lodo Corti: già prolungato">
                      ↗
                    </span>
                  )}
                </td>
                <td className="tenue">{g.club}</td>
                <td>
                  <span className="ruoli">{g.ruoli.join("/")}</span>
                </td>
                <td className="tenue">
                  {g.italiano && <span title="Italiano">🇮🇹 </span>}
                  {g.nazionalita}
                </td>
                <td className="numerica">{g.eta ?? "—"}</td>
                <td className="centrata">{g.u21 ? "●" : ""}</td>
                <td className={`numerica${g.in_scadenza ? " scadenza" : ""}`}>
                  {g.anni_residui}
                </td>
                <td className="numerica">{milioni(g.ingaggio, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="didascalia">
        Under 21 valutati al {giorno} · ingaggi dalla fonte Capology · ↗ già
        prolungato (Lodo Corti)
      </p>
    </>
  );
}

export function Squadra() {
  const { id } = useParams();
  const numero = Number(id);
  const { dato, errore, inCorso } = useCarica(() => api.squadra(numero), [numero]);

  if (inCorso) return <div className="fantasma alto" />;
  if (errore) return <div className="errore">{errore}</div>;
  if (!dato) return null;

  const c = dato.conti;
  const capResiduo = c.limite_cap - c.monte_ingaggi;

  return (
    <>
      <Link to="/squadre" className="indietro">
        ← Tutte le squadre
      </Link>

      <header className="testata-squadra">
        <div
          className="striscia"
          style={{
            background: `linear-gradient(90deg, ${dato.colori.primario}, ${dato.colori.secondario})`,
          }}
        />
        <div>
          <h1>
            {dato.nome}
            {dato.e_mia && <span className="pastiglia-mia">LA TUA</span>}
          </h1>
          {dato.motto && <p className="motto">{dato.motto}</p>}
        </div>
        <dl className="anagrafica">
          <div>
            <dt>Presidente</dt>
            <dd>{dato.presidente || "—"}</dd>
          </div>
          <div>
            <dt>Stadio</dt>
            <dd>{dato.stadio || "—"}</dd>
          </div>
          <div>
            <dt>Città</dt>
            <dd>{dato.citta || "—"}</dd>
          </div>
          <div>
            <dt>Curva</dt>
            <dd>{dato.curva || "—"}</dd>
          </div>
          {dato.anno_fondazione && (
            <div>
              <dt>Fondata nel</dt>
              <dd>{dato.anno_fondazione}</dd>
            </div>
          )}
        </dl>
      </header>

      <section>
        <h2 className="sezione">🏆 Bacheca</h2>
        {dato.titoli.length === 0 ? (
          <p className="vuoto">
            Ancora nessun titolo. La bacheca si riempie da sola quando chi
            amministra registra un vincitore nell'albo d'oro.
          </p>
        ) : (
          <div className="pastiglie">
            {dato.titoli.map((t, i) => (
              <span key={i} className="pastiglia">
                {t.icona} {t.etichetta} {t.stagione}
              </span>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="sezione">Conti</h2>
        <div className="riquadri">
          <Numero
            etichetta="Rosa"
            valore={String(c.giocatori)}
            nota={`su ${c.limite_dimensione}${c.slot_u21 ? ` (+${c.slot_u21} U21)` : ""}`}
            sfora={c.giocatori > c.limite_dimensione}
            quota={c.giocatori / Math.max(c.limite_dimensione, 1)}
          />
          <Numero
            etichetta="Anni di contratto"
            valore={`${c.anni_impegnati}/${c.monte_anni}`}
            nota={`${c.monte_anni - c.anni_impegnati} liberi`}
            sfora={c.anni_impegnati > c.monte_anni}
            quota={c.anni_impegnati / Math.max(c.monte_anni, 1)}
          />
          <Numero
            etichetta="Cap residuo"
            valore={milioni(capResiduo)}
            nota={`su ${milioni(c.limite_cap, 0)}`}
            sfora={capResiduo < 0}
            quota={c.monte_ingaggi / Math.max(c.limite_cap, 1)}
          />
          <Numero
            etichetta="Italiani"
            valore={String(c.italiani)}
            nota={`di cui ${c.u21} Under 21`}
          />
        </div>
      </section>

      <section>
        <h2 className="sezione">Rosa</h2>
        <Rosa rosa={dato.rosa} riferimento={dato.riferimento_u21} />
      </section>

      <section>
        <h2 className="sezione">Conformità al regolamento</h2>
        {dato.violazioni.length === 0 ? (
          <p className="conforme">✅ Nessuna violazione: rosa conforme.</p>
        ) : (
          <ul className="violazioni">
            {dato.violazioni.map((v) => (
              <RigaViolazione key={v.codice} v={v} />
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
