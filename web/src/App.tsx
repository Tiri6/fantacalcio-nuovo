import { BrowserRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";
import { Accesso } from "./pagine/Accesso";
import { Identita } from "./pagine/Identita";
import { Listone } from "./pagine/Listone";
import { Squadra } from "./pagine/Squadra";
import { Squadre } from "./pagine/Squadre";
import { ConSessione, useSessione } from "./sessione";

function Intelaiatura() {
  const { utente, esci } = useSessione();
  if (!utente) return null;

  return (
    <>
      <header className="testata">
        <div className="marchio">
          FantaCalcio <span>NuoVo</span>
        </div>
        <nav className="navigazione">
          <NavLink
            to="/squadre"
            className={({ isActive }) => (isActive ? "attiva" : undefined)}
          >
            Squadre
          </NavLink>
          <NavLink
            to="/giocatori"
            className={({ isActive }) => (isActive ? "attiva" : undefined)}
          >
            Listone
          </NavLink>
          <NavLink
            to="/identita"
            className={({ isActive }) => (isActive ? "attiva" : undefined)}
          >
            Identità
          </NavLink>
          <button className="esci" onClick={esci}>
            Esci, {utente.nome}
          </button>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/squadre" element={<Squadre />} />
          <Route path="/squadre/:id" element={<Squadra />} />
          <Route path="/giocatori" element={<Listone />} />
          <Route path="/identita" element={<Identita />} />
          <Route path="*" element={<Navigate to="/squadre" replace />} />
        </Routes>
      </main>
    </>
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
