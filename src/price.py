from pyparsing import ABC, abstractmethod
from src.model import OffertaEnergia
from .config import config  
from loguru import logger
from enum import Enum
import pandas as pd

class TipoFormula(str, Enum):
    STANDARD = "standard"
    RIDOTTA = "ridotta"
    COSTANTE = "costante"

def calcola_prezzo_energia(pun, fee: float, perdite_rete: float, indice_go: float, tipo="standard"):
    """
    Calcola il prezzo dell'energia basato sulla formula indicizzata.
    
    Parametri:
    - pun: Prezzo Unico Nazionale (es. 0.12)
    - fee: Spread applicato dal fornitore (es. 0.015)
    - perdite_rete: Coefficiente perdite (default 10% -> 0.10)
    - indice_go: Costo Garanzia d'Origine (es. 0.002)
    - tipo: "standard" (include GO) o "ridotta" (esclude GO)
    """
    
    try:
        # Formula base: PUN × (1 + perdite) + Fee
        prezzo_base = pun * (1 + perdite_rete) + fee
        
        if tipo == TipoFormula.STANDARD:
            prezzo_finale = prezzo_base + indice_go
            logger.debug(f"Calcolo standard: ({pun} * 1.10) + {fee} + {indice_go}")
        elif tipo == TipoFormula.RIDOTTA:
            prezzo_finale = prezzo_base
            logger.debug(f"Calcolo ridotto: ({pun} * 1.10) + {fee}")
        else:
            raise ValueError("Tipo formula non riconosciuto. Usa 'standard' o 'ridotta'.")
            
        return round(prezzo_finale, 6)
    
    except Exception as e:
        logger.error(f"Errore nel calcolo: {e}")
        return None
    
class Price(ABC):
    @abstractmethod
    def _calcola_prezzo_mensile(self, *args, **kwargs) -> float:
        ...
    @abstractmethod
    def calcola_prezzo_offerta(self) -> float:
        ...
    @abstractmethod
    def calcola_prezzo_finita_medio(self) -> float:
        ...
    @abstractmethod
    def calcola_prezzo_finita_peggiore(self) -> float:
        ...
    @abstractmethod
    def calcola_tutto(self) -> dict:
        ...
        
class PrezzoGas:
    pass

class PrezzoLuce(Price):
    def __init__(self, offerta_energia: OffertaEnergia):
        self.offerta_energia = offerta_energia
        self.consumo_mensile = int(config.get("consumption_kwh_monthly", 2500))
        self.pun_index_eur_kwh_mean = float(config.get("pun_index_eur_kwh_mean", 0.12))
        self.pun_index_eur_kwh_worst = float(config.get("pun_index_eur_kwh_worst", 0.15))
        self.go_index_eur_kwh = float(config.get("go_index_eur_kwh", 0.0002))
        self.perdite_rete = float(config.get("perdite_rete_percent", 0.10))
        logger.info(f"Configurazione Price: consumo_mensile={self.consumo_mensile}, pun_mean={self.pun_index_eur_kwh_mean}, pun_worst={self.pun_index_eur_kwh_worst}, go_index={self.go_index_eur_kwh}, perdite_rete={self.perdite_rete}")
        logger.info(f"Dati offerta: {self.offerta_energia}")
    
    def _calcola_prezzo_mensile(
        self,
        prezzo_stimato_kwh: float | None,
        fee_kwh: float | None,
        pun: float,
        tipo_formula: str | None
    ) -> float:

        # Prezzo fisso: non si usa la funzione indicizzata
        if prezzo_stimato_kwh is not None:
            prezzo_kwh = prezzo_stimato_kwh
        else:
            prezzo_kwh = calcola_prezzo_energia(
                pun=pun,
                fee=fee_kwh or 0.0,
                perdite_rete=self.perdite_rete,
                indice_go=self.go_index_eur_kwh,
                tipo=tipo_formula or "standard"
            )

            if prezzo_kwh is None:
                logger.error("Calcolo prezzo indicizzato fallito")
                raise ValueError("Calcolo prezzo indicizzato fallito")

        totale = prezzo_kwh * self.consumo_mensile
        totale += (self.offerta_energia.costi_fissi_anno or 0) / 12
        return round(totale, 2)

    def calcola_prezzo_offerta(self) -> float:
        return self._calcola_prezzo_mensile(
            self.offerta_energia.prezzo_stimato_offerta_kwh,
            self.offerta_energia.fee_offerta_kwh,
            self.pun_index_eur_kwh_mean,
            TipoFormula(self.offerta_energia.tipologia_formula_offerta)
        )

    def calcola_prezzo_finita_medio(self) -> float:
        return self._calcola_prezzo_mensile(
            self.offerta_energia.prezzo_stimato_finita_kwh,
            self.offerta_energia.fee_finita_kwh,
            self.pun_index_eur_kwh_mean,
            TipoFormula(self.offerta_energia.tipologia_formula_finita)
        )

    def calcola_prezzo_finita_peggiore(self) -> float:
        return self._calcola_prezzo_mensile(
            self.offerta_energia.prezzo_stimato_finita_kwh,
            self.offerta_energia.fee_finita_kwh,
            self.pun_index_eur_kwh_worst,
            TipoFormula(self.offerta_energia.tipologia_formula_finita)
        )
    def calcola_tutto(self) -> dict:
        """
        Calcola tutti gli scenari di prezzo mensile.
        """
        return pd.DataFrame([{
            "prezzo_offerta_mensile": self.calcola_prezzo_offerta(),
            "prezzo_finita_migliore_mensile": self.calcola_prezzo_finita_medio(),
            "prezzo_finita_peggiore_mensile": self.calcola_prezzo_finita_peggiore()
        }])