import { useState, type ReactNode } from "react";
import {
  ErroreApi,
  api,
  type CampoFile,
  type EsitoFile,
  type EsitoListoneImport,
  type EsitoRisultatiImport,
  type EsitoRoseImport,
  type FormatiImport,
  type ProblemaFile,
  type StatoRosaImport,
} from "../api";
import { milioni, useCarica } from "../carica";
import { leggiBase64, scarica } from "../file";

/**
 * Caricare i dati della lega da file: listone, rose del draft, risultati.
 *
 * **Prima l'anteprima, poi la conferma**, come su Streamlit. Un import che
 * scrive al primo clic, dopo un draft, vuol dire dieci rose sbagliate e
 * nessun modo di sapere quale riga le ha rotte: qui si guarda cosa entrerebbe
 * — riga per riga, con gli errori e la conformita' che ne risulterebbe — e
 * solo dopo si scrive.
 *
 * Il file si manda due volte, una per l'anteprima e una per la conferma. Il
 * server non ricorda niente fra le due: cosi' la conferma rivalida, e non
 * esiste il caso in cui si scrive un esito che nessuno ha controllato.
 *
 * Le colonne che ogni file vuole **arrivano dal server**, non sono scritte
 * qui: le prende dallo stesso modulo che poi legge il file.
 */

type Scheda = "Listone" | "Rose dal draft" | "Risultati";

const SCHEDE: Scheda[] = ["Listone", "Rose dal draft", "Risultati"];

// ---------------------------------------------------------------------------
// Pezzi comuni alle tre schede
// ---------------------------------------------------------------------------

