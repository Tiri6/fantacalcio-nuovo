/**
 * Chi sta usando il sito, per tutta l'applicazione.
 *
 * All'avvio si chiede all'API chi siamo (`/api/io`): il cookie c'e' gia' o
 * non c'e', e il front-end non deve indovinarlo. E' il sostituto di
 * `ui.utente_corrente()`, con una differenza che vale la pena: qui
 * ricaricare la pagina **non** butta fuori, perche' il cookie sopravvive.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, type ChiSono, type Iscrizione } from "./api";

type Stato = {
  utente: ChiSono | null;
  /** Vero finche' non sappiamo ancora se c'e' una sessione. */
  inCorso: boolean;
  entra: (nomeUtente: string, password: string) => Promise<void>;
  /** Registrarsi fa entrare: l'utente ha appena scelto le credenziali. */
  iscriviti: (corpo: Iscrizione) => Promise<void>;
  esci: () => Promise<void>;
};

const Contesto = createContext<Stato | null>(null);

export function ConSessione({ children }: { children: ReactNode }) {
  const [utente, setUtente] = useState<ChiSono | null>(null);
  const [inCorso, setInCorso] = useState(true);

  useEffect(() => {
    let vivo = true;
    api
      .io()
      .then((chi) => vivo && setUtente(chi))
      // Un 401 qui e' la risposta normale di chi non e' ancora entrato, non
      // un guasto: si resta semplicemente fuori.
      .catch(() => vivo && setUtente(null))
      .finally(() => vivo && setInCorso(false));
    return () => {
      vivo = false;
    };
  }, []);

  const entra = useCallback(async (nomeUtente: string, password: string) => {
    setUtente(await api.entra(nomeUtente, password));
  }, []);

  const iscriviti = useCallback(async (corpo: Iscrizione) => {
    setUtente(await api.iscriviti(corpo));
  }, []);

  const esci = useCallback(async () => {
    await api.esci();
    setUtente(null);
  }, []);

  return (
    <Contesto.Provider value={{ utente, inCorso, entra, iscriviti, esci }}>
      {children}
    </Contesto.Provider>
  );
}

export function useSessione(): Stato {
  const stato = useContext(Contesto);
  if (!stato) throw new Error("useSessione va usato dentro <ConSessione>");
  return stato;
}
