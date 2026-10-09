import { Link } from "react-router-dom";
import { api, type Squadra } from "../api";
import { milioni, useCarica } from "../carica";

function Scheda({ squadra }: { squadra: Squadra }) {
  const { colori } = squadra;
  return (
    <Link to={`/squadre/${squadra.id}`} className={`scheda${squadra.e_mia ? " mia" : ""}`}>
      <div
        className="striscia"
        style={{
          background: `linear-gradient(90deg, ${colori.primario}, ${colori.secondario})`,
        }}
      />
      <h2>
        {squadra.nome}
        {squadra.e_mia && <span className="pastiglia-mia">LA TUA</span>}
      </h2>
      <p className="presidente">{squadra.presidente || "—"}</p>
      <p className="motto">{squadra.motto}</p>

      <div className="numeri">
        <div className="numero">
          <span className="etichetta">Rosa</span>
          <span className="valore">{squadra.giocatori}</span>
        </div>
        <div className="numero">
          <span className="etichetta">Anni</span>
          <span className="valore">{squadra.anni_impegnati}</span>
        </div>
        <div className="numero">
          <span className="etichetta">Ingaggi</span>
          <span className="valore">{milioni(squadra.monte_ingaggi)}</span>
        </div>
      </div>
    </Link>
  );
}

export function Squadre() {
  const { dato: squadre, errore } = useCarica(() => api.squadre(), []);

  return (
    <>
      <div className="intestazione-pagina">
        <h1>Squadre</h1>
        <p>
          {squadre
            ? `${squadre.length} squadre iscritte alla lega.`
            : "Carico le squadre…"}
        </p>
      </div>

      {errore && <div className="errore">{errore}</div>}

      {/* Scheletri invece di uno spinner: la pagina non salta quando i dati
          arrivano, perche' lo spazio era gia' quello giusto. */}
      {!squadre && !errore && (
        <div className="caricamento">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="fantasma" />
          ))}
        </div>
      )}

      {squadre && (
        <div className="griglia">
          {squadre.map((s) => (
            <Scheda key={s.id} squadra={s} />
          ))}
        </div>
      )}
    </>
  );
}
