"""La chat sul regolamento: cosa legge il modello, e cosa gli si manda.

Due cose non si possono provare qui e vanno dette: **la qualita' delle
risposte** (la da' il modello, non il codice) e **la chiamata vera** (costa
soldi e una chiave). Quello che si prova e' tutto il resto, che e' anche
l'unico posto dove un errore passerebbe inosservato:

- che il dossier contenga **ogni** parametro, cosi' un lodo nuovo arriva alla
  chat senza che nessuno si ricordi di aggiungerlo a mano;
- che ci arrivino i valori *di questa lega*, non i default;
- che la richiesta sia fatta come l'API la vuole, blocco per blocco;
- che un errore dell'SDK diventi una frase leggibile invece di un traceback.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import date

import anthropic
import httpx2
import pytest

from fantacalcio.assistente import (
    CHIAVE_SECRET,
    ISTRUZIONI,
    LIMITE_DOMANDA,
    MODELLO,
    TURNI_DI_STORIA,
    AssistenteNonConfigurato,
    AssistenteNonRaggiungibile,
    DomandaNonValida,
    Messaggio,
    costruisci_messaggi,
    crea_client,
    punti_aperti_del_progetto,
    rispondi,
    scheda_regolamento,
)
from fantacalcio.leghe import ModalitaSostituzioni, OpzioniLega
from fantacalcio.regole import ParametriLega

DATA_U21 = date(2026, 8, 31)


def scheda(parametri=None, opzioni=None, **kw) -> str:
    return scheda_regolamento(
        parametri or ParametriLega(),
        opzioni or OpzioniLega(),
        nome_lega=kw.pop("nome_lega", "FantaCalcio NuoVo"),
        data_u21=kw.pop("data_u21", DATA_U21),
        **kw,
    )


# --- il client finto --------------------------------------------------------


class _FlussoFinto:
    def __init__(self, pezzi: list[str], errore: Exception | None) -> None:
        self._pezzi = pezzi
        self._errore = errore

    def __enter__(self) -> _FlussoFinto:
        if self._errore is not None:
            raise self._errore
        return self

    def __exit__(self, *_) -> bool:
        return False

    @property
    def text_stream(self):
        yield from self._pezzi


class _MessaggiFinti:
    def __init__(self, pezzi: list[str], errore: Exception | None) -> None:
        self._pezzi = pezzi
        self._errore = errore
        self.chiamate: list[dict] = []

    def stream(self, **argomenti) -> _FlussoFinto:
        self.chiamate.append(argomenti)
        return _FlussoFinto(self._pezzi, self._errore)


class ClientFinto:
    """Il minimo che `rispondi` usa: `client.messages.stream(...)`."""

    def __init__(
        self, pezzi: list[str] | None = None, errore: Exception | None = None
    ) -> None:
        self.messages = _MessaggiFinti(pezzi or ["Sono ", "tre ", "pezzi."], errore)

    @property
    def ultima_chiamata(self) -> dict:
        return self.messages.chiamate[-1]


def _errore_http(classe, stato: int):
    richiesta = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    if classe is anthropic.APIConnectionError:
        return classe(request=richiesta)
    return classe(
        "errore di prova",
        response=httpx2.Response(stato, request=richiesta),
        body=None,
    )


# --- il dossier -------------------------------------------------------------


class TestNienteRestaFuoriDalDossier:
    """Se un parametro non e' nella scheda, per la chat non esiste.

    E' il difetto che nessuno noterebbe: la lega vota un lodo, il sito lo
    applica, e la chat continua a rispondere con la regola di prima.
    """

    @pytest.mark.parametrize("campo", [c.name for c in fields(ParametriLega)])
    def test_ogni_parametro_del_regolamento_e_citato(self, campo):
        assert campo in scheda()

    @pytest.mark.parametrize("campo", [c.name for c in fields(OpzioniLega)])
    def test_ogni_scelta_della_lega_e_citata(self, campo):
        assert campo in scheda()


class TestIValoriSonoQuelliDellaLega:
    def test_un_salary_cap_cambiato_arriva_nella_scheda(self):
        testo = scheda(ParametriLega(salary_cap=120_000_000.0))
        assert "120.000.000" in testo
        assert "100.000.000" not in testo

    def test_le_soglie_degli_annuali_sono_scritte_per_fascia(self):
        assert "31-33 giocatori -> 11 annuali" in scheda()

    def test_la_modalita_di_sostituzione_scelta_e_spiegata(self):
        testo = scheda(
            opzioni=OpzioniLega(modalita_sostituzioni=ModalitaSostituzioni.MASTER)
        )
        assert "Master" in testo
        assert ModalitaSostituzioni.MASTER.spiegazione in testo

    def test_la_data_u21_e_quella_passata_non_oggi(self):
        assert "31/08/2026" in scheda()

    def test_il_nome_della_lega_compare(self):
        assert "Lega dei Matti" in scheda(nome_lega="Lega dei Matti")


class TestLeRegoleDelMantra:
    def test_la_tabella_delle_sostituzioni_c_e_tutta(self):
        testo = scheda()
        for casella in ("Por", "Pc", "Dc", "W"):
            assert f"- casella {casella}:" in testo

    def test_il_portiere_resta_isolato_anche_nella_scheda(self):
        riga = next(r for r in scheda().splitlines() if r.startswith("- casella Por:"))
        # Nessun giocatore di movimento copre il portiere: tutta la riga e' NO
        # tranne la casella con se' stesso.
        assert riga.count("=NO") == 11
        assert "Por=OK" in riga

    def test_i_moduli_hanno_le_loro_caselle(self):
        assert "- 3-4-3: Por |" in scheda()

    def test_la_legenda_degli_asterischi_c_e(self):
        testo = scheda()
        assert "*** = OK se lo ammette, vietato nel 4-1-4-1" in testo


class TestPuntiAperti:
    def test_senza_punti_aperti_la_sezione_non_compare(self):
        assert "ancora aperti" not in scheda()

    def test_con_i_punti_aperti_la_sezione_c_e(self):
        testo = scheda(punti_aperti="## 2. La Draft Lottery e' da decidere")
        assert "ancora aperti" in testo
        assert "Draft Lottery" in testo

    def test_solo_spazi_non_contano_come_punti_aperti(self):
        assert "ancora aperti" not in scheda(punti_aperti="   \n  ")

    def test_il_file_del_progetto_si_legge(self):
        # Viaggia col repository: se sparisse, la chat perderebbe l'unica
        # fonte su cosa il sito ipotizza dove il regolamento tace.
        assert "Punti aperti del regolamento" in punti_aperti_del_progetto()


class TestLeIstruzioniRestanoIdentiche:
    """Il primo blocco di sistema e' il prefisso della cache: non deve muoversi."""

    def test_non_contengono_niente_di_questa_lega(self):
        for pezzo in ("FantaCalcio", "66", "2026"):
            assert pezzo not in ISTRUZIONI

    def test_dicono_di_non_inventare(self):
        assert "Non inventare" in ISTRUZIONI


