import os
import sys
import pandas as pd
from loguru import logger
from .extractor import EnergyGeminiExtractor

# Import delle classi per il calcolo dei prezzi
from src.price import PrezzoLuce, PrezzoGas
from .config import config
# Configura logger
logger.remove()
logger.add(sys.stdout, level="INFO")


def process_file(pdf_path: str, tipo: str):
    """
    Estrae i dati da un PDF e calcola i prezzi in base al tipo ('luce' o 'gas').
    Restituisce il DataFrame finale.
    """
    extractor = EnergyGeminiExtractor()
    try:
        dati = extractor.extract_from_pdf(pdf_path, is_debug=False)
        if dati is None:
            raise ValueError("Nessun dato estratto dal PDF")
    except Exception as e:
        logger.error(f"[{pdf_path}] Errore durante l'estrazione: {e}")
        return None

    try:
        if tipo == "luce":
            result = PrezzoLuce(dati).calcola_tutto()
        elif tipo == "gas":
            result = PrezzoGas(dati).calcola_tutto()
        else:
            raise ValueError(f"Tipo sconosciuto: {tipo}")
    except Exception as e:
        logger.error(f"[{pdf_path}] Errore durante il calcolo dei prezzi: {e}")
        return None

    try:
        df_dati = dati.to_dataframe()
    except Exception as e:
        logger.error(f"[{pdf_path}] Errore durante la conversione in DataFrame: {e}")
        return None

    # Aggiunta colonne di risultati
    for col in result.columns:
        try:
            df_dati[col] = result[col].iloc[0]
        except Exception as e:
            logger.warning(f"[{pdf_path}] Impossibile aggiungere la colonna '{col}': {e}")

    return df_dati

def main():
    cartelle = {
        "luce": config.get("path_luce_offers", "data/offerte/luce"),
        "gas": config.get("path_gas_offers", "data/offerte/gas")
    }
    output_folder = os.path.join("data", "output")
    os.makedirs(output_folder, exist_ok=True)

    for tipo, folder in cartelle.items():
        if not os.path.exists(folder):
            logger.warning(f"La cartella '{folder}' non esiste. Skipping.")
            continue

        pdf_files = [f for f in os.listdir(folder) if f.lower().endswith(".pdf")]
        if not pdf_files:
            logger.info(f"Nessun PDF trovato in '{folder}'")
            continue

        # Lista per accumulare tutti i DataFrame
        all_dfs = []

        for pdf_file in pdf_files:
            pdf_path = os.path.join(folder, pdf_file)
            logger.info(f"Elaborazione file: {pdf_path}")
            df = process_file(pdf_path, tipo)
            if df is not None:
                all_dfs.append(df)

        # Concatenazione di tutti i DataFrame e salvataggio
        if all_dfs:
            try:
                final_df = pd.concat(all_dfs, ignore_index=True)
                output_path = os.path.join(output_folder, f"{tipo}_prezzi.xlsx")
                final_df.to_excel(output_path, index=False)
                logger.info(f"Tutti i risultati salvati in {output_path}")
            except Exception as e:
                logger.error(f"Errore durante il salvataggio in Excel: {e}")



if __name__ == "__main__":
    main()
