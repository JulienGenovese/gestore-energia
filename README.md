# gestore-energia

## Descrizione
`gestore-energia` è un progetto Python progettato per analizzare e confrontare le offerte dei gestori di energia elettrica e gas. Il progetto utilizza librerie avanzate per l'elaborazione dei dati e genera report dettagliati per aiutare gli utenti a scegliere l'offerta più conveniente.

## Funzionalità principali
- Estrazione di dati strutturati da file PDF contenenti offerte energetiche.
- Analisi e confronto delle offerte di energia elettrica e gas.
- Generazione di report dettagliati con costi stimati e note contrattuali.
- Cache dei risultati per migliorare le prestazioni.

## Requisiti
- Python >= 3.12
- Librerie richieste (vedi `pyproject.toml`):

## Installazione
1. Clonare il repository:
   ```bash
   git clone <URL-del-repository>
   cd gestore-energia
   ```

2. Creare un ambiente virtuale e attivarlo:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Su Windows: venv\Scripts\activate
   ```

3. Installare le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```

## Configurazione
1. Creare un file `.env` nella directory `env/` e aggiungere le seguenti variabili:
   ```env
   GENAI_API_KEY=<la-tua-chiave-API>
   PROMPT_FILE=prompts/data_requests.txt
   ```

2. Assicurarsi che il file di prompt esista nel percorso specificato.

## Utilizzo
### Esecuzione principale
Per eseguire il progetto, utilizzare il file `main.py`:
```bash
python -m src.main
```

### Estrazione da PDF
Un esempio di utilizzo della classe `EnergyGeminiExtractor`:
```python
from src.extractor import EnergyGeminiExtractor

extractor = EnergyGeminiExtractor()
pdf_path = "data/offerte/NEXTENERGYSMARTLUCE_Dual_191225.pdf"

dati = extractor.extract_from_pdf(pdf_path, is_debug=True)
print(dati)
```

### Debugging
Per abilitare il debug, passare `is_debug=True` durante l'estrazione.

## Struttura del progetto
- `data/`: Contiene i file PDF delle offerte.
- `output/`: Directory per i report generati.
- `src/`: Codice sorgente del progetto.
- `notebooks/`: Notebook Jupyter per analisi esplorative.
- `env/`: File di configurazione `.env`.

## Contributi
Contributi e segnalazioni di bug sono benvenuti! Sentiti libero di aprire una issue o inviare una pull request.

## Licenza
Questo progetto è distribuito sotto licenza MIT.
