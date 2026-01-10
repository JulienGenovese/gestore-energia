import pandas as pd
from pyparsing import ABC, abstractmethod
from enum import Enum


class ABCPrice(ABC):

    @abstractmethod
    def calcola_prezzo_offerta(self) -> float:
        ...
    @abstractmethod
    def calcola_prezzo_finita_medio(self) -> float:
        ...
    @abstractmethod
    def calcola_prezzo_finita_peggiore(self) -> float:
        ...
    def calcola_tutto(self) -> dict:
        """
        Calcola tutti gli scenari di prezzo mensile.
        """
        return pd.DataFrame([{
            "prezzo_offerta_mensile": self.calcola_prezzo_offerta(),
            "prezzo_finita_medio_mensile": self.calcola_prezzo_finita_medio(),
            "prezzo_finita_peggiore_mensile": self.calcola_prezzo_finita_peggiore()
        }])


    

def return_tipo_formula(tipo: str | None) -> TipoFormula:
    """Converte una stringa in TipoFormula Enum o None."""
    if tipo is None:
        tipo = None
    else:
        tipo = TipoFormula(tipo)
    return tipo