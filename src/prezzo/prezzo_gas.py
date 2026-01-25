from loguru import logger

from src.model import Offerta, TipoFormula
from src.prezzo.abc import ABCPrice
from decimal import Decimal, ROUND_HALF_UP
from ..config import config  


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

    def stima_accisa_media(self, consumo_mensile_smc, mese_rif, consumo_annuo_reale=None):
        if consumo_annuo_reale:
            consumo_annuo = Decimal(str(consumo_annuo_reale))
        else:
            c_mese = Decimal(str(consumo_mensile_smc))
            peso = self.PESI_MENSILI[mese_rif]
            consumo_annuo = c_mese / peso

        accisa_tot = self._calcola_accisa_puntuale(consumo_annuo, Decimal("0"))
        return (accisa_tot / 12).quantize(Decimal("0.01"), ROUND_HALF_UP)

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

         
def calcola_iva_annua(imponibile_annuo, consumo_annuo, residente=True):
    if not residente:
        return imponibile_annuo * Decimal("0.22")

    soglia = Decimal("480")

    if consumo_annuo <= soglia:
        return imponibile_annuo * Decimal("0.10")

    quota10 = imponibile_annuo * (soglia / consumo_annuo)
    quota22 = imponibile_annuo - quota10

    return quota10 * Decimal("0.10") + quota22 * Decimal("0.22")         
         
   
class PrezzoGas(ABCPrice):
    def __init__(self, offerta_energia: Offerta):
        super().__init__(offerta_energia)
        self.zona_geografica = config.get("zona_geografica")
        self.is_residente = config.get("residenza", "true").lower() == "true"
        self.consumo_mensile_smc = Decimal(str(config.get("consumption_smc_monthly")))
        self.mese_rif = int(config.get("mese_riferimento", 1))
        self.consumo_annuo_smc = config.get("consumption_smc_yearly")
        # Parametri tecnici
        
        self.pcs_ratio = Decimal(str(self.pcs_locale_gj_smc)) / Decimal(str(self.pcs_standard_gj_smc))
        self.c_coeff = Decimal(str(config.get("c_coefficiente", "1.0")))
        self.psv_medio = Decimal(str(config.get("psv_eur_smc")))
        self.psv_worst = Decimal(str(config.get("psv_eur_smc_worst", "0.0")))
        logger.warning("Approssimazione del trasporto grezza fatta per consumi annuali intorno ai 1000 smc e in sole 2 fasce zonali.")
    
    @property
    def pcs_standard_gj_smc(self) -> Decimal:
        """Restituisce il potere calorifico superiore standard in GJ/Smc"""
        return Decimal("0.03852")
    
    @property
    def pcs_locale_gj_smc(self) -> Decimal:
        """Restituisce il potere calorifico superiore locale in GJ/Smc"""
        return Decimal(str(config.get("pcs_locale_gj_smc")))

    @property
    def trasporto_oneri_mensile(self) -> Decimal:
        """Calcola i costi di trasporto e oneri di sistema mensili"""
        ct = CalcolatoreTrasportoGas()
        return ct.stima_costo_mensile(self.consumo_mensile_smc)
    
    def stima_accisa_media(
                           self,
                           zona: str,
                           consumo_mensile_smc: float, 
                           mese_rif: int, 
                           consumo_annuo_reale: float = None):
        ca = CalcolatoreAccisaGas(zona=zona)
        return ca.stima_accisa_media(consumo_mensile_smc, mese_rif, consumo_annuo_reale=consumo_annuo_reale)
        
        
    def get_prezzo_materia_smc(
                             self, 
                             fee_smc: Decimal = None,
                             prezzo_stimato_smc: Decimal = None,
                             psv_val: float = 0.0,
                             tipo_formula: TipoFormula = None
                             ) -> Decimal:
        """Calcola il costo della materia prima (variabile + fisso)
        Viene calcolato come: 
        - Se formula COSTANTE: uso il prezzo_stimato_smc
        - Se formula INDICIZZATA: uso psv_val * pcs_ratio + fee_s
        """
        if fee_smc is None and prezzo_stimato_smc is None:
            return None
        
        fee_smc = Decimal(str(fee_smc)) if fee_smc is not None else None
        prezzo_stimato_smc = Decimal(str(prezzo_stimato_smc)) if prezzo_stimato_smc is not None else None
        
        if tipo_formula == TipoFormula.COSTANTE:
            prezzo_smc = prezzo_stimato_smc
        else:
            prezzo_smc = psv_val * self.pcs_ratio * self.c_coeff  + fee_smc 
        print("-------")
        print("materia:", prezzo_smc)
        print("---")
        prezzo_mensile = prezzo_smc * self.consumo_mensile_smc
        
        return prezzo_mensile.quantize(Decimal("0.01"), ROUND_HALF_UP)

    def _calcola_prezzo_mensile(self, fee_smc=None, prezzo_stimato_smc=None,
                                psv_val=0, costo_fisso_annuo=None,
                                tipo_formula=None):
        if fee_smc is None and prezzo_stimato_smc is None:
            return None
        materia = self.get_prezzo_materia_smc(
            fee_smc, prezzo_stimato_smc, Decimal(str(psv_val)), tipo_formula
        )

        trasporto = self.trasporto_oneri_mensile
        accisa = self.stima_accisa_media(zona=self.zona_geografica,
                                         consumo_mensile_smc=self.consumo_mensile_smc,
                                         mese_rif=self.mese_rif,
                                         consumo_annuo_reale=self.consumo_annuo_smc,
                                         )

        costo_fissi_vendita = Decimal(str(costo_fisso_annuo or 0)) / 12

        imponibile_mese = materia + trasporto + accisa + costo_fissi_vendita

        consumo_annuo = Decimal(str(self.consumo_annuo_smc))
        imponibile_annuo = imponibile_mese * 12

        iva_annua = calcola_iva_annua(imponibile_annuo, consumo_annuo, self.is_residente)

        totale_mensile = (imponibile_annuo + iva_annua) / 12

        return totale_mensile.quantize(Decimal("0.01"), ROUND_HALF_UP)
    
    def calcola_prezzo_offerta(self):
            return self._calcola_prezzo_mensile(
                fee_smc=self.offerta_energia.fee_offerta,
                prezzo_stimato_smc=self.offerta_energia.prezzo_fisso_offerta,
                psv_val=self.psv_medio,
                costo_fisso_annuo=self.offerta_energia.costi_fissi_anno,
                tipo_formula=self.offerta_energia.tipologia_formula_offerta
            )
        
    def calcola_prezzo_finita_medio(self) -> float:
        return self._calcola_prezzo_mensile(
            fee_smc=self.offerta_energia.fee_finita,
            prezzo_stimato_smc=self.offerta_energia.prezzo_fisso_finita,
            psv_val=self.psv_medio,
            costo_fisso_annuo=self.offerta_energia.costi_fissi_anno,
            tipo_formula=self.offerta_energia.tipologia_formula_finita
        )
        
        
    def calcola_prezzo_finita_peggiore(self) -> float:
        return self._calcola_prezzo_mensile(
            fee_smc=self.offerta_energia.fee_finita,
            prezzo_stimato_smc=self.offerta_energia.prezzo_fisso_finita,
            costo_fisso_annuo=self.offerta_energia.costi_fissi_anno,
            psv_val=self.psv_worst,
            tipo_formula=self.offerta_energia.tipologia_formula_finita
        )
        
    
        
