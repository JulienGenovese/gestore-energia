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
    
def return_tipo_formula(tipo: str | None) -> TipoFormula:
    """Converte una stringa in TipoFormula Enum o None."""
    if tipo is None:
        tipo = None
    else:
        tipo = TipoFormula(tipo)
    return tipo
    
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
        try:
            self.consumo_mensile = float(config.get("consumption_kwh_monthly"))
            self.pun_index_eur_kwh_mean = float(config.get("pun_index_eur_kwh_mean"))
            self.pun_index_eur_kwh_worst = float(config.get("pun_index_eur_kwh_worst"))
            self.go_index_eur_kwh = float(config.get("go_index_eur_kwh", 0.0002))
            self.perdite_rete = float(config.get("perdite_rete_percent", 0.10))

            self.potenza_impegnata = float(config.get("potenza_kw", 3.0))
            # --- TRASPORTO E CONTATORE ---
            self.quota_fissa_trasporto_mese = 24 / 12            # €/mese
            self.quota_potenza_kw_mese = 23 / 12                 # €/kW/mese
            self.quota_variabile_trasporto_kwh = 0.009           # €/kWh

            # --- ONERI DI SISTEMA ---
            self.oneri_fissi_mese = 20 / 12                      # €/mese
            self.oneri_variabili_kwh = 0.040                     # €/kWh

            # --- IMPOSTE ---
            self.accisa_kwh = 0.0227
            self.kwh_esenti_accisa_mese = 150
            self.prima_casa = True if config.get("prima_casa").lower() == "true" else False
            self.residenza = True if config.get("residenza").lower() == "true" else False
        except Exception as e:        
            logger.error(f"Errore durante l'inizializzazione: {e}")
            raise e
        logger.info("Inizializzazione PrezzoLuce completata.")


    def _calcola_prezzo_mensile(
        self,
        prezzo_stimato_kwh: float | None,
        fee_kwh: float | None,
        pun: float,
        tipo_formula: TipoFormula | None
    ) -> float | None:

        # -------------------------
        # 1. PREZZO ENERGIA €/kWh
        # -------------------------
        if prezzo_stimato_kwh is not None:
            prezzo_energia = prezzo_stimato_kwh
        else:
            prezzo_energia = calcola_prezzo_energia(
                pun=pun,
                fee=fee_kwh or 0.0,
                perdite_rete=self.perdite_rete,
                indice_go=self.go_index_eur_kwh,
                tipo=tipo_formula or TipoFormula.STANDARD
            )

        if prezzo_energia is None:
            return None

        # -------------------------
        # 2. QUOTE VARIABILI €/mese
        # -------------------------
        costo_energia = prezzo_energia * self.consumo_mensile
        costo_trasporto_var = self.quota_variabile_trasporto_kwh * self.consumo_mensile
        costo_oneri_var = self.oneri_variabili_kwh * self.consumo_mensile

        # -------------------------
        # 3. ACCISA (parziale)
        # -------------------------
        costo_accisa = self.calcola_accisa()

        # -------------------------
        # 4. QUOTE FISSE €/mese
        # -------------------------
        costo_fissi_vendita = (getattr(self.offerta_energia, "costi_fissi_anno", 0) or 0) / 12
        costo_trasporto_fisso = (
            self.quota_fissa_trasporto_mese +
            self.potenza_impegnata * self.quota_potenza_kw_mese
        )
        costo_oneri_fissi = self.oneri_fissi_mese

        # -------------------------
        # 5. TOTALE
        # -------------------------
        totale_netto = (
            costo_energia +
            costo_trasporto_var +
            costo_oneri_var +
            costo_accisa +
            costo_fissi_vendita +
            costo_trasporto_fisso +
            costo_oneri_fissi
        )

        totale_ivato = totale_netto * (1 + self.iva)

        return round(totale_ivato, 2)

    def calcola_accisa(self):
        """Calcola l'accisa mensile in base ai kWh esenti."""
        if self.prima_casa and self.residenza and self.potenza_impegnata <= 3:
            kwh_tassati = max(0, self.consumo_mensile - self.kwh_esenti_accisa_mese)
        else:
            kwh_tassati = self.consumo_mensile

        return kwh_tassati * self.accisa_kwh
    
    @property
    def iva(self) -> float:
        """Restituisce l'IVA applicabile."""
        return 0.10 if self.residenza else 0.22

    def calcola_prezzo_offerta(self) -> float:

        return self._calcola_prezzo_mensile(
            self.offerta_energia.prezzo_stimato_offerta_kwh,
            self.offerta_energia.fee_offerta_kwh,
            self.pun_index_eur_kwh_mean,
            return_tipo_formula(self.offerta_energia.tipologia_formula_offerta)
        )

    def calcola_prezzo_finita_medio(self) -> float:
        return self._calcola_prezzo_mensile(
            self.offerta_energia.prezzo_stimato_finita_kwh,
            self.offerta_energia.fee_finita_kwh,
            self.pun_index_eur_kwh_mean,
            return_tipo_formula(self.offerta_energia.tipologia_formula_finita)
        )

    def calcola_prezzo_finita_peggiore(self) -> float:
        return self._calcola_prezzo_mensile(
            self.offerta_energia.prezzo_stimato_finita_kwh,
            self.offerta_energia.fee_finita_kwh,
            self.pun_index_eur_kwh_worst,
            return_tipo_formula(self.offerta_energia.tipologia_formula_finita)
        )
    def calcola_tutto(self) -> dict:
        """
        Calcola tutti gli scenari di prezzo mensile.
        """
        return pd.DataFrame([{
            "prezzo_offerta_mensile": self.calcola_prezzo_offerta(),
            "prezzo_finita_medio_mensile": self.calcola_prezzo_finita_medio(),
            "prezzo_finita_peggiore_mensile": self.calcola_prezzo_finita_peggiore()
        }])