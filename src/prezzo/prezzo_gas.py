from loguru import logger

from src.model import Offerta
from src.prezzo.abc import ABCPrice
from decimal import Decimal, ROUND_HALF_UP
from ..config import config  


# TODO: verifica cacolo dell'accisa
# TODO: calcolo per altre tipologie di offerte di gas
# TODO: verifica calcolo complessivo

class CalcolatoreAccisaGas:
    """
    Inferred le accise medie mensili proiettando un singolo mese 
    sull'intero anno solare tramite pesi stagionali.
    """
    
    # Percentuali medie di consumo mensile (Riscaldamento + Cottura + Acqua)
    PESI_MENSILI = {
        1:  Decimal('0.18'), 
        2:  Decimal('0.15'),
        3:  Decimal('0.12'),
        4:  Decimal('0.07'),
        5:  Decimal('0.04'),
        6:  Decimal('0.03'),
        7:  Decimal('0.02'), 
        8:  Decimal('0.02'),
        9:  Decimal('0.03'),
        10: Decimal('0.06'),
        11: Decimal('0.12'),
        12: Decimal('0.16')
    }
    # 2024 Tariffe Accisa Gas per Zona
    TARIFFE_ACCISA = {
        "CENTRO_NORD": [
            (Decimal('120'),  Decimal('0.0440')),
            (Decimal('480'),  Decimal('0.1750')),
            (Decimal('1560'), Decimal('0.1700')),
            (None,            Decimal('0.1860'))
        ],
        "SUD_MEZZOGIORNO": [
            (Decimal('120'),  Decimal('0.0380')),
            (Decimal('480'),  Decimal('0.1350')),
            (Decimal('1560'), Decimal('0.1200')),
            (None,            Decimal('0.1500'))
        ]
    }

    def __init__(self, zona: str = "CENTRO_NORD"):
        if zona not in self.TARIFFE_ACCISA:
            raise ValueError(f"Zona non valida. Scegli tra: {list(self.TARIFFE_ACCISA.keys())}")
        self.scaglioni = self.TARIFFE_ACCISA[zona]

    def stima_accisa_media(self, consumo_mensile: float, mese_riferimento: int) -> dict:
        """
        :param consumo_mensile: Smc consumati nel mese indicato
        :param mese_riferimento: Il mese (1-12) a cui si riferisce il consumo
        :return: Dizionario con stima annua, accisa totale e accisa media mensile
        """
        c_mese = Decimal(str(consumo_mensile))
        peso_mese = self.PESI_MENSILI.get(mese_riferimento)
        
        consumo_annuo_stimato = c_mese / peso_mese
        
        accisa_annua_totale = Decimal('0')
        progressivo_annuo = Decimal('0')
        
        for m in range(1, 13):
            consumo_del_mese = consumo_annuo_stimato * self.PESI_MENSILI[m]
            
            accisa_mese = self._calcola_accisa_puntuale(consumo_del_mese, progressivo_annuo)
            accisa_annua_totale += accisa_mese
            progressivo_annuo += consumo_del_mese

        accisa_media_mensile = accisa_annua_totale / Decimal('12')

        return {
            "consumo_annuo_inferred": float(consumo_annuo_stimato.quantize(Decimal('0.01'))),
            "accisa_totale_annua": float(accisa_annua_totale.quantize(Decimal('0.01'))),
            "accisa_media_mensile": float(accisa_media_mensile.quantize(Decimal('0.01'))),
            "metodologia": f"Basato su peso {float(peso_mese)*100}% per il mese {mese_riferimento}"
        }

    def _calcola_accisa_puntuale(self, c_mese, c_progressivo) -> Decimal:
        restante = c_mese
        partenza = c_progressivo
        totale = Decimal('0')
        lim_prec = Decimal('0')

        for lim, tar in self.scaglioni:
            if lim is not None and partenza >= lim:
                lim_prec = lim
                continue
            inizio = max(partenza, lim_prec)
            if lim is None:
                quota = restante
            else:
                quota = min(restante, lim - inizio)
            
            if quota > 0:
                totale += quota * tar
                restante -= quota
                partenza += quota
            if restante <= 0: break
            if lim is not None: lim_prec = lim
        return totale
    
class CalcolatoreTrasportoGas:
    """
    Stima i costi di trasporto + oneri di sistema.
    Allineato alle macro-zone fiscali (Centro-Nord e Sud-Mezzogiorno).
    """

    # nota: mega approssimazione per evitare di dover gestire troppe zone
    # in realta' le tariffe variano per zona piu' dettagliate
    QUOTE_FISSE_BASE = {
        "CENTRO_NORD":      Decimal("72.50"),
        "SUD_MEZZOGIORNO":  Decimal("79.40")
    }

    QUOTA_VARIABILE_RETE = Decimal("0.115")
    QUOTA_ONERI = Decimal("0.010")
    

    def __init__(self, zona: str = "CENTRO_NORD"):
        self.zona = zona.upper()
        if self.zona not in self.QUOTE_FISSE_BASE:
            self.zona = "CENTRO_NORD"
        logger.warning("Approssimazione grezza fatta per consumi annuali intorno ai 1000 smc e in sole 2 fasce zonali.")

    def stima_costo_mensile(self, consumo_mensile: Decimal) -> Decimal:
        """
        Calcola la quota fissa mensile e la quota variabile su base Smc.
        """
        quota_fissa_mensile = self.QUOTE_FISSE_BASE[self.zona] / Decimal("12")
        costo_variabile_smc = self.QUOTA_VARIABILE_RETE + self.QUOTA_ONERI
        quota_variabile = consumo_mensile * costo_variabile_smc

        return (quota_fissa_mensile + quota_variabile).quantize(
            Decimal("0.01"),
            ROUND_HALF_UP
        )
        
        
