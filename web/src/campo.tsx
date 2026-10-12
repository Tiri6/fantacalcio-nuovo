/**
 * Il campo con le maglie, disegnato una volta sola per le due pagine che lo
 * usano: Formazione, dove ci sono solo i nomi, e Giornata, dove appena i voti
 * arrivano compaiono i punti.
 *
 * Le maglie accettano i campi in più senza chiederli: `punti`, `entrato`,
 * `senza_voto`, `adattato`. Chi disegna una formazione non li ha e non deve
 * inventarseli; chi disegna una giornata li ha e il campo li mostra.
 */

export type InCampo = {
  id: number;
  nome: string;
  ruoli: string[];
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

function Maglia({ giocatore }: { giocatore: InCampo }) {
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

export function Campo({ reparti }: { reparti: InCampo[][] }) {
  return (
    <div className="campo-gioco">
      <div className="cerchio" aria-hidden="true" />
      {reparti.map((riga, indice) => (
        <div key={indice} className="reparto">
          {riga.map((g, posto) => (
            <Maglia key={`${g.id}-${posto}`} giocatore={g} />
          ))}
        </div>
      ))}
    </div>
  );
}
