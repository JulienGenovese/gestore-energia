from dataclasses import dataclass
from typing import Optional
import pandas as pd


@dataclass
class OffertaEnergia:
    nome_offerta: str
    gestore: str
    prezzo_stimato_offerta_kwh: Optional[float]
    prezzo_stimato_finita_kwh: Optional[float]
    tipologia_formula_finita: Optional[str]
    tipologia_formula_offerta: Optional[str]
    durata_mesi: Optional[int]
    costi_fissi_anno: Optional[float]
    fee_offerta_kwh: Optional[float]
    fee_finita_kwh: Optional[float]
    clausole: Optional[str]
    
    def to_dataframe(self):
        return pd.DataFrame([{
            "nome_offerta": self.nome_offerta,
            "gestore": self.gestore,
            "prezzo_stimato_offerta_kwh": self.prezzo_stimato_offerta_kwh,
            "prezzo_stimato_finita_kwh": self.prezzo_stimato_finita_kwh,
            "tipologia_formula_finita": self.tipologia_formula_finita,
            "tipologia_formula_offerta": self.tipologia_formula_offerta,
            "durata_mesi": self.durata_mesi,
            "costi_fissi_anno": self.costi_fissi_anno,
            "fee_offerta_kwh": self.fee_offerta_kwh,
            "fee_finita_kwh": self.fee_finita_kwh,
            "clausole": self.clausole
        }])