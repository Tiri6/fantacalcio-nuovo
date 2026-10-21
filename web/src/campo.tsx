/**
 * Il campo con le maglie, disegnato una volta sola per le pagine che lo
 * usano: Formazione, dove ci sono i nomi (e, mentre si compone, le maglie si
 * toccano per cambiare chi gioca), e Giornata, dove appena i voti arrivano
 * compaiono i punti.
 *
 * Le maglie accettano i campi in più senza chiederli: `punti`, `entrato`,
 * `senza_voto`, `adattato`, `sigla`. Chi disegna una formazione non ha i
 * primi e non deve inventarseli; chi disegna una giornata li ha e il campo li
 * mostra. **`<Campo>` senza `variante` resta com'è per Giornata**: il nuovo
 * aspetto (prato a strisce, maglia col badge del reparto) è opt-in.
 *
 * Qui non c'è regolamento: la lettera del reparto (`sigla`) e se uno gioca
 * fuori posizione (`adattato`) arrivano dal server.
 */

export type InCampo = {
  id: number;
  nome: string;
  ruoli: string[];
  /** P, D, C o A: la decide il server. */
  sigla?: string;
  punti?: number | null;
  entrato?: boolean;
  senza_voto?: boolean;
  adattato?: boolean;
};

/** Verde da 6 in su, rosso sotto la sufficienza piena, neutro in mezzo. */
function classePunti(punti: number): string {
  if (punti >= 6) return "punti buoni";
  if (punti < 5.5) return "punti scarsi";
  return "punti";
}

const NOMI_REPARTO: Record<string, string> = {
  P: "Portiere",
  D: "Difensore",
  C: "Centrocampista",
  A: "Attaccante",
};

/** La sagoma della maglia col reparto scritto dentro: lettera e colore. */
export function Badge({ sigla }: { sigla: string }) {
  return (
    <span
      className={`maglietta r-${sigla.toLowerCase()}`}
      title={NOMI_REPARTO[sigla]}
      aria-hidden="true"
    >
      <b>{sigla}</b>
    </span>
  );
}

function Maglia({
  giocatore,
  conSigla,
}: {
  giocatore: InCampo;
  conSigla: boolean;
}) {
  const classi = ["maglia"];
  if (giocatore.entrato) classi.push("entrato");
  if (giocatore.senza_voto && !giocatore.entrato) classi.push("senza-voto");

  const ruolo = [
    giocatore.ruoli.join("/"),
    giocatore.adattato ? "adattato" : "",
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className={classi.join(" ")}>
      {conSigla && giocatore.sigla && <Badge sigla={giocatore.sigla} />}
      <span className="nome">{giocatore.nome}</span>
      {ruolo && <span className="ruolo">{ruolo}</span>}
      {giocatore.punti !== null && giocatore.punti !== undefined && (
        <span className={classePunti(giocatore.punti)}>
          {giocatore.punti.toFixed(1)}
        </span>
      )}
    </div>
  );
}

export function Campo({
  reparti,
  variante,
}: {
  reparti: InCampo[][];
  /** `formazione`: prato a strisce e maglie col badge del reparto. */
  variante?: "formazione";
}) {
  const grande = variante === "formazione";
  return (
    <div className={grande ? "campo-gioco grande" : "campo-gioco"}>
      <Linee />
      {/* Dal server arrivano dalla porta all'attacco; nel campo grande
          l'attacco sta in alto, come nella composizione. */}
      {(grande ? [...reparti].reverse() : reparti).map((riga, indice) => (
        <div key={indice} className="reparto">
          {riga.map((g, posto) => (
            <Maglia key={`${g.id}-${posto}`} giocatore={g} conSigla={grande} />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Cerchio di centrocampo e, nel campo grande, le linee e le aree. */
function Linee() {
  return (
    <>
      <div className="cerchio" aria-hidden="true" />
      <div className="linea-meta" aria-hidden="true" />
      <div className="area alta" aria-hidden="true" />
      <div className="area bassa" aria-hidden="true" />
    </>
  );
}

// ---------------------------------------------------------------------------
// Il campo che si compone
// ---------------------------------------------------------------------------

export type PostoInCampo = {
  indice: number;
  /** Il reparto della casella (P, D, C, A), dal server. */
  sigla: string;
  /** I ruoli che la casella chiede, come «Dc/B». */
  etichetta: string;
  giocatore: InCampo | null;
  /** Gioca fuori ruolo e paga il malus (lo dice il server). */
  adattato: boolean;
  /** È schierato anche in un'altra casella. */
  doppio: boolean;
};

/**
 * Le maglie come tasti: toccandone una si apre la scelta di chi ci gioca.
 * Avvisi e adattamenti sono **badge sulla maglia** (testo, non solo colore):
 * «−1» per chi paga il malus, «2×» per chi sta in due caselle.
 */
export function CampoComposizione({
  righe,
  malus,
  onApri,
}: {
  righe: PostoInCampo[][];
  malus: number;
  onApri: (indice: number, tasto: HTMLButtonElement) => void;
}) {
  return (
    <div className="campo-gioco grande compone">
      <Linee />
      {righe.map((riga, i) => (
        <div key={i} className="reparto">
          {riga.map((posto) => {
            const g = posto.giocatore;
            const classi = ["maglia", "tasto"];
            if (posto.adattato) classi.push("adattata");
            if (posto.doppio) classi.push("doppia");
            const spiega = [
              `${NOMI_REPARTO[posto.sigla] ?? posto.etichetta}, casella ${posto.etichetta}`,
              g ? `${g.nome} (${g.ruoli.join("/")})` : "vuota",
              posto.adattato
                ? `fuori posizione, ${Math.abs(malus)} ${Math.abs(malus) === 1 ? "punto" : "punti"} in meno`
                : "",
              posto.doppio ? "schierato anche in un'altra casella" : "",
              "tocca per cambiare",
            ]
              .filter(Boolean)
              .join(", ");
            return (
              <button
                key={posto.indice}
                type="button"
                className={classi.join(" ")}
                aria-label={spiega}
                onClick={(e) => onApri(posto.indice, e.currentTarget)}
              >
                <Badge sigla={posto.sigla} />
                <span className="nome">{g ? g.nome : "Scegli"}</span>
                <span className="ruolo">{posto.etichetta}</span>
                {posto.adattato && (
                  <span className="distintivo ambra">−{Math.abs(malus)}</span>
                )}
                {posto.doppio && <span className="distintivo rosso">2×</span>}
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
}
