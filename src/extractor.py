import os
import re
import json
from google import genai
from google.genai import types
from loguru import logger

from src.model import OffertaEnergia
from .config import config  
from loguru import logger
import hashlib
import time

CACHE_DIR = "cache"
CACHE_TTL_SECONDS = 24 * 3600  


class EnergyGeminiExtractor:
    """
    Classe per estrarre dati strutturati da PDF usando Google Gemini.
    """

    def __init__(self, api_key=None, prompt_file=None, model="gemini-2.5-flash"):
        self.api_key = api_key or config.get("GENAI_API_KEY")
        self.prompt_file = prompt_file or config.get("PROMPT_FILE")
        self.model = model

        if not self.api_key:
            raise ValueError("GENAI_API_KEY non trovato. Controlla il file .env.")
        if not self.prompt_file or not os.path.exists(self.prompt_file):
            raise FileNotFoundError(f"Prompt file non trovato: {self.prompt_file}")

        self.client = genai.Client(api_key=self.api_key)

        self._load_prompt()
        
    def _cache_key(self, pdf_path: str) -> str:
        """Genera una chiave di cache unica basata sul file PDF e il prompt."""
        stat = os.stat(pdf_path)

        payload = f"""
        {os.path.basename(pdf_path)}
        {stat.st_size}
        {stat.st_mtime}
        {self.model}
        {self.prompt_text}
        """

        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _cache_path(self, key: str) -> str:
        """Restituisce il percorso del file di cache per una chiave data."""
        return os.path.join(CACHE_DIR, f"{key}.json")

    def _load_from_cache(self, key: str):
        """Carica i dati dalla cache se esistono e non sono scaduti."""
        path = self._cache_path(key)
        if not os.path.exists(path):
            return None

        if time.time() - os.path.getmtime(path) > CACHE_TTL_SECONDS:
            return None

        logger.info("Risultato caricato da cache")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
        
    def _save_to_cache(self, key: str, data: dict):
        """Salva i dati nella cache."""
        self._ensure_cache_dir()
        path = self._cache_path(key)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def _ensure_cache_dir(self):
        """Crea la cartella di cache se non esiste."""
        os.makedirs(CACHE_DIR, exist_ok=True)

    def _load_prompt(self):
        """Carica il testo del prompt in memoria."""
        with open(self.prompt_file, "r", encoding="utf-8") as f:
            self.prompt_text = f.read()

    def _clean_text(self, raw_text):
        """Rimuove i blocchi di codice Markdown e spazi inutili."""
        cleaned = re.sub(r"```.*?\n", "", raw_text).replace("```", "").strip()
        return cleaned

    def extract_from_pdf(self, path_to_pdf, use_cache=True, is_debug: bool =False) -> dict:
        """Estrae dati strutturati da un PDF."""
        
        if is_debug:
            logger.debug(f"Estrazione da PDF: {path_to_pdf}")
            dict_result ={
                "nome_offerta": "NEXTENERGYSMARTLUCE",
                "gestore": "Sorgenia",
                "prezzo_stimato_offerta_kwh": 0.14,
                "prezzo_stimato_finita_kwh": None,
                "durata_mesi": 12,
                "costi_fissi_anno": 81.03,
                "tipologia_formula_offerta": "costante",
                "tipologia_formula_finita": "standard",
                "fee_offerta_kwh": 0.008,
                "fee_finita_kwh": 0.03,
                "clausole": "Uscita non possibile prima di 24 mesi"
                }
            return OffertaEnergia(**dict_result)
        else:
                
            if not os.path.exists(path_to_pdf):
                raise FileNotFoundError(f"File PDF non trovato: {path_to_pdf}")

            cache_key = self._cache_key(path_to_pdf)
            cached = self._load_from_cache(cache_key)
            if cached is not None:
                return cached

            uploaded_file = self.client.files.upload(file=path_to_pdf)
            logger.info(f"File {path_to_pdf} caricato.")

            try:
                parts = [
                    types.Part.from_text(text=self.prompt_text),
                    types.Part.from_uri(
                        file_uri=uploaded_file.uri,
                        mime_type=uploaded_file.mime_type
                    ),
                ]
                contents = [types.Content(role="user", parts=parts)]

                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents
                )

                cleaned_text = self._clean_text(response.text)
                result = json.loads(cleaned_text)

                self._save_to_cache(cache_key, result)
                return  OffertaEnergia(**result)

            finally:
                self.client.files.delete(name=uploaded_file.name)


# --- Esempio di utilizzo ---
if __name__ == "__main__":
    import sys

    extractor = EnergyGeminiExtractor()
    pdf_path = os.path.join("data", "offerte", "NEXTENERGYSMARTLUCE_Dual_191225.pdf")
    try:
        dati = extractor.extract_from_pdf(pdf_path)
        print(json.dumps(dati, indent=4, ensure_ascii=False))
    except Exception as e:
        print("Errore:", e)
        sys.exit(1)
