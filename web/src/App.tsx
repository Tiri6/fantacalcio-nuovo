import { useState } from "react";
import { BrowserRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";
import { Accesso } from "./pagine/Accesso";
import { Albo } from "./pagine/Albo";
import { Bacheca } from "./pagine/Bacheca";
import { Campionato } from "./pagine/Campionato";
import { Cruscotto } from "./pagine/Cruscotto";
import { Identita } from "./pagine/Identita";
import { Listone } from "./pagine/Listone";
import { Squadra } from "./pagine/Squadra";
import { Squadre } from "./pagine/Squadre";
import { ConSessione, useSessione } from "./sessione";

/**
 * Le voci stanno in sezioni, non in fila.
 *
 * Con tre pagine una barra orizzontale bastava; arrivando a quindici diventa
 * un elenco in cui non si trova niente. Le sezioni sono le stesse di
 * Streamlit — chi passa da un sito all'altro ritrova le cose dov'erano.
 */
const SEZIONI = [
  {
    titolo: "Lega",
    voci: [
      { a: "/bacheca", icona: "📣", testo: "Bacheca" },
      { a: "/cruscotto", icona: "🏠", testo: "Cruscotto" },
      { a: "/campionato", icona: "🏆", testo: "Campionato" },
      { a: "/albo", icona: "🏛️", testo: "Albo d'oro" },
    ],
  },
  {
    titolo: "Squadre e giocatori",
    voci: [
      { a: "/squadre", icona: "🛡️", testo: "Squadre" },
      { a: "/giocatori", icona: "📋", testo: "Listone" },
      { a: "/identita", icona: "🎨", testo: "Identità" },
    ],
  },
];

function Navigazione({ onScelto }: { onScelto: () => void }) {
  return (
    <nav className="navigazione">
      {SEZIONI.map((sezione) => (
        <div key={sezione.titolo} className="sezione">
          <h2>{sezione.titolo}</h2>
          {sezione.voci.map((voce) => (
            <NavLink
              key={voce.a}
              to={voce.a}
              onClick={onScelto}
              className={({ isActive }) => (isActive ? "voce attiva" : "voce")}
            >
              <span className="icona">{voce.icona}</span>
              {voce.testo}
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  );
}

function Intelaiatura() {
  const { utente, esci } = useSessione();
  // Su schermo stretto il menu parte chiuso: occuperebbe tutta la pagina.
  const [menuAperto, setMenuAperto] = useState(false);
  if (!utente) return null;

  return (
    <div className={menuAperto ? "impianto menu-aperto" : "impianto"}>
      <header className="testata">
        <button
          className="apri-menu"
          onClick={() => setMenuAperto((aperto) => !aperto)}
          aria-label="Menu"
        >
          ☰
        </button>
        <div className="marchio">
          FantaCalcio <span>NuoVo</span>
        </div>
        <button className="esci" onClick={esci}>
          Esci, {utente.nome}
        </button>
      </header>

      <aside className="fianco">
        <Navigazione onScelto={() => setMenuAperto(false)} />
      </aside>

      <main>
        <Routes>
          <Route path="/bacheca" element={<Bacheca />} />
          <Route path="/cruscotto" element={<Cruscotto />} />
          <Route path="/campionato" element={<Campionato />} />
          <Route path="/albo" element={<Albo />} />
          <Route path="/squadre" element={<Squadre />} />
          <Route path="/squadre/:id" element={<Squadra />} />
          <Route path="/giocatori" element={<Listone />} />
          <Route path="/identita" element={<Identita />} />
          {/* La bacheca è la pagina d'ingresso: chi entra vuole sapere cosa
              è successo, non leggere una tabella di contratti. */}
          <Route path="*" element={<Navigate to="/bacheca" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function Instradamento() {
  const { utente, inCorso } = useSessione();

  // Finche' non sappiamo se c'e' una sessione non si disegna niente: un
  // lampo della schermata d'accesso a chi e' gia' dentro sembra un guasto.
  if (inCorso) return null;

  return utente ? <Intelaiatura /> : <Accesso />;
}

export default function App() {
  return (
    <BrowserRouter>
      <ConSessione>
        <Instradamento />
      </ConSessione>
    </BrowserRouter>
  );
}