class PrezzoGas(ABCPrice):
    def __init__(self, offerta_gas: Offerta):
        self.offerta_gas = offerta_gas
        self.zona_geografica = config.get("zona_geografica")
        self.is_residente = config.get("residenza", "true").lower() == "true"
        self.consumo_mensile = Decimal(str(config.get("consumption_smc_monthly")))
        self.mese_rif = int(config.get("mese_riferimento", 1))
        self.morfologia_territorio = config.get("morfologia_territorio", "PIANURA")

        # Parametri tecnici
        self.pcs_ratio = Decimal(str(config.get("pcs", "0.03852"))) / Decimal("0.03852")
        
    @property
    def accisa_mensile_media(self) -> CalcolatoreAccisaGas:
        ca = CalcolatoreAccisaGas(zona=self.zona_geografica)   
        stima_accisa_media = ca.stima_accisa_media(
            float(self.consumo_mensile),
            self.mese_rif
        )
        return stima_accisa_media

    @property
    def trasporto_oneri_mensile(self) -> Decimal:
        ct = CalcolatoreTrasportoGas(
            zona=self.zona_geografica)
        return ct.stima_costo_mensile(self.consumo_mensile)
    
    def get_quota_materia(self, psv_val: Decimal) -> Decimal:
        """Calcola il costo della materia prima (variabile + fisso)"""
        fee = Decimal(str(getattr(self.offerta_gas, "fee_offerta_smc", 0) or 0))
        #TODO: capire se e' giusto che venga calcolato cosi' o ci sono altri modi
        prezzo_smc = (psv_val + fee)* self.pcs_ratio
        
        costo_var = prezzo_smc * self.consumo_mensile
        costo_fiss = self.offerta_gas.costi_fissi_anno / 12
        return costo_var + costo_fiss

    def get_quota_trasporto_e_oneri(self) -> Decimal:
        """Calcola i costi di rete e oneri di sistema (stabiliti da ARERA)"""
        calcolatore = CalcolatoreTrasportoGas(zona=self.zona_geografica)
        return calcolatore.stima_costo_mensile(self.consumo_mensile)        

    def get_quota_fiscale_media(self) -> dict:
        """
        Usa l'inferenza per calcolare l'accisa media e il tasso IVA medio proiettato.
        """
        accisa_media = self.accisa_mensile_media
        consumo_annuo = self.consumo_mensile * 12

        # Calcolo tasso IVA medio (proiettato su base annua per residenti)
        if not self.is_residente:
            tasso_iva = Decimal("0.22")
        else:
            # 10% fino a 480 Smc/anno, resto al 22%
            quota_10 = min(Decimal("1.0"), Decimal("480") / consumo_annuo) if consumo_annuo > 0 else Decimal("1.0")
            tasso_iva = (quota_10 * Decimal("0.10")) + ((1 - quota_10) * Decimal("0.22"))
            
        return {
            "accisa": accisa_media,
            "tasso_iva_medio": tasso_iva,
            "consumo_annuo_stimato": consumo_annuo
        }

    def _calcola_prezzo_finito(self, psv_val: float) -> Decimal:
        """Mette assieme i pezzi per calcolare il totale mensile ivato"""
        psv = Decimal(str(psv_val))
        
        # 1. Recupero le singole componenti
        materia = self.get_quota_materia(psv)
        trasporto_oneri = self.trasporto_oneri_mensile
        fisco = self.get_quota_fiscale_media()
        
        # 2. Somma imponibile (Materia + Rete + Accisa)
        imponibile = materia + trasporto_oneri + fisco["accisa"]
        
        # 3. Applicazione IVA
        totale = imponibile * (1 + fisco["tasso_iva_medio"])
        
        return totale.quantize(Decimal("0.01"), ROUND_HALF_UP)

    def calcola_tutto(self) -> dict:
        """Metodo principale per ottenere il report completo"""
        psv_medio = getattr(self.offerta_gas, "psv_index_eur_smc_mean", 0.50)
        
        return {
            "totale_mensile_medio": float(self._calcola_prezzo_finito(psv_medio)),
            "dettaglio_annuo": self.get_quota_fiscale_media()["consumo_annuo_stimato"]
        }
        
if __name__ == "__main__":
    # Creazione di un'istanza di Offerta per il Mercato Libero
    offerta_esempio = Offerta(
        nome_offerta="Trend Casa Gas",
        gestore="EcoEnergy S.p.A.",
        prezzo_stimato_offerta=None,
        prezzo_stimato_finita=None,
        tipologia_formula_offerta="Standard",
        tipologia_formula_finita="Standard",
        durata_mesi=12,
        costi_fissi_anno=102.0,
        fee_offerta=0.10,
        fee_finita=0.14,
        note="Offerta indicizzata al PSV_da mensile con pagamento SDD e bolletta web."
    )
    print(CalcolatoreTrasportoGas(zona="CENTRO_NORD").stima_costo_mensile(Decimal("83.33")))