# --- la conversazione -------------------------------------------------------


class TestCostruzioneDeiMessaggi:
    def test_la_domanda_nuova_sta_in_fondo(self):
        messaggi = costruisci_messaggi("E adesso?", [])
        assert messaggi == [{"role": "user", "content": "E adesso?"}]

    def test_lo_storico_diventa_botta_e_risposta(self):
        storico = [Messaggio("utente", "Prima"), Messaggio("assistente", "Risposta")]
        assert costruisci_messaggi("Poi", storico) == [
            {"role": "user", "content": "Prima"},
            {"role": "assistant", "content": "Risposta"},
            {"role": "user", "content": "Poi"},
        ]

    def test_si_comincia_sempre_da_un_turno_dell_utente(self):
        # Tagliando lo storico si puo' restare con una risposta in testa:
        # l'API la rifiuta, quindi si scarta.
        storico = [Messaggio("assistente", "Risposta orfana")]
        assert costruisci_messaggi("Domanda", storico)[0]["role"] == "user"

    def test_lo_storico_lungo_si_taglia(self):
        storico = [
            Messaggio("utente" if i % 2 == 0 else "assistente", f"turno {i}")
            for i in range(40)
        ]
        messaggi = costruisci_messaggi("Ultima", storico)
        assert len(messaggi) == TURNI_DI_STORIA + 1
        assert messaggi[0]["role"] == "user"

    def test_i_turni_vuoti_non_si_mandano(self):
        storico = [Messaggio("utente", "  "), Messaggio("assistente", "Vera")]
        assert costruisci_messaggi("Ora", storico) == [{"role": "user", "content": "Ora"}]

    def test_una_domanda_vuota_non_parte(self):
        with pytest.raises(DomandaNonValida):
            costruisci_messaggi("   ", [])

    def test_una_domanda_troppo_lunga_si_ferma_e_lo_dice(self):
        with pytest.raises(DomandaNonValida, match=str(LIMITE_DOMANDA)):
            costruisci_messaggi("a" * (LIMITE_DOMANDA + 1), [])

    def test_gli_spazi_intorno_si_tolgono(self):
        assert costruisci_messaggi("  Ciao  ", [])[0]["content"] == "Ciao"


