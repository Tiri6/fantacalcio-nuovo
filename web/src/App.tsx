import { useState } from "react";
import {
  BrowserRouter,
  NavLink,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";
import { Accesso } from "./pagine/Accesso";
import { Onboarding } from "./pagine/Onboarding";
import { Albo } from "./pagine/Albo";
import { Bacheca } from "./pagine/Bacheca";
import { Calendario } from "./pagine/Calendario";
import { Campionato } from "./pagine/Campionato";
import { ChatRegolamento } from "./pagine/ChatRegolamento";
import { Coppa } from "./pagine/Coppa";
import { Cruscotto } from "./pagine/Cruscotto";
import { F1Rush } from "./pagine/F1Rush";
import { Formazione } from "./pagine/Formazione";
import { Giornata } from "./pagine/Giornata";
import { Identita } from "./pagine/Identita";
import { Importa } from "./pagine/Importa";
import { Lega } from "./pagine/Lega";
import { Listone } from "./pagine/Listone";
import { Profilo } from "./pagine/Profilo";
import { Regolamento } from "./pagine/Regolamento";
import { Sala } from "./pagine/Sala";
import { Scambi } from "./pagine/Scambi";
import { Squadra } from "./pagine/Squadra";
import { Squadre } from "./pagine/Squadre";
import { ConSessione, useSessione } from "./sessione";
import type { ChiSono } from "./api";

/**
 * Le voci stanno in sezioni, non in fila.
 *
 * Con tre pagine una barra orizzontale bastava; arrivando a quindici diventa
 * un elenco in cui non si trova niente. Le sezioni sono le stesse di
 * Streamlit — chi passa da un sito all'altro ritrova le cose dov'erano.
 */
type Voce = {
  a: string;
  icona: string;
  testo: string;
  /** Quando c'e', la voce compare solo se torna vero. */
  soloSe?: (utente: ChiSono) => boolean;
};

const SEZIONI: { titolo: string; voci: Voce[] }[] = [
  {
    titolo: "Lega",
    voci: [
      { a: "/bacheca", icona: "📣", testo: "Bacheca" },
      { a: "/cruscotto", icona: "🏠", testo: "Cruscotto" },
      { a: "/formazione", icona: "📋", testo: "Formazione" },
      { a: "/giornata", icona: "⚔️", testo: "Giornata" },
      { a: "/campionato", icona: "🏆", testo: "Campionato" },
      // Coppa e F1 Rush ci sono solo se la lega le gioca: una voce che
      // parla di una competizione inesistente e' peggio di una mancante.
      {
        a: "/coppa",
        icona: "🥇",
        testo: "Coppa Italia",
        soloSe: (u) => u.gioca_coppa,
      },
      {
        a: "/f1-rush",
        icona: "🏁",
        testo: "F1 Rush",
        soloSe: (u) => u.gioca_f1_rush,
      },
      { a: "/calendario", icona: "📅", testo: "Calendario" },
      { a: "/albo", icona: "🏛️", testo: "Albo d'oro" },
      { a: "/regolamento", icona: "📖", testo: "Regolamento" },
      { a: "/regolamento/chat", icona: "💬", testo: "Chat sul regolamento" },
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
  {
    titolo: "Mercato",
    voci: [
      { a: "/sala", icona: "🎙️", testo: "Draft Room" },
      { a: "/scambi", icona: "🤝", testo: "Scambi" },
    ],
  },
  {
    titolo: "Impostazioni",
    voci: [
      { a: "/profilo", icona: "👤", testo: "Il mio profilo" },
      // Riscrive rose, catalogo e risultati di tutti: e' del presidente
      // (art. 1), e a chi non la puo' usare non si mostra.
      {
        a: "/importa",
        icona: "📥",
        testo: "Importa dati",
        soloSe: (u) => u.puo_importare,
      },
      { a: "/lega", icona: "⚙️", testo: "La lega" },
    ],
  },
];

function Navigazione({
  utente,
  onScelto,
}: {
  utente: ChiSono;
  onScelto: () => void;
}) {
  return (
    <nav className="navigazione">
      {SEZIONI.map((sezione) => (
        <div key={sezione.titolo} className="sezione">
          <h2>{sezione.titolo}</h2>
          {sezione.voci
            .filter((voce) => !voce.soloSe || voce.soloSe(utente))
            .map((voce) => (
              <NavLink
                key={voce.a}
                to={voce.a}
                onClick={onScelto}
                className={({ isActive }) =>
                  isActive ? "voce attiva" : "voce"
                }
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
        <Navigazione utente={utente} onScelto={() => setMenuAperto(false)} />
      </aside>

      <main>
        <Routes>
          <Route path="/bacheca" element={<Bacheca />} />
          <Route path="/cruscotto" element={<Cruscotto />} />
          <Route path="/formazione" element={<Formazione />} />
          <Route path="/giornata" element={<Giornata />} />
          <Route path="/campionato" element={<Campionato />} />
          <Route path="/coppa" element={<Coppa />} />
          <Route path="/f1-rush" element={<F1Rush />} />
          <Route path="/calendario" element={<Calendario />} />
          <Route path="/regolamento" element={<Regolamento />} />
          <Route path="/regolamento/chat" element={<ChatRegolamento />} />
          <Route path="/albo" element={<Albo />} />
          <Route path="/squadre" element={<Squadre />} />
          <Route path="/squadre/:id" element={<Squadra />} />
          <Route path="/giocatori" element={<Listone />} />
          <Route path="/identita" element={<Identita />} />
          <Route path="/sala" element={<Sala />} />
          <Route path="/scambi" element={<Scambi />} />
          <Route path="/profilo" element={<Profilo />} />
          <Route path="/importa" element={<Importa />} />
          <Route path="/lega" element={<Lega />} />
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
  // Chi amministra e basta puo' rimandare la squadra: la scelta vale per
  // questa visita, e al giro dopo il sito glielo richiede. E' voluto —
  // un presidente senza squadra deve poter entrare, ma e' anche vero che
  // nove volte su dieci se l'e' solo dimenticata.
  const [saltaSquadra, setSaltaSquadra] = useState(false);

  // Finche' non sappiamo se c'e' una sessione non si disegna niente: un
  // lampo della schermata d'accesso a chi e' gia' dentro sembra un guasto.
  if (inCorso) return null;
  if (!utente) return <Accesso />;

  // I due cancelli, nello stesso ordine di Streamlit: prima la lega, poi la
  // squadra. Si decidono da `ChiSono`, che il server rilegge a ogni
  // richiesta: non serve una chiamata in piu' per sapere a che punto siamo.
  const serveLega = utente.lega_id === null;
  const serveSquadra = utente.squadra_id === null && !saltaSquadra;
  if (serveLega || serveSquadra) {
    return <Onboarding onSalta={() => setSaltaSquadra(true)} />;
  }

  return <Intelaiatura />;
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
