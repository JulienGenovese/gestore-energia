import os
from dotenv import load_dotenv, dotenv_values
from loguru import logger

class Config:
    def __init__(self, env_dir=None):
        """
        Inizializza la configurazione leggendo TUTTI i file .env 
        presenti nella cartella specificata (default: 'env').
        """
        if env_dir is None:
            # Punta alla cartella 'env' nella root del progetto
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            env_dir = os.path.join(base_dir, "env")
        
        self.env_dir = env_dir
        self.settings = {}

        if not os.path.exists(self.env_dir):
            logger.error(f"Cartella env non trovata: {self.env_dir}")
            raise FileNotFoundError(f"Cartella env non trovata: {self.env_dir}")

        self._load_all_env_files()

    def _load_all_env_files(self):
        """Itera e carica ogni file nella cartella env."""
        # Otteniamo la lista dei file e li ordiniamo (opzionale, per prevedibilità)
        files = sorted(os.listdir(self.env_dir))
        
        for filename in files:
            # Carichiamo solo file (escludiamo cartelle)
            file_path = os.path.join(self.env_dir, filename)
            
            if os.path.isfile(file_path):
                logger.info(f"Caricamento file env: {filename}")
                
                # Carica nel sistema (os.environ)
                load_dotenv(dotenv_path=file_path, override=True)
                
                # Aggiorna il dizionario interno settings
                file_values = dotenv_values(dotenv_path=file_path)
                self.settings.update(file_values)

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def as_dict(self):
        return self.settings

config = Config()  

if __name__ == "__main__":
    
    try:
        config = Config() # Cerca automaticamente la cartella 'env'
        print("\n--- Riepilogo Impostazioni ---")
        for k, v in config.as_dict().items():
            print(f"{k}: {v}")
    except Exception as e:
        logger.exception("Errore durante l'inizializzazione della configurazione")