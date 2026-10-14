import { useEffect, useState, type FormEvent } from "react";
import {
  ErroreApi,
  api,
  type NuovaLega,
  type NuovaSquadra,
  type StatoOnboarding,
} from "../api";
import { useSessione } from "../sessione";

/**
 * I due passi fra «ho un account» e «vedo il mio fantacalcio».
 *
 * Streamlit li chiamava cancelli: fermavano la pagina finché non erano
 * superati. Qui è `App.tsx` a mostrare questa schermata al posto del sito, ma
 * la sequenza è la stessa — prima la lega, poi la squadra — e per la stessa
 * ragione: da lì in giù tutto il resto dà per scontato che ci sia una lega.
 *
 * Il secondo passo si **salta**: chi amministra e basta non è obbligato ad
 * avere una squadra, e obbligarlo lo chiuderebbe fuori dal suo gestionale.
 */

function Codice({ valore }: { valore: string }) {
  const [copiato, setCopiato] = useState(false);

  async function copia() {
    try {
      await navigator.clipboard.writeText(valore);
      setCopiato(true);
      setTimeout(() => setCopiato(false), 2000);
    } catch {
      // Senza permesso per gli appunti resta la selezione a mano: il codice
      // è lì, grande e leggibile.
    }
  }

  return (
    <div className="codice-invito">
      <code>{valore}</code>
      <button type="button" className="secondario" onClick={copia}>
        {copiato ? "✓ Copiato" : "Copia"}
      </button>
    </div>
  );
}

/** L'indirizzo completo da incollare in chat: chi lo apre trova il codice
 *  gia' scritto, e se non ha un account si registra e lo ritrova comunque. */
function linkInvito(codice: string): string {
  return `${window.location.origin}/entra/${codice}`;
}

function Unisciti({
  stato,
  codiceIniziale,
  onFatto,
}: {
  stato: StatoOnboarding;
  codiceIniziale: string;
  onFatto: () => void;
}) {
  const [codice, setCodice] = useState(codiceIniziale);
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  async function entra(quale: string) {
    setErrore(null);
    setInCorso(true);
    try {
      await api.unisciti(quale);
      onFatto();
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi ? guasto.message : "Non riesco a entrare.",
      );
    } finally {
      setInCorso(false);
    }
  }

  async function invia(evento: FormEvent) {
    evento.preventDefault();
    await entra(codice);
  }

  return (
    <form onSubmit={invia} noValidate>
      {/* Chi è stato invitato non deve andare a cercare il codice in chat:
          il sito sa già che lo aspettano. */}
      {stato.invito && (
        <div className="avviso corona">
          ✉️ Ti hanno invitato alla lega{" "}
          <strong>{stato.invito.lega_nome}</strong>.
          <button
            type="button"
            className="principale"
            disabled={inCorso}
            onClick={() => entra(stato.invito!.codice)}
          >
            Entra in «{stato.invito.lega_nome}»
          </button>
        </div>
      )}

      {!stato.esistono_leghe && (
        <div className="avviso">
          🕰️ Non esiste ancora nessuna lega. Creane una tu, oppure aspetta il
          codice da chi la sta creando.
        </div>
      )}

      <div className="campo">
        <label htmlFor="o-codice">Codice d'invito</label>
        <input
          id="o-codice"
          value={codice}
          onChange={(e) => setCodice(e.target.value.toUpperCase())}
          placeholder="ABCD-2345"
          autoCapitalize="characters"
          autoFocus
        />
      </div>
      <p className="porta-aiuto">
        Otto caratteri, te li passa chi ha creato la lega. Funziona anche il
        link che ti ha mandato.
      </p>

      {errore && (
        <div className="errore" role="alert">
          {errore}
        </div>
      )}

      <button
        className="principale"
        type="submit"
        disabled={inCorso || !codice.trim()}
      >
        {inCorso ? "Entro…" : "Entra nella lega"}
      </button>
    </form>
  );
}

