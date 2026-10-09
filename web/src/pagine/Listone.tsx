import { useMemo, useState } from "react";
import { api, type Giocatore } from "../api";
import { milioni, useCarica } from "../carica";

/**
 * I filtri girano nel browser, non sul server.
 *
 * Sono cinquecento righe: mandarle tutte una volta e filtrarle qui vuol dire
 * che scrivere nella casella di ricerca non fa partire una richiesta a ogni
 * lettera. È esattamente quello che Streamlit non poteva dare — lì ogni
 * tasto era un rerun dell'intera pagina.
 */
export function Listone() {
  const { dato, errore, inCorso } = useCarica(() => api.listone(), []);

  const [cerca, setCerca] = useState("");
  const [club, setClub] = useState("");
  const [ruolo, setRuolo] = useState("");
  const [squadra, setSquadra] = useState("");
  const [soloIta, setSoloIta] = useState(false);
  const [soloU21, setSoloU21] = useState(false);

  const tutti = dato?.giocatori ?? [];

  const scelte = useMemo(() => {
    const club = new Set<string>();
    const ruoli = new Set<string>();
    const squadre = new Set<string>();
    for (const g of tutti) {
      if (g.club) club.add(g.club);
      g.ruoli.forEach((r) => ruoli.add(r));
      if (g.squadra) squadre.add(g.squadra);
    }
    return {
      club: [...club].sort(),
      ruoli: [...ruoli].sort(),
      squadre: [...squadre].sort(),
    };
  }, [tutti]);

  const filtrati = useMemo(() => {
    const testo = cerca.trim().toLowerCase();
    return tutti.filter((g: Giocatore) => {
      if (
        testo &&
        !g.nome.toLowerCase().includes(testo) &&
        !g.club.toLowerCase().includes(testo)
      )
        return false;
      if (club && g.club !== club) return false;
      if (ruolo && !g.ruoli.includes(ruolo)) return false;
      if (squadra && g.squadra !== squadra) return false;
      if (soloIta && !g.italiano) return false;
      if (soloU21 && !g.u21) return false;
      return true;
    });
  }, [tutti, cerca, club, ruolo, squadra, soloIta, soloU21]);

  if (inCorso) return <div className="fantasma alto" />;
  if (errore) return <div className="errore">{errore}</div>;
  if (!dato) return null;

  const svincolati = tutti.filter((g) => g.squadra === dato.svincolato).length;

  return (
    <>
      <div className="intestazione-pagina">
        <h1>Listone giocatori</h1>
        <p>
          {tutti.length} giocatori · {svincolati} svincolati ·{" "}
          {dato.con_stipendio} con stipendio · {dato.con_data_nascita} con data
          di nascita
        </p>
      </div>

      <div className="filtri">
        <input
          className="cerca"
          placeholder="Cerca nome o club…"
          value={cerca}
          onChange={(e) => setCerca(e.target.value)}
          aria-label="Cerca"
        />
        <select value={club} onChange={(e) => setClub(e.target.value)} aria-label="Club">
          <option value="">Tutti i club</option>
          {scelte.club.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select
          value={ruolo}
          onChange={(e) => setRuolo(e.target.value)}
          aria-label="Ruolo Mantra"
        >
          <option value="">Tutti i ruoli</option>
          {scelte.ruoli.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <select
          value={squadra}
          onChange={(e) => setSquadra(e.target.value)}
          aria-label="Squadra della lega"
        >
          <option value="">Tutte le squadre</option>
          {scelte.squadre.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <label className="interruttore">
          <input
            type="checkbox"
            checked={soloIta}
            onChange={(e) => setSoloIta(e.target.checked)}
          />
          Solo 🇮🇹
        </label>
        <label className="interruttore">
          <input
            type="checkbox"
            checked={soloU21}
            onChange={(e) => setSoloU21(e.target.checked)}
          />
          Solo U21
        </label>
      </div>

      <p className="didascalia conteggio">
        {filtrati.length} giocatori su {tutti.length}
      </p>

      <div className="tabella-contenitore">
        <table className="tabella">
          <thead>
            <tr>
              <th>Giocatore</th>
              <th>Club</th>
              <th>Ruoli</th>
              <th>Squadra</th>
              <th className="numerica">Anni</th>
              <th className="numerica">Ingaggio</th>
              <th>Nazionalità</th>
              <th className="numerica">Età</th>
              <th className="centrata">U21</th>
            </tr>
          </thead>
          <tbody>
            {filtrati.map((g) => (
              <tr key={g.id}>
                <td className="forte">{g.nome}</td>
                <td className="tenue">{g.club}</td>
                <td>
                  <span className="ruoli">{g.ruoli.join("/")}</span>
                </td>
                <td
                  className={g.squadra === dato.svincolato ? "tenue" : undefined}
                >
                  {g.squadra}
                </td>
                <td className="numerica">{g.anni || ""}</td>
                <td className="numerica">
                  {g.ingaggio ? milioni(g.ingaggio, 2) : ""}
                </td>
                <td className="tenue">
                  {g.italiano && "🇮🇹 "}
                  {g.nazionalita}
                </td>
                <td className="numerica">{g.eta ?? ""}</td>
                <td className="centrata">{g.u21 ? "●" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {filtrati.length === 0 && (
        <p className="vuoto">Nessun giocatore con questi filtri.</p>
      )}
    </>
  );
}
