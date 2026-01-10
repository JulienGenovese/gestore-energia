from loguru import logger

from src.model import Offerta
from src.prezzo.abc import ABCPrice
from decimal import Decimal, ROUND_HALF_UP
from ..config import config  

class CalcolatoreMorfologicoC:
    """
    Fornisce un valore approssimato del Coefficiente C basato sulla 
    morfologia del territorio, utile se l'utente non ha la bolletta sottomano.
    """
    
    VALORI_C = {
        "MARE":     Decimal("1.027"), # Altitudine ~0m (Pressione massima)
        "PIANURA":  Decimal("1.015"), # Altitudine ~100-200m
        "COLLINA":  Decimal("0.985"), # Altitudine ~400-500m
        "MONTAGNA": Decimal("0.940")  # Altitudine > 800m (Pressione minima)
    }

    @classmethod
    def ottieni_c(cls, tipo_territorio: str) -> Decimal:
        """
        Ritorna il coefficiente C stimato. 
        Default su PIANURA se il parametro è errato.
        """
        tipo = tipo_territorio.upper()
        if tipo not in cls.VALORI_C:
            # Se l'utente scrive male, logghiamo un warning e usiamo la pianura
            return cls.VALORI_C["PIANURA"]
            
        return cls.VALORI_C[tipo]

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
        
        # 1. Inferenziazione: Consumo Annuo Stimato = Consumo Mese / Peso Mese
        consumo_annuo_stimato = c_mese / peso_mese
        
        # 2. Simulazione anno solare per riempire gli scaglioni
        accisa_annua_totale = Decimal('0')
        progressivo_annuo = Decimal('0')
        
        for m in range(1, 13):
            consumo_del_mese = consumo_annuo_stimato * self.PESI_MENSILI[m]
            
            accisa_mese = self._calcola_accisa_puntuale(consumo_del_mese, progressivo_annuo)
            accisa_annua_totale += accisa_mese
            progressivo_annuo += consumo_del_mese

        # 3. Media
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
    
    
    
from decimal import Decimal, ROUND_HALF_UP

class PrezzoGas(ABCPrice):
    def __init__(self, offerta_gas: Offerta):
        self.offerta_gas = offerta_gas
        # Inizializziamo il calcolatore fiscale (quello con i pesi mensili)
        zona = config.get("zona_geografica")
        self.calcolatore_fiscale = CalcolatoreAccisaGas(zona=zona)
        
        # Dati base
        self.consumo_mensile = Decimal(str(config.get("consumption_smc_monthly")))
        self.mese_rif = int(config.get("mese_riferimento", 1))
        self.is_residente = config.get("residenza", "true").lower() == "true"
        
        # Parametri tecnici
        self.coeff_c = Decimal(str(config.get("coefficiente_c", "1.0")))
        self.pcs_ratio = Decimal(str(config.get("pcs", "0.03852"))) / Decimal("0.03852")

    def get_quota_materia(self, psv_val: Decimal) -> Decimal:
        """Calcola il costo della materia prima (variabile + fisso)"""
        fee = Decimal(str(getattr(self.offerta_gas, "fee_offerta_smc", 0) or 0))
        prezzo_smc = (psv_val + fee) * self.coeff_c * self.pcs_ratio
        
        costo_var = prezzo_smc * self.consumo_mensile
        costo_fiss = Decimal(str(getattr(self.offerta_gas, "costi_fissi_anno", 0) or 0)) / 12
        return costo_var + costo_fiss

    def get_quota_trasporto_e_oneri(self) -> Decimal:
        """Calcola i costi di rete e oneri di sistema (stabiliti da ARERA)"""
        # Valori standard (70€ trasporto + 40€ oneri fissi annui / 0.045 e 0.030 variabili)
        fissi = (Decimal("70.00") + Decimal("40.00")) / 12
        variabili = (Decimal("0.045") + Decimal("0.030")) * self.consumo_mensile
        return fissi + variabili

    def get_quota_fiscale_media(self) -> dict:
        """
        Usa l'inferenza per calcolare l'accisa media e il tasso IVA medio proiettato.
        """
        stima = self.calcolatore_fiscale.stima_accisa_media(float(self.consumo_mensile), self.mese_rif)
        accisa_media = Decimal(str(stima["accisa_media_mensile"]))
        consumo_annuo = Decimal(str(stima["consumo_annuo_inferred"]))

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
        trasporto_oneri = self.get_quota_trasporto_e_oneri()
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