function CreaLega({
  stato,
  onFatto,
}: {
  stato: StatoOnboarding;
  onFatto: () => void;
}) {
  const [campi, setCampi] = useState<NuovaLega>({
    nome: "",
    stagione: "2026/27",
    // Mantra, non la prima dell'elenco: e' la modalita' in cui si gioca, e
    // partire dall'altra fa creare la lega sbagliata a chi non guarda.
    modalita: "MANTRA",
    formato: stato.formati[0]?.nome ?? "ANDATA_RITORNO",
    partecipanti: 10,
    coppa_italia: false,
    f1_rush: false,
  });
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  function cambia<K extends keyof NuovaLega>(chiave: K, valore: NuovaLega[K]) {
    setCampi((precedenti) => ({ ...precedenti, [chiave]: valore }));
  }

  async function invia(evento: FormEvent) {
    evento.preventDefault();
    setErrore(null);
    setInCorso(true);
    try {
      await api.creaLega(campi);
      onFatto();
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi
          ? guasto.message
          : "Non riesco a creare la lega.",
      );
    } finally {
      setInCorso(false);
    }
  }

  return (
    <form onSubmit={invia} noValidate>
      <div className="campo">
        <label htmlFor="l-nome">Nome della lega</label>
        <input
          id="l-nome"
          value={campi.nome}
          onChange={(e) => cambia("nome", e.target.value)}
          placeholder="FantaCalcio NuoVo"
          autoFocus
          required
        />
      </div>

      <div className="coppia">
        <div className="campo">
          <label htmlFor="l-stagione">Stagione</label>
          <input
            id="l-stagione"
            value={campi.stagione}
            onChange={(e) => cambia("stagione", e.target.value)}
          />
        </div>
        <div className="campo">
          <label htmlFor="l-partecipanti">Quante squadre</label>
          <input
            id="l-partecipanti"
            type="number"
            min={2}
            max={20}
            value={campi.partecipanti}
            onChange={(e) => cambia("partecipanti", Number(e.target.value))}
          />
        </div>
      </div>

      <div className="coppia">
        <div className="campo">
          <label htmlFor="l-modalita">Modalità</label>
          <select
            id="l-modalita"
            value={campi.modalita}
            onChange={(e) => cambia("modalita", e.target.value)}
          >
            {stato.modalita.map((m) => (
              <option key={m.nome} value={m.nome}>
                {m.etichetta}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label htmlFor="l-formato">Formato</label>
          <select
            id="l-formato"
            value={campi.formato}
            onChange={(e) => cambia("formato", e.target.value)}
          >
            {stato.formati.map((f) => (
              <option key={f.nome} value={f.nome}>
                {f.etichetta}
              </option>
            ))}
          </select>
        </div>
      </div>

      <h3 className="porta-gruppo">Competizioni</h3>
      <div className="interruttori">
        <label>
          <input
            type="checkbox"
            checked={campi.coppa_italia}
            onChange={(e) => cambia("coppa_italia", e.target.checked)}
          />
          🥇 Coppa Italia{" "}
          <span className="tenue">(gironi a fine campionato, poi scontri)</span>
        </label>
        <label>
          <input
            type="checkbox"
            checked={campi.f1_rush}
            onChange={(e) => cambia("f1_rush", e.target.checked)}
          />
          🏁 F1 Rush Finale{" "}
          <span className="tenue">(ultime 6 giornate di Serie A)</span>
        </label>
      </div>

      <p className="porta-aiuto">
        Il resto delle regole — rosa, monte anni, Salary Cap, bonus, moduli —
        parte dai valori del regolamento e si cambia quando vuoi da
        «Impostazioni lega». Chiederti trenta campi adesso non servirebbe a
        niente.
      </p>

      {errore && (
        <div className="errore" role="alert">
          {errore}
        </div>
      )}

      <button
        className="principale"
        type="submit"
        disabled={inCorso || !campi.nome.trim()}
      >
        {inCorso ? "Creo la lega…" : "🏆 Crea la lega"}
      </button>
    </form>
  );
}

/**
 * «Di quale squadra sei presidente?»
 *
 * Quando la lega ha gia' caricato il calendario, le dieci squadre esistono
 * col loro nome e nessuna ha un presidente: chiedere «come si chiama la tua»
 * sarebbe la domanda sbagliata, e chi risponde si ritrova un'undicesima
 * squadra che nel campionato non gioca. Fondarne una resta possibile — lo
 * dice il bottone in fondo — ma non e' piu' la prima cosa che si vede.
 */
function SceltaSquadra({
  stato,
  onFatto,
  onFondaComunque,
  onSalta,
}: {
  stato: StatoOnboarding;
  onFatto: () => void;
  onFondaComunque: () => void;
  onSalta: () => void;
}) {
  const [scelta, setScelta] = useState<number | null>(null);
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  async function conferma() {
    if (scelta === null) return;
    setErrore(null);
    setInCorso(true);
    try {
      await api.rivendicaSquadra(scelta);
      onFatto();
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi
          ? guasto.message
          : "Non riesco a collegarti la squadra.",
      );
    } finally {
      setInCorso(false);
    }
  }

  const scelta_nome = stato.squadre_libere.find((s) => s.id === scelta)?.nome;

  return (
    <>
      <div className="sala-liberi squadre-da-prendere">
        {stato.squadre_libere.map((s) => (
          <button
            key={s.id}
            type="button"
            className={scelta === s.id ? "sala-libero scelto" : "sala-libero"}
            onClick={() => setScelta(s.id)}
          >
            <span className="forte">{s.nome}</span>
            <span className="tenue">
              {s.giocatori === 0
                ? "rosa ancora da fare"
                : `${s.giocatori} giocatori in rosa`}
            </span>
          </button>
        ))}
      </div>

      {errore && (
        <div className="errore" role="alert">
          {errore}
        </div>
      )}

      <button
        className="principale"
        type="button"
        onClick={conferma}
        disabled={scelta === null || inCorso}
      >
        {inCorso
          ? "Collego…"
          : scelta_nome
            ? `Sono il presidente di ${scelta_nome}`
            : "Scegli la tua squadra"}
      </button>

      <p className="porta-aiuto">
        Il nome non ti convince? Lo cambi dalla pagina «Identità», con colori e
        maglia. Quello che conta adesso è prendere la squadra giusta: le partite
        del calendario sono già sue.
      </p>

      <p className="porta-passaggio">
        <button type="button" onClick={onFondaComunque}>
          Nessuna di queste è la mia: ne fondo una nuova
        </button>
      </p>
      <p className="porta-passaggio">
        <button type="button" onClick={onSalta}>
          Lo faccio dopo, portami al sito
        </button>
      </p>
    </>
  );
}

function FondaSquadra({
  stato,
  onFatto,
  onSalta,
}: {
  stato: StatoOnboarding;
  onFatto: () => void;
  onSalta: () => void;
}) {
  const [campi, setCampi] = useState<NuovaSquadra>({
    nome: "",
    citta: "",
    stadio: "",
    curva: "",
    motto: "",
    colore_primario: "#2e7d32",
    colore_secondario: "#ffffff",
    stile_maglia: stato.stili_maglia[0]?.nome ?? "TINTA_UNITA",
  });
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  function cambia<K extends keyof NuovaSquadra>(
    chiave: K,
    valore: NuovaSquadra[K],
  ) {
    setCampi((precedenti) => ({ ...precedenti, [chiave]: valore }));
  }

  async function invia(evento: FormEvent) {
    evento.preventDefault();
    setErrore(null);
    setInCorso(true);
    try {
      await api.fondaSquadra(campi);
      onFatto();
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi
          ? guasto.message
          : "Non riesco a creare la squadra.",
      );
    } finally {
      setInCorso(false);
    }
  }

  return (
    <form onSubmit={invia} noValidate>
      <div className="campo">
        <label htmlFor="s-nome">Nome della squadra</label>
        <input
          id="s-nome"
          value={campi.nome}
          onChange={(e) => cambia("nome", e.target.value)}
          placeholder="Real Sporcaccioni"
          autoFocus
          required
        />
      </div>

      <div className="coppia">
        <div className="campo">
          <label htmlFor="s-citta">Città</label>
          <input
            id="s-citta"
            value={campi.citta}
            onChange={(e) => cambia("citta", e.target.value)}
            placeholder="Cuneo"
          />
        </div>
        <div className="campo">
          <label htmlFor="s-stadio">Stadio</label>
          <input
            id="s-stadio"
            value={campi.stadio}
            onChange={(e) => cambia("stadio", e.target.value)}
            placeholder="Arena del NuoVo"
          />
        </div>
      </div>

      <div className="coppia">
        <div className="campo">
          <label htmlFor="s-curva">Nome della curva</label>
          <input
            id="s-curva"
            value={campi.curva}
            onChange={(e) => cambia("curva", e.target.value)}
            placeholder="Curva Nord"
          />
        </div>
        <div className="campo">
          <label htmlFor="s-motto">Motto</label>
          <input
            id="s-motto"
            value={campi.motto}
            onChange={(e) => cambia("motto", e.target.value)}
            placeholder="Chi non salta un pari è"
          />
        </div>
      </div>

      <h3 className="porta-gruppo">Colori sociali</h3>
      <div className="terna">
        <div className="campo">
          <label htmlFor="s-primario">Primario</label>
          <input
            id="s-primario"
            type="color"
            value={campi.colore_primario}
            onChange={(e) => cambia("colore_primario", e.target.value)}
          />
        </div>
        <div className="campo">
          <label htmlFor="s-secondario">Secondario</label>
          <input
            id="s-secondario"
            type="color"
            value={campi.colore_secondario}
            onChange={(e) => cambia("colore_secondario", e.target.value)}
          />
        </div>
        <div className="campo">
          <label htmlFor="s-stile">Stile maglia</label>
          <select
            id="s-stile"
            value={campi.stile_maglia}
            onChange={(e) => cambia("stile_maglia", e.target.value)}
          >
            {stato.stili_maglia.map((s) => (
              <option key={s.nome} value={s.nome}>
                {s.etichetta}
              </option>
            ))}
          </select>
        </div>
      </div>

      <p className="porta-aiuto">
        Si cambia tutto dalla pagina «Identità», logo e maglia compresi. Il nome
        però è quello con cui ti vedranno gli altri.
      </p>

      {errore && (
        <div className="errore" role="alert">
          {errore}
        </div>
      )}

      <button
        className="principale"
        type="submit"
        disabled={inCorso || !campi.nome.trim()}
      >
        {inCorso ? "Fondo la squadra…" : "Fonda la squadra"}
      </button>

      {/* Rimandabile di proposito: chi amministra e basta non è obbligato ad
          avere una squadra. */}
      <p className="porta-passaggio">
        <button type="button" onClick={onSalta}>
          Lo faccio dopo, portami al sito
        </button>
      </p>
    </form>
  );
}

