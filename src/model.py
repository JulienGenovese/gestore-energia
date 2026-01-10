from dataclasses import dataclass
from typing import Optional
import pandas as pd


@dataclass
class Offerta:
    nome_offerta: str
    gestore: str
    prezzo_stimato_offerta: Optional[float]
    prezzo_stimato_finita: Optional[float]
    tipologia_formula_finita: Optional[str]
    tipologia_formula_offerta: Optional[str]
    durata_mesi: Optional[int]
    costi_fissi_anno: Optional[float]
    fee_offerta: Optional[float]
    fee_finita: Optional[float]
    note: Optional[str]
    
    def to_dataframe(self):
        return pd.DataFrame([{
            "nome_offerta": self.nome_offerta,
            "gestore": self.gestore,
            "prezzo_stimato_offerta": self.prezzo_stimato_offerta,
            "prezzo_stimato_finita": self.prezzo_stimato_finita,
            "tipologia_formula_finita": self.tipologia_formula_finita,
            "tipologia_formula_offerta": self.tipologia_formula_offerta,
            "durata_mesi": self.durata_mesi,
            "costi_fissi_anno": self.costi_fissi_anno,
            "fee_offerta": self.fee_offerta,
            "fee_finita": self.fee_finita,
            "note": self.note
        }])
        
        
class TipoFormula(str, Enum):
    STANDARD = "standard"
    RIDOTTA = "ridotta"
    COSTANTE = "costante"
        
    