import { useMemo, useState } from "react";
import { ErroreApi, api, type Giocatore } from "../api";
import { milioni, useCarica } from "../carica";
import { IntestazioneOrdinabile } from "../intestazioneOrdinabile";
import { useOrdinamento } from "../ordinamento";

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
  const [soloSvincolati, setSoloSvincolati] = useState(false);
  // Le correzioni dello status Under 21 fatte da qui, per id: la riga cambia
  // subito, senza ricaricare cinquecento giocatori. Il valore vero è quello che
  // il server ha risposto.
  const [u21Cambiati, setU21Cambiati] = useState<Record<number, boolean>>({});
  const [erroreU21, setErroreU21] = useState<string | null>(null);

  const dal_server = dato?.giocatori;
  const tutti = useMemo(
    () =>
      (dal_server ?? []).map((g) =>
        g.id in u21Cambiati ? { ...g, u21: u21Cambiati[g.id] } : g,
      ),
    [dal_server, u21Cambiati],
  );

  async function segnaU21(g: Giocatore) {
    setErroreU21(null);
    try {
      const aggiornato = await api.impostaU21(g.id, !g.u21);
      setU21Cambiati((prima) => ({ ...prima, [g.id]: aggiornato.u21 }));
    } catch (guasto) {
      setErroreU21(
        guasto instanceof ErroreApi
          ? guasto.message
          : "Non riesco a contattare il server.",
      );
    }
  }

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
      if (soloSvincolati && g.squadra !== dato?.svincolato) return false;
      return true;
    });
  }, [tutti, cerca, club, ruolo, squadra, soloIta, soloU21, soloSvincolati, dato]);

  const { ordinate, colonna, direzione, imposta } = useOrdinamento(filtrati, {
    nome: (g) => g.nome,
    club: (g) => g.club,
    ruoli: (g) => g.ruoli.join("/"),
    squadra: (g) => g.squadra,
    anni: (g) => g.anni || null,
    ingaggio: (g) => g.ingaggio || null,
    nazionalita: (g) => g.nazionalita,
    u21: (g) => g.u21,
  });

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
          {dato.con_stipendio} con stipendio
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
        <label className="interruttore">
          <input
            type="checkbox"
            checked={soloSvincolati}
            onChange={(e) => setSoloSvincolati(e.target.checked)}
          />
          Solo svincolati
        </label>
      </div>

      <p className="didascalia conteggio">
        {filtrati.length} giocatori su {tutti.length}
      </p>
      {erroreU21 && (
        <div className="errore" role="alert">
          {erroreU21}
        </div>
      )}
      {dato.posso_modificare_u21 && (
        <p className="didascalia">
          Chi amministra la lega segna lo status Under 21 italiano toccando il
          cerchio nell'ultima colonna (valutato al 31 agosto, vale per tutta la
          stagione).
        </p>
      )}

      <div className="tabella-contenitore">
        <table className="tabella">
          <thead>
            <tr>
              {(
                [
                  ["nome", "Giocatore", undefined],
                  ["club", "Club", undefined],
                  ["ruoli", "Ruoli", undefined],
                  ["squadra", "Squadra", undefined],
                  ["anni", "Anni", "numerica"],
                  ["ingaggio", "Ingaggio", "numerica"],
                  ["nazionalita", "Nazionalità", undefined],
                  ["u21", "U21", "centrata"],
                ] as const
              ).map(([nome, etichetta, classe]) => (
                <IntestazioneOrdinabile
                  key={nome}
                  nome={nome}
                  attiva={colonna}
                  direzione={direzione}
                  onOrdina={imposta}
                  className={classe}
                >
                  {etichetta}
                </IntestazioneOrdinabile>
              ))}
            </tr>
          </thead>
          <tbody>
            {ordinate.map((g) => (
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
                <td className="centrata">
                  {dato.posso_modificare_u21 ? (
                    <button
                      type="button"
                      className="u21-tasto"
                      aria-pressed={g.u21}
                      aria-label={`${g.nome}: Under 21 italiano, ${g.u21 ? "sì" : "no"}. Premi per cambiare`}
                      onClick={() => segnaU21(g)}
                    >
                      {g.u21 ? "●" : "○"}
                    </button>
                  ) : g.u21 ? (
                    <span aria-label="Under 21 italiano">●</span>
                  ) : (
                    ""
                  )}
                </td>
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