export function Onboarding({ onSalta }: { onSalta: () => void }) {
  const { aggiorna } = useSessione();
  const [stato, setStato] = useState<StatoOnboarding | null>(null);
  const [errore, setErrore] = useState<string | null>(null);
  const [scheda, setScheda] = useState<"unisciti" | "crea">("unisciti");
  const [creata, setCreata] = useState<{ nome: string; codice: string } | null>(
    null,
  );
  // Chi ha detto «nessuna di queste è la mia»: da lì in poi vede il modulo.
  const [fondaComunque, setFondaComunque] = useState(false);

  // Il codice può arrivare dal link d'invito: `/entra/ABCD-2345`. Si legge
  // dall'indirizzo e basta — nessuna rotta nuova da mantenere, e il link
  // funziona anche per chi non ha ancora l'account, perché dopo la
  // registrazione l'indirizzo è ancora quello.
  const dalLink = decodeURIComponent(
    window.location.pathname.match(/^\/entra\/(.+)$/)?.[1] ?? "",
  ).toUpperCase();

  /** Rilegge dove siamo arrivati, e con essa la sessione: entrando in una
   *  lega la riga dell'utente cambia, ed e' quella che decide se questa
   *  schermata deve ancora comparire. */
  async function ricarica() {
    try {
      setStato(await api.onboarding());
      await aggiorna();
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi
          ? guasto.message
          : "Non riesco a contattare il server.",
      );
    }
  }

  useEffect(() => {
    void ricarica();
    if (dalLink) setScheda("unisciti");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (errore && !stato) {
    return (
      <div className="porta">
        <section className="accesso">
          <div className="accesso-riquadro">
            <div className="errore">{errore}</div>
          </div>
        </section>
      </div>
    );
  }
  if (!stato) return <div className="fantasma alto" />;

  const serveLega = stato.serve === "lega";
  const scegliFraLeSue =
    !serveLega && !fondaComunque && stato.squadre_libere.length > 0;

  return (
    <div className="porta">
      <section className="porta-vetrina">
        <div className="porta-marchio">
          <span className="porta-stemma" aria-hidden="true">
            ⚽
          </span>
          <span>FantaCalcio NuoVo</span>
        </div>

        <h1>
          Ciao {stato.nome},
          <br />
          {serveLega
            ? "manca la lega"
            : scegliFraLeSue
              ? "di quale squadra sei presidente?"
              : "manca la squadra"}
        </h1>
        <p className="porta-richiamo">
          {serveLega
            ? "Entra in una lega che esiste già col codice che ti hanno passato, oppure creane una tua e invita gli amici."
            : scegliFraLeSue
              ? `Sei dentro ${stato.nome_lega}. Le squadre sono già nel calendario: scegli la tua.`
              : `Sei dentro ${stato.nome_lega}. Adesso fonda la tua squadra: nome, casa e colori.`}
        </p>

        {!serveLega && !creata && stato.codice_invito && (
          <div>
            <p className="porta-richiamo">Il codice da girare agli altri:</p>
            <Codice valore={stato.codice_invito} />
          </div>
        )}
      </section>

      <section className="accesso">
        <div className="accesso-riquadro">
          {creata ? (
            <>
              <h2>🏆 {creata.nome} è nata</h2>
              <p className="porta-spiega">
                Questo è il codice d'invito: giralo a chi deve entrare. Lo
                ritrovi sempre in «Impostazioni lega».
              </p>
              <Codice valore={creata.codice} />
              <p className="porta-aiuto">
                Oppure mandagli direttamente il link:
              </p>
              <Codice valore={linkInvito(creata.codice)} />
              <button
                className="principale"
                onClick={() => {
                  setCreata(null);
                  void ricarica();
                }}
              >
                Avanti
              </button>
            </>
          ) : serveLega ? (
            <>
              <div className="porta-schede" role="tablist">
                <button
                  type="button"
                  role="tab"
                  aria-selected={scheda === "unisciti"}
                  className={scheda === "unisciti" ? "scheda attiva" : "scheda"}
                  onClick={() => setScheda("unisciti")}
                >
                  🔑 Unisciti
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={scheda === "crea"}
                  className={scheda === "crea" ? "scheda attiva" : "scheda"}
                  onClick={() => setScheda("crea")}
                >
                  🏆 Crea una lega
                </button>
              </div>

              {scheda === "unisciti" ? (
                <>
                  <h2>Entra in una lega</h2>
                  <p className="porta-spiega">
                    Col codice che ti ha passato il presidente.
                  </p>
                  <Unisciti
                    stato={stato}
                    codiceIniziale={dalLink}
                    onFatto={ricarica}
                  />
                </>
              ) : (
                <>
                  <h2>Crea la tua lega</h2>
                  <p className="porta-spiega">
                    Ne diventi presidente: sarai tu a invitare gli altri.
                  </p>
                  <CreaLega
                    stato={stato}
                    onFatto={async () => {
                      const fresco = await api.onboarding();
                      setCreata({
                        nome: fresco.nome_lega,
                        codice: fresco.codice_invito,
                      });
                      setStato(fresco);
                    }}
                  />
                </>
              )}
            </>
          ) : scegliFraLeSue ? (
            <>
              <h2>Scegli la tua squadra</h2>
              <p className="porta-spiega">
                {stato.squadre_libere.length === 1
                  ? "Una sola aspetta ancora un presidente."
                  : `${stato.squadre_libere.length} squadre di ${stato.nome_lega} aspettano un presidente.`}
              </p>
              <SceltaSquadra
                stato={stato}
                onFatto={ricarica}
                onFondaComunque={() => setFondaComunque(true)}
                onSalta={onSalta}
              />
            </>
          ) : (
            <>
              <h2>Fonda la tua squadra</h2>
              <p className="porta-spiega">In {stato.nome_lega}.</p>
              <FondaSquadra
                stato={stato}
                onFatto={ricarica}
                onSalta={onSalta}
              />
            </>
          )}
        </div>
      </section>
    </div>
  );
}
