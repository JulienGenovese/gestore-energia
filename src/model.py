from typing import Optional
from pydantic import BaseModel, Field
import pandas as pd
from enum import Enum

class DfDict(BaseModel):
    def to_dict(self) -> dict:
        return self.dict()

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([self.to_dict()])


class Offerta(DfDict):
    nome_offerta: str
    gestore: str
    prezzo_stimato_offerta: Optional[float] = None
    prezzo_stimato_finita: Optional[float] = None
    tipologia_formula_finita: Optional[str] = None
    tipologia_formula_offerta: Optional[str] = None
    durata_mesi: Optional[int] = None
    costi_fissi_anno: Optional[float] = None
    fee_offerta: Optional[float] = None
    fee_finita: Optional[float] = None
    note: Optional[str] = None


class DatiPrezzo(DfDict):
    nome_offerta: Optional[str] = None
    gestore: Optional[str] = None
    prezzo_offerta_mensile: Optional[float] = None
    prezzo_finita_medio_mensile: Optional[float] = None
    prezzo_finita_peggiore_mensile: Optional[float] = None



class TipoFormula(str, Enum):
    STANDARD = "standard"
    RIDOTTA = "ridotta"
    COSTANTE = "costante"
    
        
    