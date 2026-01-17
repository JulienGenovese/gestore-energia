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

    def stima_accisa_media(self, consumo_mensile: float, mese_riferimento: int) -> float:
        """
        :param consumo_mensile: Smc consumati nel mese indicato
        :param mese_riferimento: Il mese (1-12) a cui si riferisce il consumo
        :return: Accisa media mensile
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

        return accisa_media_mensile

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
            
class PrezzoGas(ABCPrice):
    def __init__(self, offerta_gas: Offerta):
        self.offerta_gas = offerta_gas
        self.zona_geografica = config.get("zona_geografica")
        self.is_residente = config.get("residenza", "true").lower() == "true"
        self.consumo_mensile = Decimal(str(config.get("consumption_smc_monthly")))
        self.mese_rif = int(config.get("mese_riferimento", 1))

        # Parametri tecnici
        self.pcs_ratio = Decimal(str(config.get("pcs", "0.03852"))) / Decimal("0.03852")
        self.psv_medio = Decimal(str(config.get("psv_eur_smc", "0.0")))
        self.psv_worst = Decimal(str(config.get("psv_eur_smc_worst", "0.0")))
        logger.warning("Approssimazione del trasporto grezza fatta per consumi annuali intorno ai 1000 smc e in sole 2 fasce zonali.")

    @property
    def accisa_mensile_media(self) -> CalcolatoreAccisaGas:
        """
        Calcola l'accisa media mensile usando l'inferenza.
        """
        ca = CalcolatoreAccisaGas(zona=self.zona_geografica)   
        stima_accisa_media = ca.stima_accisa_media(
            float(self.consumo_mensile),
            self.mese_rif
        )
        return stima_accisa_media

    @property
    def trasporto_oneri_mensile(self) -> Decimal:
        """Calcola i costi di trasporto e oneri di sistema mensili"""
        ct = CalcolatoreTrasportoGas(
            zona=self.zona_geografica)
        return ct.stima_costo_mensile(self.consumo_mensile)
        
    @property 
    def iva_mensile_media(self) -> float:
        """
        Usa l'inferenza per calcolare l'accisa media e il tasso IVA medio proiettato.
        """
        consumo_annuo = self.consumo_mensile * 12

        # Calcolo tasso IVA medio (proiettato su base annua per residenti)
        if not self.is_residente:
            tasso_iva = Decimal("0.22")
        else:
            # 10% fino a 480 Smc/anno, resto al 22%
            quota_10 = min(Decimal("1.0"), Decimal("480") / consumo_annuo) if consumo_annuo > 0 else Decimal("1.0")
            tasso_iva = (quota_10 * Decimal("0.10")) + ((1 - quota_10) * Decimal("0.22"))
            
        return tasso_iva
        
    def get_prezzo_materia_smc(
                             self, 
                             fee_smc: Decimal = None,
                             prezzo_stimato_smc: Decimal = None,
                             psv_val: float = 0.0,
                             tipo_formula: TipoFormula = None
                             ) -> Decimal:
        """Calcola il costo della materia prima (variabile + fisso)"""
        
        assert (fee_smc is None) != (prezzo_stimato_smc is None), \
            "Devi fornire esattamente uno tra fee_smc e prezzo_stimato_smc" 
        fee_smc = Decimal(str(fee_smc)) if fee_smc is not None else None
        prezzo_stimato_smc = Decimal(str(prezzo_stimato_smc)) if prezzo_stimato_smc is not None else None
        
        if tipo_formula == TipoFormula.COSTANTE:
            prezzo_smc = prezzo_stimato_smc
        else:
            prezzo_smc = psv_val * self.pcs_ratio + fee_smc 
        prezzo_mensile = prezzo_smc * self.consumo_mensile
        return prezzo_mensile.quantize(Decimal("0.01"), ROUND_HALF_UP)


    def _calcola_prezzo_mensile(self, 
                                fee_smc: Decimal = None,
                                prezzo_stimato_smc: Decimal = None,
                                psv_val: float = 0.0,
                                tipo_formula: TipoFormula = None
                                ) -> Decimal:
        """Mette assieme i pezzi per calcolare il totale mensile ivato"""
        prezzo_mensile_materia = self.get_prezzo_materia_smc(
            fee_smc=fee_smc,
            prezzo_stimato_smc=prezzo_stimato_smc,
            psv_val=Decimal(str(psv_val)),
            tipo_formula=tipo_formula,
        )
        
        # 1. Recupero le singole componenti
        trasporto_oneri = self.trasporto_oneri_mensile
        iva = self.iva_mensile_media
        accisa = self.accisa_mensile_media
        
        # 2. Somma imponibile (Materia + Rete + Accisa)
        imponibile = prezzo_mensile_materia + trasporto_oneri + accisa
        
        # 3. Applicazione IVA
        totale = imponibile * (1 + iva)
        
        return totale.quantize(Decimal("0.01"), ROUND_HALF_UP)

    def calcola_prezzo_offerta(self):
        return self._calcola_prezzo_mensile(
            fee_smc=self.offerta_gas.fee_offerta,
            prezzo_stimato_smc=self.offerta_gas.prezzo_stimato_offerta,
            psv_val=self.psv_medio,
            tipo_formula=self.offerta_gas.tipologia_formula_offerta
        )
    
    def calcola_prezzo_finita_medio(self) -> float:
        return self._calcola_prezzo_mensile(
            fee_smc=self.offerta_gas.fee_finita,
            prezzo_stimato_smc=self.offerta_gas.prezzo_stimato_finita,
            psv_val=self.psv_medio,
            tipo_formula=self.offerta_gas.tipologia_formula_finita
        )
        
        
    def calcola_prezzo_finita_peggiore(self) -> float:
        return self._calcola_prezzo_mensile(
            fee_smc=self.offerta_gas.fee_finita,
            prezzo_stimato_smc=self.offerta_gas.prezzo_stimato_finita,
            psv_val=self.psv_worst,
            tipo_formula=self.offerta_gas.tipologia_formula_finita
        )
        
    
        
if __name__ == "__main__":
    # Creazione di un'istanza di Offerta per il Mercato Libero
    offerta_esempio = Offerta(
        nome_offerta="Sorgenia Next Energy Smart Gas",
        gestore="Sorgenia S.p.A.",
        
        # Se l'offerta è indicizzata, usiamo le FEE e lasciamo il PREZZO STIMATO a None
        prezzo_stimato_offerta=None, 
        prezzo_stimato_finita=None,
        
        tipologia_formula_offerta="Indicizzata PSV",
        tipologia_formula_finita="Indicizzata PSV + Oneri",
        
        durata_mesi=12,
        costi_fissi_anno=96.90,  # Corrisponde alla quota fissa (QVD)
        
        # Qui inseriamo lo spread (la fee) sopra l'indice di mercato
        fee_offerta=0.41,        # fee_smc (es. 0.15 €/SMC)
        fee_finita=0.41,         # fee comprensiva di eventuali perdite o margini extra
        
        note="Offerta con rata costante basata sul PSV. Include sconto fedeltà."
    )
    print(CalcolatoreTrasportoGas(zona="CENTRO_NORD").stima_costo_mensile(Decimal("83.33")))
    print(CalcolatoreAccisaGas(zona="CENTRO_NORD").stima_accisa_media(83.33, 1))
    
    prezzo_gas = PrezzoGas(offerta_esempio)
    print("Calcolo Prezzi Gas:")
    
    print("prezzo offerta: ", prezzo_gas.calcola_prezzo_offerta())
    print("prezzo finita medio: ", prezzo_gas.calcola_prezzo_finita_medio())
    print("prezzo finita peggiore: ", prezzo_gas.calcola_prezzo_finita_peggiore())