import pytest
from decimal import Decimal
from src.prezzo.prezzo_gas import CalcolatoreMorfologicoC, CalcolatoreAccisaGas


class TestCalcolatoreMorfologicoC:
    """Test suite per CalcolatoreMorfologicoC"""

    def test_ottieni_c_mare(self):
        """Test che ottieni_c ritorna il valore corretto per MARE"""
        result = CalcolatoreMorfologicoC.ottieni_c("MARE")
        assert result == Decimal("1.027")

    def test_ottieni_c_pianura(self):
        """Test che ottieni_c ritorna il valore corretto per PIANURA"""
        result = CalcolatoreMorfologicoC.ottieni_c("PIANURA")
        assert result == Decimal("1.015")

    def test_ottieni_c_collina(self):
        """Test che ottieni_c ritorna il valore corretto per COLLINA"""
        result = CalcolatoreMorfologicoC.ottieni_c("COLLINA")
        assert result == Decimal("0.985")

    def test_ottieni_c_montagna(self):
        """Test che ottieni_c ritorna il valore corretto per MONTAGNA"""
        result = CalcolatoreMorfologicoC.ottieni_c("MONTAGNA")
        assert result == Decimal("0.940")

    def test_ottieni_c_lowercase(self):
        """Test che ottieni_c accetta input lowercase"""
        result = CalcolatoreMorfologicoC.ottieni_c("mare")
        assert result == Decimal("1.027")

    def test_ottieni_c_mixed_case(self):
        """Test che ottieni_c accetta input mixed case"""
        result = CalcolatoreMorfologicoC.ottieni_c("PiAnUrA")
        assert result == Decimal("1.015")

    def test_ottieni_c_invalid_territory_defaults_to_pianura(self):
        """Test che ottieni_c ritorna PIANURA per territorio non valido"""
        result = CalcolatoreMorfologicoC.ottieni_c("DESERTO")
        assert result == Decimal("1.015")

    def test_ottieni_c_empty_string_defaults_to_pianura(self):
        """Test che ottieni_c ritorna PIANURA per stringa vuota"""
        result = CalcolatoreMorfologicoC.ottieni_c("")
        assert result == Decimal("1.015")

    def test_ottieni_c_all_valid_territories_are_decimals(self):
        """Test che tutti i valori sono Decimal"""
        for territorio in ["MARE", "PIANURA", "COLLINA", "MONTAGNA"]:
            result = CalcolatoreMorfologicoC.ottieni_c(territorio)
            assert isinstance(result, Decimal)


class TestCalcolatoreAccisaGas:
    """Test suite per CalcolatoreAccisaGas"""

    def test_init_centro_nord_default(self):
        """Test che l'inizializzazione di default usa CENTRO_NORD"""
        calc = CalcolatoreAccisaGas()
        assert calc.scaglioni == CalcolatoreAccisaGas.TARIFFE_ACCISA["CENTRO_NORD"]

    def test_init_centro_nord_explicit(self):
        """Test che l'inizializzazione con CENTRO_NORD esplicito funziona"""
        calc = CalcolatoreAccisaGas(zona="CENTRO_NORD")
        assert calc.scaglioni == CalcolatoreAccisaGas.TARIFFE_ACCISA["CENTRO_NORD"]

    def test_init_sud_mezzogiorno(self):
        """Test che l'inizializzazione con SUD_MEZZOGIORNO funziona"""
        calc = CalcolatoreAccisaGas(zona="SUD_MEZZOGIORNO")
        assert calc.scaglioni == CalcolatoreAccisaGas.TARIFFE_ACCISA["SUD_MEZZOGIORNO"]

    def test_init_invalid_zona_raises_error(self):
        """Test che una zona non valida solleva ValueError"""
        with pytest.raises(ValueError, match="Zona non valida"):
            CalcolatoreAccisaGas(zona="NORD_OVEST")

    def test_stima_accisa_media_returns_dict_with_required_keys(self):
        """Test che stima_accisa_media ritorna un dizionario con le chiavi richieste"""
        calc = CalcolatoreAccisaGas()
        result = calc.stima_accisa_media(50.0, 1)
        
        required_keys = {
            "consumo_annuo_inferred",
            "accisa_totale_annua",
            "accisa_media_mensile",
            "metodologia"
        }
        assert set(result.keys()) == required_keys

    def test_stima_accisa_media_low_consumption_winter_month(self):
        """Test stima_accisa_media con consumo basso in mese invernale (gennaio)"""
        calc = CalcolatoreAccisaGas(zona="CENTRO_NORD")
        result = calc.stima_accisa_media(50.0, 1)
        
        # Gennaio ha peso 0.18, quindi consumo annuo stimato = 50 / 0.18 ≈ 277.78
        assert result["consumo_annuo_inferred"] > 0
        assert result["accisa_totale_annua"] > 0
        assert result["accisa_media_mensile"] > 0
        assert "metodologia" in result

    def test_stima_accisa_media_high_consumption_summer_month(self):
        """Test stima_accisa_media con consumo alto in mese estivo (agosto)"""
        calc = CalcolatoreAccisaGas(zona="CENTRO_NORD")
        result = calc.stima_accisa_media(100.0, 8)
        
        # Agosto ha peso 0.02, quindi consumo annuo stimato = 100 / 0.02 = 5000
        assert result["consumo_annuo_inferred"] == 5000.0
        assert result["accisa_totale_annua"] > 0

    def test_stima_accisa_media_south_vs_north(self):
        """Test che il sud ha accise diverse dal nord per lo stesso consumo"""
        consumo = 50.0
        mese = 1
        
        calc_nord = CalcolatoreAccisaGas(zona="CENTRO_NORD")
        result_nord = calc_nord.stima_accisa_media(consumo, mese)
        
        calc_sud = CalcolatoreAccisaGas(zona="SUD_MEZZOGIORNO")
        result_sud = calc_sud.stima_accisa_media(consumo, mese)
        
        # Il sud dovrebbe avere accise diverse dal nord
        assert result_nord["accisa_totale_annua"] != result_sud["accisa_totale_annua"]

    def test_stima_accisa_media_all_months(self):
        """Test stima_accisa_media per tutti i mesi"""
        calc = CalcolatoreAccisaGas()
        
        for mese in range(1, 13):
            result = calc.stima_accisa_media(50.0, mese)
            assert result["consumo_annuo_inferred"] > 0
            assert result["accisa_totale_annua"] > 0
            assert result["accisa_media_mensile"] > 0

