"""Qué series usa cada bloque. Sin dependencias: lo importan también los scripts de descarga,
que corren en GitHub Actions sin Streamlit."""

# Sectores: ETFs SPDR de los 11 sectores del S&P 500
SECTORES = {
    "XLK": "Tecnología", "XLF": "Financiero", "XLV": "Salud", "XLY": "Consumo discrecional",
    "XLP": "Consumo básico", "XLE": "Energía", "XLI": "Industrial", "XLB": "Materiales",
    "XLU": "Servicios básicos", "XLRE": "Inmobiliario", "XLC": "Comunicaciones",
}
# Macro · Tendencia
ETFS = {"SPY": "S&P 500", "QQQ": "Nasdaq 100", "IWM": "Russell 2000", "RSP": "S&P 500 pesos iguales"}
# Macro · Volatilidad
VOLATILIDAD = {"^VIX": "VIX", "^VIX3M": "VIX3M", "^MOVE": "MOVE"}
# Macro · Economía: commodities (futuros continuos de Yahoo)
COMMODITIES = {"CL=F": "Petróleo WTI", "NG=F": "Gas natural", "GC=F": "Oro", "SI=F": "Plata", "HG=F": "Cobre"}
# Macro · Economía: tasas (FRED). Curva a plazo constante: todos los plazos con la misma metodología del Tesoro
PLAZOS = {"3M": "DGS3MO", "1A": "DGS1", "2A": "DGS2", "5A": "DGS5", "10A": "DGS10", "30A": "DGS30"}
FRED = ["DFEDTAR", "DFEDTARU", "CPIAUCSL", *PLAZOS.values()]

# Todo lo de mercado que se guarda junto a los precios de las empresas
MERCADO = list(dict.fromkeys([*SECTORES, "SPY", *ETFS, *VOLATILIDAD, *COMMODITIES]))
