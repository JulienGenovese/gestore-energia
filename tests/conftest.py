import sys
from pathlib import Path

# Aggiungi il parent directory al path Python per consentire le importazioni da src
sys.path.insert(0, str(Path(__file__).parent.parent))