class TestMessaggio:
    def test_un_ruolo_inventato_non_passa(self):
        with pytest.raises(ValueError, match="Ruolo non previsto"):
            Messaggio("sistema", "testo")


class TestClient:
    def test_senza_chiave_si_dice_quale_secret_manca(self):
        with pytest.raises(AssistenteNonConfigurato, match=CHIAVE_SECRET):
            crea_client(None)

    def test_una_chiave_vuota_conta_come_assente(self):
        with pytest.raises(AssistenteNonConfigurato):
            crea_client("")


# --- la richiesta -----------------------------------------------------------


class TestRichiesta:
    def test_la_risposta_arriva_a_pezzi(self):
        client = ClientFinto(["Il ", "primo ", "gol ", "a 66."])
        assert "".join(rispondi("Quando?", [], scheda(), client)) == "Il primo gol a 66."

    def _chiamata(self, **kw) -> dict:
        client = ClientFinto()
        list(
            rispondi(kw.pop("domanda", "Domanda"), [], kw.pop("testo", scheda()), client)
        )
        return client.ultima_chiamata

    def test_il_modello_e_quello_dichiarato(self):
        assert self._chiamata()["model"] == MODELLO

    def test_il_sistema_e_in_due_blocchi_istruzioni_poi_scheda(self):
        sistema = self._chiamata(testo="LA SCHEDA")["system"]
        assert [b["text"] for b in sistema] == [ISTRUZIONI, "LA SCHEDA"]

    def test_la_scheda_viaggia_in_cache_e_le_istruzioni_la_precedono(self):
        # Il prefisso stabile davanti, il pezzo grosso marcato: dalla seconda
        # domanda in poi la scheda non si paga piu'.
        sistema = self._chiamata()["system"]
        assert "cache_control" not in sistema[0]
        assert sistema[1]["cache_control"] == {"type": "ephemeral"}

    def test_c_e_un_tetto_alla_risposta(self):
        assert self._chiamata()["max_tokens"] > 0

    def test_la_domanda_e_l_ultimo_messaggio(self):
        messaggi = self._chiamata(domanda="Quanti annuali?")["messages"]
        assert messaggi[-1] == {"role": "user", "content": "Quanti annuali?"}

    def test_una_domanda_vuota_non_chiama_l_api(self):
        client = ClientFinto()
        with pytest.raises(DomandaNonValida):
            list(rispondi("", [], scheda(), client))
        assert client.messages.chiamate == []


class TestErroriTradotti:
    """Un traceback dell'SDK in pagina e' un sito rotto: qui diventa una frase."""

    @pytest.mark.parametrize(
        ("classe", "stato", "pezzo"),
        [
            (anthropic.AuthenticationError, 401, CHIAVE_SECRET),
            (anthropic.RateLimitError, 429, "Troppe domande"),
            (anthropic.APIConnectionError, 0, "Non riesco a raggiungere"),
            (anthropic.APIStatusError, 503, "503"),
        ],
    )
    def test_ogni_errore_diventa_leggibile(self, classe, stato, pezzo):
        client = ClientFinto(errore=_errore_http(classe, stato))
        with pytest.raises(AssistenteNonRaggiungibile, match=pezzo):
            list(rispondi("Domanda", [], scheda(), client))

    def test_un_errore_vero_del_codice_non_si_nasconde(self):
        # Solo gli errori dell'API si traducono: un difetto nostro deve
        # arrivare fino ai log, non travestirsi da problema di rete.
        client = ClientFinto(errore=ZeroDivisionError("difetto nostro"))
        with pytest.raises(ZeroDivisionError):
            list(rispondi("Domanda", [], scheda(), client))
