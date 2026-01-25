import os
import re
import json
import hashlib
import time
from google import genai
from google.genai import types
from loguru import logger

from src.model import Offerta
from ..config import config  


class CacheManager:
    def __init__(self, cache_dir: str, ttl_seconds: int):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        os.makedirs(cache_dir, exist_ok=True)

    def _cache_path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")

    def save(self, key: str, data: dict):
        with open(self._cache_path(key), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def load(self, key: str):
        path = self._cache_path(key)
        if not os.path.exists(path):
            return None
        if time.time() - os.path.getmtime(path) > self.ttl_seconds:
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def generate_key(self, *args) -> str:
        payload = "\n".join(str(a) for a in args)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class DebugProvider:
    def get_offerta(self, pdf_path: str):
        return {
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
            "note": "Uscita non possibile prima di 24 mesi"
        }
        
class EnergyGeminiExtractor:
    def __init__(self, model="gemini-2.5-flash", prompt_text=""):
        self.api_key = config.get("GENAI_API_KEY")
        self.model = model
        self.prompt_text = prompt_text
        self.cache = CacheManager(config.get("CACHE_DIR"), float(config.get("CACHE_TTL_SECONDS")))

        if not self.api_key:
            raise ValueError("GENAI_API_KEY non trovato. Controlla il file 'keys.env'")
        self.client = genai.Client(api_key=self.api_key)

    def extract(self, pdf_path: str, use_cache: bool = True) -> Offerta:
        logger.info(f"[{pdf_path}] Inizio estrazione dati con Energy Gemini")
        cache_key = self.cache.generate_key(pdf_path, self.model, self.prompt_text)

        if use_cache:
            cached_data = self.cache.load(cache_key)
            if cached_data:
                logger.success(f"[{pdf_path}] Dati caricati dalla cache.")
                return Offerta(**cached_data)
            logger.info(f"[{pdf_path}] Nessun dato in cache.")

        uploaded_file = self.client.files.upload(file=pdf_path)
        response_text = None
        try:
            parts = [
                types.Part.from_text(text=self.prompt_text),
                types.Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type)
            ]
            contents = [types.Content(role="user", parts=parts)]

            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": Offerta.model_json_schema()  
                }
            )
            response_text = response.text

            result_dict = json.loads(self._clean_text(response_text))
            offerta = Offerta(**result_dict)

            self.cache.save(cache_key, result_dict)
            logger.success(f"[{pdf_path}] Estrazione completata e salvata in cache.")
            return offerta

        finally:
            if response_text:
                with open("last_response.txt", "w", encoding="utf-8") as f:
                    f.write(response_text)
            self.client.files.delete(name=uploaded_file.name)

    @staticmethod
    def _clean_text(raw_text: str) -> str:
        """Rimuove eventuali blocchi di Markdown``` e spazi inutili."""
        return raw_text.replace("```", "").strip()



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
