# gestore-energia

Applicazione Python per l'estrazione, analisi e confronto delle offerte di energia elettrica e gas da file PDF. Il progetto utilizza l'API Google Gemini per estrarre dati strutturati dai PDF e calcola i costi personalizzati in base ai parametri dell'utente.

## 🎯 Funzionalità principali

- **Estrazione intelligente da PDF**: Utilizza Google Gemini per estrarre dati strutturati dalle offerte energetiche
- **Calcolo prezzi personalizzato**: Calcola automaticamente i costi mensili in base ai consumi e alle tariffe dell'utente
- **Supporto Luce e Gas**: Gestisce sia offerte di energia elettrica che di gas naturale
- **Cache intelligente**: Memorizza i risultati per evitare richieste API ripetute (24 ore di TTL)
- **Report Excel**: Genera fogli di calcolo formattati con i risultati per facile consultazione
- **Accise parametrizzate**: Considera automaticamente accise sulla base della zona geografica e della prima casa

## 📋 Requisiti

- Python >= 3.12
- Chiave API Google Gemini (gratuita con account Google)
- Librerie Python (vedi `pyproject.toml`)

## 🚀 Installazione

### 1. Clonare il repository
```bash
git clone <URL-del-repository>
cd gestore-energia
```

### 2. Creare e attivare l'ambiente virtuale
```bash
python -m venv venv
source venv/bin/activate  # Su Windows: venv\Scripts\activate
```

### 3. Installare le dipendenze
```bash
pip install -e .
```

## ⚙️ Configurazione

Il progetto utilizza file `.env` per la configurazione. Sono già presenti template nella directory `env/`. **È obbligatorio** compilarli correttamente per il funzionamento dell'applicazione.

### 1. `env/keys.env` - **OBBLIGATORIO**

Contiene la chiave API di Google Gemini necessaria per far funzionare il modello di estrazione:

```env
GENAI_API_KEY=<mykey>
```

**Come ottenere la chiave API:**
1. Accedi a [Google AI Studio](https://aistudio.google.com/apikey)
2. Clicca su "Get API Key"
3. Crea una nuova chiave API per il progetto
4. Copia la chiave nel file `env/keys.env`

### 2. `env/general.env` - Configurazione generale

Contiene i percorsi dei file e le impostazioni dell'applicazione:

```env
# Percorsi dei file PDF delle offerte
PATH_OFFERTE_LUCE = "data/offerte/luce"
PATH_OFFERTE_GAS = "data/offerte/gas"

# File dei prompt per l'estrazione
PROMPT_LUCE_FILE="prompts/dati_luce.txt"
PROMPT_GAS_FILE="prompts/dati_gas.txt"

# Modello Gemini da utilizzare
GENAI_MODEL="gemini-2.5-flash"

# Configurazione cache
CACHE_DIR = "data/cache"
CACHE_TTL_SECONDS = 86400  # 24 ore
```

### 3. `env/user.env` - Parametri dell'utente

Contiene i dati personali per il calcolo dei prezzi:

```env
# Dati anagrafici (per accise)
prima_casa=true                              # true/false
residenza=true                               # true/false
zona_geografica=CENTRO_NORD                  # CENTRO_NORD o SUD_MEZZOGIORNO

# Parametri LUCE
consumption_kwh_monthly=208.3                # Consumo medio mensile in kWh
potenza_kw=3.0                               # Potenza dell'impianto in kW

# Parametri GAS
consumption_smc_monthly=83.3                 # Consumo medio mensile in Smc
consumption_smc_yearly=1000                  # Consumo annuale in Smc
mese_riferimento=12                          # Mese di riferimento (1-12)
```

### 4. `env/price_coeff.env` - Coefficienti di prezzo

Contiene i valori di mercato e i coefficienti per il calcolo:

```env
# LUCE
pun_index_eur_kwh_mean=0.08846               # PUN medio 2025
pun_index_eur_kwh_worst=0.15                 # PUN pessimistico
go_index_eur_kwh=0.001                       # Indice Garantie d'Origine
perdite_el_rete_percent=0.10                 # Perdite di rete

# GAS
psv_eur_smc=0.4127                           # PSV medio
psv_eur_smc_worst=0.566770                   # PSV pessimistico
pcs_locale_gj_smc=0.0392570                  # Potere calorifico superiore locale
c_coefficiente=1.02                          # Coefficiente di correzione
```

## 📂 Struttura del progetto

```
gestore-energia/
├── env/                          # File di configurazione (obbligatorio)
│   ├── keys.env                 # ⚠️ OBBLIGATORIO: Chiave API Gemini
│   ├── general.env              # Configurazione generale
│   ├── user.env                 # Parametri dell'utente
│   └── price_coeff.env          # Coefficienti di prezzo
├── data/
│   ├── offerte/
│   │   ├── luce/                # PDF offerte di luce (input)
│   │   └── gas/                 # PDF offerte di gas (input)
│   ├── cache/                   # Cache risultati (auto-generato)
│   └── output/                  # Report Excel (output)
├── src/
│   ├── main.py                  # Script principale
│   ├── config.py                # Gestione configurazione
│   ├── model.py                 # Modelli dati
│   ├── data_extractor/          # Estrazione da PDF
│   ├── excel_writer/            # Generazione report Excel
│   └── prezzo/                  # Calcolo prezzi (luce e gas)
├── prompts/
│   ├── dati_luce.txt            # Prompt per estrazione offerte luce
│   └── dati_gas.txt             # Prompt per estrazione offerte gas
└── notebooks/                   # Jupyter notebooks per analisi
```

## 🔧 Utilizzo

### Elaborazione di tutte le offerte
```bash
python -m src.main
```

### Elaborazione solo offerte di luce
```bash
python -m src.main --fornitura=luce
```

### Elaborazione solo offerte di gas
```bash
python -m src.main --fornitura=gas
```

### Disabilitare la cache (force refresh)
```bash
python -m src.main --no-cache
```

## 📊 Output

Il programma genera file Excel nella cartella `data/output/`:

- **`risultati_prezzi_luce.xlsx`**: Analisi offerte di energia elettrica
- **`risultati_prezzi_gas.xlsx`**: Analisi offerte di gas naturale

Ogni file contiene:
- Nome offerta e gestore
- Prezzo offerta mensile
- Prezzo medio stimato (basato su PUN/PSV medio)
- Prezzo pessimistico (basato su PUN/PSV massimo)
- Note contrattuali

## 🐛 Troubleshooting

### Errore: "API key not found"
Assicurati che il file `env/keys.env` esista e contenga una chiave API valida.

### Errore: "Cartella non esiste"
Verifica che i percorsi in `env/general.env` siano corretti e che le cartelle `data/offerte/luce` e `data/offerte/gas` contengano i PDF.

### Cache stale
Usa l'opzione `--no-cache` per ignorare la cache e forzare l'estrazione dai PDF.

## 📝 Licenza

Questo progetto è distribuito sotto licenza MIT.
