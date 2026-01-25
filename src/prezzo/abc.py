import pandas as pd
from abc import ABC, abstractmethod
from enum import Enum

from src.model import DatiPrezzo, TipoFormula


class ABCPrice(ABC):
    def __init__(self, offerta_energia: DatiPrezzo):
        self.offerta_energia = offerta_energia

    @abstractmethod
    def calcola_prezzo_offerta(self) -> float:
        ...
    @abstractmethod
    def calcola_prezzo_finita_medio(self) -> float:
        ...
    @abstractmethod
    def calcola_prezzo_finita_peggiore(self) -> float:
        ...
    def calcola_tutto(self) -> DatiPrezzo:
        """
        Calcola tutti gli scenari di prezzo mensile.
        """
        return DatiPrezzo(
            nome_offerta=self.offerta_energia.nome_offerta,
            gestore=self.offerta_energia.gestore,
            prezzo_offerta_mensile=self.calcola_prezzo_offerta(),
            prezzo_finita_medio_mensile=self.calcola_prezzo_finita_medio(),
            prezzo_finita_peggiore_mensile=self.calcola_prezzo_finita_peggiore()
        )
        
        
def return_tipo_formula(tipo: str | None) -> TipoFormula:
    """Converte una stringa in TipoFormula Enum o None."""
    if tipo is None:
        tipo = None
    else:
        tipo = TipoFormula(tipo)
    return tipo