function TabellaFormato({ campi, nota }: { campi: CampoFile[]; nota: string }) {
  return (
    <details className="formato">
      <summary>Le colonne che legge</summary>
      <div className="tabella-contenitore">
        <table className="tabella">
          <thead>
            <tr>
              <th>Colonna</th>
              <th className="centrata">Obbl.</th>
              <th>Esempio</th>
              <th>Serve a</th>
            </tr>
          </thead>
          <tbody>
            {campi.map((c) => (
              <tr key={c.nome}>
                <td className="forte">{c.nome}</td>
                <td className="centrata">{c.obbligatorio ? "sì" : "—"}</td>
                <td className="tenue">{c.esempio}</td>
                <td>{c.nota}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="didascalia">{nota}</p>
    </details>
  );
}

function Problemi({
  titolo,
  righe,
  grave,
}: {
  titolo: string;
  righe: ProblemaFile[];
  grave: boolean;
}) {
  if (righe.length === 0) return null;
  return (
    <details className={grave ? "problemi gravi" : "problemi"} open={grave}>
      <summary>
        {titolo} ({righe.length})
      </summary>
      <div className="tabella-contenitore">
        <table className="tabella">
          <thead>
            <tr>
              <th className="numerica">Riga</th>
              <th>Colonna</th>
              <th>Valore</th>
              <th>Problema</th>
            </tr>
          </thead>
          <tbody>
            {righe.map((p, indice) => (
              <tr key={`${p.riga}-${p.colonna}-${indice}`}>
                <td className="numerica">{p.riga || "—"}</td>
                <td className="tenue">{p.colonna}</td>
                <td className="tenue">{p.valore || "—"}</td>
                <td>{p.messaggio}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function Conteggi({ esito }: { esito: EsitoFile }) {
  return (
    <div className="numeri">
      <div className="numero">
        <span className="etichetta">Righe lette</span>
        <span className="valore">{esito.lette}</span>
      </div>
      <div className="numero">
        <span className="etichetta">Errori</span>
        <span className="valore">{esito.errori.length}</span>
      </div>
      <div className="numero">
        <span className="etichetta">Avvisi</span>
        <span className="valore">{esito.avvisi.length}</span>
      </div>
    </div>
  );
}

/**
 * Il riquadro di una scheda: scegli il file, guarda, conferma.
 *
 * Il file sta qui e non nel genitore: ogni scheda ne ha uno suo, e passando
 * da una all'altra non si perde quello che si era appena caricato.
 */
function Caricatore<T extends EsitoFile>({
  accetta,
  anteprima,
  scrivi,
  rendi,
  etichettaScrivi,
  extra,
}: {
  accetta: string;
  anteprima: (base64: string, nome: string) => Promise<T>;
  scrivi: (base64: string, nome: string) => Promise<{ messaggio: string }>;
  rendi: (esito: T) => ReactNode;
  etichettaScrivi: string;
  /** Comandi che cambiano *come* si scrive, mostrati prima del bottone. */
  extra?: ReactNode;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [esito, setEsito] = useState<T | null>(null);
  const [errore, setErrore] = useState<string | null>(null);
  const [fatto, setFatto] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  async function scegli(scelto: File | null) {
    setFile(scelto);
    setEsito(null);
    setErrore(null);
    setFatto(null);
    if (!scelto) return;

    setInCorso(true);
    try {
      setEsito(await anteprima(await leggiBase64(scelto), scelto.name));
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi
          ? guasto.message
          : String((guasto as Error)?.message ?? guasto),
      );
    } finally {
      setInCorso(false);
    }
  }

  async function conferma() {
    if (!file) return;
    setInCorso(true);
    setErrore(null);
    try {
      const riepilogo = await scrivi(await leggiBase64(file), file.name);
      setFatto(riepilogo.messaggio);
      // Via l'anteprima: quello che mostrava non e' piu' «cosa entrerebbe»,
      // e' entrato. Lasciarla li' con il bottone acceso invita a scrivere
      // due volte lo stesso file.
      setEsito(null);
      setFile(null);
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi
          ? guasto.message
          : "Non riesco a contattare il server.",
      );
    } finally {
      setInCorso(false);
    }
  }

  return (
    <>
      <label className="scegli-file">
        <input
          type="file"
          accept={accetta}
          onChange={(e) => scegli(e.target.files?.[0] ?? null)}
        />
        <span>{file ? `📄 ${file.name}` : "Scegli il file…"}</span>
      </label>

      {fatto && <div className="conferma">{fatto}</div>}
      {errore && (
        <div className="errore" role="alert">
          {errore}
        </div>
      )}
      {inCorso && <div className="fantasma" />}

      {esito && (
        <>
          <Conteggi esito={esito} />

          {esito.intestazioni_ignorate.length > 0 && (
            <p className="didascalia">
              Colonne ignorate perché non riconosciute:{" "}
              {esito.intestazioni_ignorate.join(", ")}
            </p>
          )}

          <Problemi
            titolo="Errori da correggere"
            righe={esito.errori}
            grave={true}
          />
          <Problemi titolo="Avvisi" righe={esito.avvisi} grave={false} />

          {rendi(esito)}

          {extra}

          <button
            className="principale"
            onClick={conferma}
            disabled={!esito.importabile || inCorso}
          >
            {inCorso ? "Scrivo…" : etichettaScrivi}
          </button>
          {!esito.importabile && (
            <p className="didascalia">Si importa quando non restano errori.</p>
          )}
        </>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Listone
// ---------------------------------------------------------------------------

function AnteprimaListone({ esito }: { esito: EsitoListoneImport }) {
  if (esito.righe.length === 0) return null;
  const senza = esito.lette - esito.con_stipendio;
  return (
    <>
      {esito.fonti.map((f) => (
        <p key={f} className="didascalia">
          {f}
        </p>
      ))}
      <p className="didascalia">
        {esito.club} squadre di Serie A. I giocatori già presenti mantengono
        contratto e, se il file non lo porta, anche l'ingaggio.
      </p>

      {/* I tre conti che decidono se metà regolamento funziona: senza
          stipendio il Salary Cap resta a zero, senza data di nascita lo
          status Under 21 non si può determinare. */}
      <div className="conti-import">
        <span className={esito.con_stipendio ? "pastiglia verde" : "pastiglia"}>
          {esito.con_stipendio} con lo stipendio
        </span>
        <span
          className={esito.con_data_nascita ? "pastiglia verde" : "pastiglia"}
        >
          {esito.con_data_nascita} con la data di nascita
        </span>
        <span
          className={esito.con_nazionalita ? "pastiglia verde" : "pastiglia"}
        >
          {esito.con_nazionalita} con la nazionalità
        </span>
      </div>

      {senza > 0 && esito.senza_stipendio.length > 0 && (
        <details className="formato">
          <summary>
            {esito.senza_stipendio.length} giocatori resterebbero senza
            stipendio
          </summary>
          <p className="didascalia">
            {esito.senza_stipendio.slice(0, 40).join(" · ")}
            {esito.senza_stipendio.length > 40 && " …"}
          </p>
        </details>
      )}

      <div className="tabella-contenitore">
        <table className="tabella">
          <thead>
            <tr>
              <th className="numerica">Id</th>
              <th>Giocatore</th>
              <th>Club</th>
              <th>Ruoli</th>
              <th className="numerica">Qt.</th>
              <th className="numerica">Ingaggio</th>
              <th>Nato</th>
              <th>Nazionalità</th>
            </tr>
          </thead>
          <tbody>
            {esito.righe.map((r) => (
              <tr key={r.id_ufficiale}>
                <td className="numerica tenue">{r.id_ufficiale}</td>
                <td className="forte">{r.nome}</td>
                <td>{r.club}</td>
                <td>{r.ruoli.join("/")}</td>
                <td className="numerica">{r.quotazione ?? "—"}</td>
                <td className="numerica">
                  {r.ingaggio > 0 ? milioni(r.ingaggio) : "—"}
                </td>
                <td className="tenue">{r.data_nascita ?? "—"}</td>
                <td className="tenue">{r.nazionalita || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/**
 * Cancellare tutto il listone: l'azione più distruttiva del sito.
 *
 * Porta via **anche i contratti**, cioè tutte le rose. La parola scritta a
 * mano non è un fastidio inventato: è l'unica cosa che distingue questo da un
 * bottone che prima o poi qualcuno preme per sbaglio.
 */
function SvuotaListone({ quanti }: { quanti: number }) {
  const [conferma, setConferma] = useState("");
  const [errore, setErrore] = useState<string | null>(null);
  const [fatto, setFatto] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  async function svuota() {
    setErrore(null);
    setInCorso(true);
    try {
      const esito = await api.svuotaListone(conferma);
      setFatto(esito.messaggio);
      setConferma("");
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi
          ? guasto.message
          : "Non riesco a contattare il server.",
      );
    } finally {
      setInCorso(false);
    }
  }

  return (
    <details className="formato">
      <summary>🗑️ Cancella tutto il listone</summary>
      <div className="riquadro avviso">
        ⚠️ Cancella tutti i {quanti} giocatori e, con loro, i contratti che li
        assegnano alle squadre. Le squadre restano, ma le rose si svuotano. Non
        si torna indietro.
      </div>
      <p className="didascalia">
        Per ricaricare un listone sbagliato non serve: basta caricare il file
        giusto con «Sostituisci il listone».
      </p>
      <div className="campo">
        <label htmlFor="svuota-conferma">Scrivi CANCELLA per confermare</label>
        <input
          id="svuota-conferma"
          value={conferma}
          placeholder="CANCELLA"
          onChange={(e) => setConferma(e.target.value)}
        />
      </div>
      {errore && (
        <div className="errore" role="alert">
          {errore}
        </div>
      )}
      {fatto && <div className="conferma">{fatto}</div>}
      <button
        className="principale"
        onClick={svuota}
        disabled={inCorso || conferma.trim().toUpperCase() !== "CANCELLA"}
      >
        {inCorso ? "Cancello…" : "Cancella il listone e tutte le rose"}
      </button>
    </details>
  );
}

function SchedaListone({ formati }: { formati: FormatiImport }) {
  const [sostituisci, setSostituisci] = useState(false);

  return (
    <div className="riquadro">
      <h2>Listone</h2>
      <p className="prosa">
        Vanno bene due file, e si riconoscono da soli — non devi dire quale stai
        caricando.
      </p>
      <p className="prosa">
        <strong>L'xlsx ufficiale di Fantacalcio.it</strong> (
        <code>Quotazioni_Fantacalcio_Stagione_*.xlsx</code>, foglio{" "}
        <strong>Tutti</strong>) porta anagrafica, ruoli e quotazioni. Stipendi,
        date di nascita e nazionalità non ce li ha: senza quelli il Salary Cap
        resta a zero e lo status Under 21 non si può determinare.
      </p>
      <p className="prosa">
        <strong>Il CSV completo</strong> li porta tutti e tre. È il file che si
        prepara in Excel mettendo insieme il listone e gli stipendi di Capology:
        scarica il modello qui sotto per vedere le colonne.
      </p>

      {/* La tabella descrive l'xlsx: le colonne del CSV stanno nel modello,
          che e' dove si va a guardarle davvero. */}
      <TabellaFormato
        campi={formati.campi_listone}
        nota={`Colonne dell'xlsx ufficiale. ${formati.nota_formato}`}
      />

      <button
        className="secondario"
        onClick={() =>
          scarica(
            "modello_listone_fantacalcio_nuovo.csv",
            formati.modello_listone,
          )
        }
      >
        ⬇️ Scarica il modello CSV
      </button>

      <Caricatore<EsitoListoneImport>
        accetta=".xlsx,.csv,.txt"
        anteprima={api.anteprimaListone}
        scrivi={(base64, nome) => api.importaListone(base64, nome, sostituisci)}
        etichettaScrivi="Importa il listone"
        rendi={(esito) => <AnteprimaListone esito={esito} />}
        extra={
          <label className="interruttore">
            <input
              type="checkbox"
              checked={sostituisci}
              onChange={(e) => setSostituisci(e.target.checked)}
            />
            <span>
              Sostituisci il listone
              <small>
                Chi non è nel file viene cancellato, e con lui il suo contratto.
                Serve quando il file precedente era sbagliato: per aggiungere
                stipendi un pezzo alla volta, lascialo spento.
              </small>
            </span>
          </label>
        }
      />

      {formati.giocatori_in_catalogo > 0 && (
        <SvuotaListone quanti={formati.giocatori_in_catalogo} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rose
// ---------------------------------------------------------------------------

function Conformita({ squadre }: { squadre: StatoRosaImport[] }) {
  if (squadre.length === 0) return null;
  const violazioni = squadre.flatMap((s) =>
    s.violazioni.map((v) => ({ squadra: s.squadra, ...v })),
  );

  return (
    <>
      <h3>Le rose sarebbero conformi al regolamento?</h3>
      <p className="didascalia">
        Verifica fatta prima di scrivere: se il draft ha lasciato qualcuno fuori
        dai paletti, si vede adesso.
      </p>

      <div className="tabella-contenitore">
        <table className="tabella">
          <thead>
            <tr>
              <th>Squadra</th>
              <th className="numerica">Rosa</th>
              <th className="numerica">U21</th>
              <th className="numerica">Portieri</th>
              <th className="numerica">Anni</th>
              <th className="numerica">Annuali</th>
              <th className="numerica">Spesa</th>
              <th className="numerica">Spazio</th>
              <th className="centrata">Conforme</th>
            </tr>
          </thead>
          <tbody>
            {squadre.map((s) => (
              <tr key={s.squadra}>
                <td className="forte">{s.squadra}</td>
                <td className="numerica">
                  {s.dimensione}/{s.limite_dimensione}
                </td>
                <td className="numerica">{s.slot_u21}</td>
                <td className="numerica">{s.portieri}</td>
                <td className="numerica">
                  {s.anni_impegnati}/{s.monte_anni}
                </td>
                <td className="numerica">
                  {s.contratti_annuali}/{s.annuali_richiesti}
                </td>
                <td className="numerica">{milioni(s.spesa_salariale)}</td>
                <td
                  className={
                    s.spazio_salariale < 0
                      ? "numerica misura sforata"
                      : "numerica misura"
                  }
                >
                  {milioni(s.spazio_salariale)}
                </td>
                <td className="centrata">{s.conforme ? "✅" : "⚠️"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {violazioni.length > 0 && (
        <div className="violazioni">
          <p className="didascalia">
            {violazioni.length} violazioni. Si importa comunque: vanno sanate
            prima della chiusura del mercato.
          </p>
          {violazioni.map((v, indice) => (
            <div
              key={`${v.squadra}-${v.codice}-${indice}`}
              className={v.bloccante ? "violazione blocca" : "violazione"}
            >
              <strong>{v.squadra}</strong>
              <span className="articolo">{v.articolo}</span>
              {v.messaggio}
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function AnteprimaRose({ esito }: { esito: EsitoRoseImport }) {
  if (esito.righe.length === 0) return null;
  return (
    <>
      <h3>Anteprima delle rose</h3>
      <div className="tabella-contenitore">
        <table className="tabella">
          <thead>
            <tr>
              <th>Squadra</th>
              <th>Giocatore</th>
              <th>Club</th>
              <th>Ruoli</th>
              <th className="numerica">Anni</th>
              <th className="numerica">Ingaggio</th>
            </tr>
          </thead>
          <tbody>
            {esito.righe.map((r) => (
              <tr key={r.riga}>
                <td>{r.squadra}</td>
                <td className="forte">{r.giocatore}</td>
                <td>{r.club || "—"}</td>
                <td>{r.ruoli.join("/")}</td>
                <td className="numerica">{r.anni}</td>
                <td className="numerica">{milioni(r.ingaggio)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Conformita squadre={esito.squadre} />
    </>
  );
}

function SchedaRose({ formati }: { formati: FormatiImport }) {
  const [sostituisci, setSostituisci] = useState(true);

  return (
    <div className="riquadro">
      <h2>Rose dal draft</h2>
      <p className="prosa">
        Chi appartiene a chi, una riga per giocatore: è il file che si compila
        dopo il draft.
      </p>
      {formati.giocatori_in_catalogo > 0 && (
        <p className="didascalia">
          Listone caricato ({formati.giocatori_in_catalogo} giocatori): puoi
          omettere <code>ruoli</code> e <code>club</code>, si ricavano dal nome.
        </p>
      )}

      <TabellaFormato campi={formati.campi_rose} nota={formati.nota_formato} />

      <button
        className="secondario"
        onClick={() =>
          scarica("modello_rose_fantacalcio_nuovo.csv", formati.modello_rose)
        }
      >
        ⬇️ Scarica il modello CSV
      </button>

      <Caricatore<EsitoRoseImport>
        accetta=".csv,.txt"
        anteprima={api.anteprimaRose}
        scrivi={(base64, nome) => api.importaRose(base64, nome, sostituisci)}
        etichettaScrivi="Importa le rose"
        rendi={(esito) => <AnteprimaRose esito={esito} />}
        extra={
          <label className="interruttore">
            <input
              type="checkbox"
              checked={sostituisci}
              onChange={(e) => setSostituisci(e.target.checked)}
            />
            <span>
              Sostituisci le rose esistenti
              <small>
                Dopo un draft il file è la situazione completa: le rose
                precedenti vengono azzerate. Le squadre mantengono identità e
                colori.
              </small>
            </span>
          </label>
        }
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Risultati
// ---------------------------------------------------------------------------

function AnteprimaRisultati({ esito }: { esito: EsitoRisultatiImport }) {
  if (esito.righe.length === 0) return null;
  return (
    <div className="tabella-contenitore">
      <table className="tabella">
        <thead>
          <tr>
            <th className="numerica">Giornata</th>
            <th>Casa</th>
            <th>Trasferta</th>
            <th className="numerica">Punti casa</th>
            <th className="numerica">Punti trasferta</th>
          </tr>
        </thead>
        <tbody>
          {esito.righe.map((r, indice) => (
            <tr key={`${r.giornata}-${r.casa}-${indice}`}>
              <td className="numerica">{r.giornata}</td>
              <td className="forte">{r.casa}</td>
              <td>{r.trasferta}</td>
              <td className="numerica">{r.punti_casa}</td>
              <td className="numerica">{r.punti_trasferta}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SchedaRisultati({ formati }: { formati: FormatiImport }) {
  return (
    <div className="riquadro">
      <h2>Risultati di giornata</h2>
      <p className="prosa">
        Una riga per partita, con i fantapunti di ciascuna squadra. I gol li
        calcola la lega dalle sue fasce: primo gol a {formati.soglia_primo_gol},
        poi uno ogni {formati.passo_gol}.
      </p>

      <TabellaFormato
        campi={formati.campi_risultati}
        nota={formati.nota_formato}
      />

      <button
        className="secondario"
        onClick={() =>
          scarica(
            "modello_risultati_fantacalcio_nuovo.csv",
            formati.modello_risultati,
          )
        }
      >
        ⬇️ Scarica il modello CSV
      </button>

      <Caricatore<EsitoRisultatiImport>
        accetta=".csv,.txt"
        anteprima={api.anteprimaRisultati}
        scrivi={api.importaRisultati}
        etichettaScrivi="Importa i risultati"
        rendi={(esito) => <AnteprimaRisultati esito={esito} />}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------

export function Importa() {
  const { dato, errore, inCorso } = useCarica(() => api.formatiImport(), []);
  const [scheda, setScheda] = useState<Scheda>("Rose dal draft");

  if (inCorso) return <div className="fantasma alto" />;
  if (errore) return <div className="errore">{errore}</div>;
  if (!dato) return null;

  // La voce di menu non compare a chi non importa, ma l'indirizzo si scrive
  // a mano: meglio una spiegazione di una pagina di bottoni che non vanno.
  if (!dato.posso_importare) {
    return (
      <div className="vuoto">
        <h1>📥 Importa dati</h1>
        <p>
          L'importazione è del presidente di lega (art. 1): riscrive rose,
          catalogo e risultati di tutti.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="intestazione-pagina">
        <h1>📥 Importa dati</h1>
        <p>
          Il draft si fa di persona: qui si carica il risultato. Prima
          l'anteprima con gli errori riga per riga, poi la conferma.
        </p>
      </div>

      <div className="schede">
        {SCHEDE.map((s) => (
          <button
            key={s}
            className={scheda === s ? "scheda attiva" : "scheda"}
            onClick={() => setScheda(s)}
          >
            {s}
          </button>
        ))}
      </div>

      {scheda === "Listone" && <SchedaListone formati={dato} />}
      {scheda === "Rose dal draft" && <SchedaRose formati={dato} />}
      {scheda === "Risultati" && <SchedaRisultati formati={dato} />}
    </>
  );
}