if __name__ == "__main__":
    # Creazione di un'istanza di Offerta per il Mercato Libero
    offerta_esempio = Offerta(
        nome_offerta="Sorgenia Next Energy Smart Gas",
        gestore="Sorgenia S.p.A.",
        
        # Se l'offerta è indicizzata, usiamo le FEE e lasciamo il PREZZO STIMATO a None
        prezzo_fisso_offerta=0.37, 
        prezzo_fisso_finita=None,
        
        tipologia_formula_offerta="costante",
        tipologia_formula_finita="standard",
        
        durata_mesi=12,
        costi_fissi_anno=102,  # Corrisponde alla quota fissa (QVD)
        
        # Qui inseriamo lo spread (la fee) sopra l'indice di mercato
        fee_offerta=None,        # fee_smc (es. 0.15 €/SMC)
        fee_finita=0.15,         # fee comprensiva di eventuali perdite o margini extra
        
        note="Offerta con rata costante basata sul PSV. Include sconto fedeltà."
    )
    print(CalcolatoreTrasportoGas().stima_costo_mensile(Decimal("83.33")))
    print(CalcolatoreAccisaGas().stima_accisa_media(83.33, 1))
    
    prezzo_gas = PrezzoGas(offerta_esempio)
    print("Calcolo Prezzi Gas:")
    
    print("prezzo offerta: ", prezzo_gas.calcola_prezzo_offerta())
    print("prezzo finita medio: ", prezzo_gas.calcola_prezzo_finita_medio())
    print("prezzo finita peggiore: ", prezzo_gas.calcola_prezzo_finita_peggiore())