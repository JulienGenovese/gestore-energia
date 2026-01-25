import os
import argparse
import sys
import pandas as pd
from loguru import logger

from src.model import DatiPrezzo, Offerta
from .data_extractor.extractor import EnergyGeminiExtractor
from .excel_writer.excel_writer import ExcelFormatter
from .prezzo.prezzo_luce import PrezzoLuce
from .prezzo.prezzo_gas import PrezzoGas
from .config import config
# Configura logger
logger.remove()
logger.add(sys.stdout, level="INFO")


def parse_arguments():
    """Parsa gli argomenti della riga di comando."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disabilita l'uso della cache durante l'estrazione"
    )
    parser.add_argument(
        "--fornitura",
        choices=["all", "luce", "gas"],
        default="all"
    )
    parser.add_argument(
        "--offerta",
        type=str,
        default=None,
        help="Nome dell'offerta specifica da elaborare"
    )
        
    args = parser.parse_args()
    return args

def validate_folder(use_cache: bool, fornitura: str) -> (dict, str):
    """Valida le cartelle di input e crea la cartella di output.""" 
    if not use_cache:
        logger.info("Cache DISABILITATA")
    else:
        logger.info("Cache ABILITATA")
        cache_dir = config.get("CACHE_DIR")
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
            logger.info(f"Creata cartella di cache: {cache_dir}")
        
    cartelle = {
        "luce": config.get("PATH_OFFERTE_LUCE"),
        "gas": config.get("PATH_OFFERTE_GAS")
    }
    
    if fornitura != "all":
        cartelle = {fornitura: cartelle[fornitura]}
        
    try:
        for folder in cartelle.values():
            if not os.path.exists(folder):
                raise FileNotFoundError(f"La cartella '{folder}' non esiste.")
            if not os.listdir(folder):
                raise FileNotFoundError(f"La cartella '{folder}' non ha pdf da processare.")
    except Exception as e:
        logger.error(f"Errore: {e}")
        sys.exit(1)
        
    output_folder = os.path.join("data", "output")
    os.makedirs(output_folder, exist_ok=True)
    return cartelle, output_folder

def extract_data(pdf_path: str, prompt_text: str, use_cache: bool = True) -> Offerta | None:
    """Estrae i dati da un PDF utilizzando EnergyGeminiExtractor."""

    extractor = EnergyGeminiExtractor(model=config.get("GENAI_MODEL"), prompt_text=prompt_text)
    try:
        dati_offerta: Offerta = extractor.extract(pdf_path, use_cache=use_cache)
        if dati_offerta is None:
            raise ValueError("Nessun dato estratto dal PDF")
    except Exception as e:
        logger.error(f"[{pdf_path}] Errore durante l'estrazione: {e}")
        raise e
    df_dati_offerta = dati_offerta
    return df_dati_offerta

def compute_price(dati: pd.DataFrame, tipo: str) -> DatiPrezzo | None:
    """Calcola i prezzi in base al tipo di fornitura."""
    try:
        if tipo == "luce":
            result: DatiPrezzo = PrezzoLuce(dati).calcola_tutto()
        elif tipo == "gas":
            result: DatiPrezzo = PrezzoGas(dati).calcola_tutto()
        else:
            raise ValueError(f"Tipo sconosciuto: {tipo}")
        result = result
        return result
    except Exception as e:
        logger.error(f"Errore durante il calcolo dei prezzi: {e}")
        raise e

def process_file(pdf_path: str, tipo: str, use_cache: bool = True) -> pd.DataFrame | None:
    """
    Estrae i dati da un PDF e calcola i prezzi in base al tipo ('luce' o 'gas').
    Restituisce il DataFrame finale.
    """
    if tipo == "luce":
        prompt_text_path = config.get("PROMPT_LUCE_FILE")
    elif tipo == "gas":
        prompt_text_path = config.get("PROMPT_GAS_FILE")
    else:
        logger.error(f"Tipo sconosciuto: {tipo}")
        return None
    with open(prompt_text_path, "r", encoding="utf-8") as f:
        prompt_text = f.read()

    dati_offerta = extract_data(pdf_path, prompt_text=prompt_text, use_cache=use_cache)
    if dati_offerta is None:
        return None
    else:
        df_dati_offerta = dati_offerta.to_dataframe()
    result = compute_price(dati_offerta, tipo)
    if result is None:
        return None
    result_df = result.to_dataframe()
    df_dati_offerta = df_dati_offerta.merge(result_df, 
                                            on=["nome_offerta", "gestore"],
                                            how="left")

    return df_dati_offerta

def build_output_dataframe(df: pd.DataFrame,output_folder: str, output_file: str) -> None:
    """Costruisce il DataFrame di output e lo salva in un file Excel."""
    try:
        final_df = df
        output_path = os.path.join(output_folder, output_file)
        offerta_cols = ["nome_offerta", "gestore"]
        prezzo_cols = ["prezzo_offerta_mensile", "prezzo_finita_medio_mensile", "prezzo_finita_peggiore_mensile"]
        note_cols  = ["note"]
        ordered_cols = offerta_cols + prezzo_cols  + [col for col in final_df.columns if col not in offerta_cols + prezzo_cols + note_cols] + note_cols
        final_df = final_df[ordered_cols]
        final_df = final_df.sort_values(by=offerta_cols).reset_index(drop=True)
        ExcelFormatter(df=final_df, 
                       output_path=output_path,
                       key_columns=offerta_cols,
                       price_columns=prezzo_cols,
                       note_column="note"
                       ).run()
        logger.info(f"Tutti i risultati salvati in {output_path}")
    except Exception as e:
        logger.error(f"Errore durante il salvataggio in Excel: {e}")
        raise e

def main():
    
    args = parse_arguments()

    use_cache = not args.no_cache
    fornitura = args.fornitura
    offerta_filtro = args.offerta
    cartelle, output_folder = validate_folder(use_cache, fornitura)
    
    for tipo, folder in cartelle.items():
        logger.info(f"Elaborazione offerte per: {tipo.upper()}")
        pdf_files = [f for f in os.listdir(folder) if f.lower().endswith(".pdf")]
        all_dfs = []
        for pdf_file in pdf_files:
            if offerta_filtro is not None and offerta_filtro.lower() != pdf_file.lower():
                logger.info(f"Saltando file (filtro offerta): {pdf_file}")
                continue
            pdf_path = os.path.join(folder, pdf_file)
            logger.info(f"Elaborazione file: {pdf_path}")
            df = process_file(pdf_path, tipo, use_cache=use_cache)
            if df is not None:
                all_dfs.append(df)

        if len(all_dfs) > 0:
            all_dfs = pd.concat(all_dfs, ignore_index=True)
            output_file = f"risultati_prezzi_{tipo}.xlsx"
            build_output_dataframe(all_dfs, output_folder, output_file)
        logger.success(f"Elaborazione completata per: {tipo.upper()}")


if __name__ == "__main__":
    main()
