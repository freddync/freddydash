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

# Down · Señales: las 74 megacaps donde se validó la estrategia swing (lista de MegaCap, sin duplicados ni
# tickers que no cotizan). El orden es la prioridad cuando hay más señales que cupos (mayor capitalización primero).
# Varias no están en datos/universo.csv (ADRs extranjeras, etc.): se bajan igual junto a los precios.
MEGACAPS = {
    "NVDA": "NVIDIA", "AAPL": "Apple", "GOOGL": "Alphabet", "MSFT": "Microsoft", "AMZN": "Amazon",
    "TSM": "Taiwan Semiconductor", "AVGO": "Broadcom", "META": "Meta Platforms", "TSLA": "Tesla",
    "BRK-B": "Berkshire Hathaway", "LLY": "Eli Lilly", "MU": "Micron", "JPM": "JPMorgan Chase", "WMT": "Walmart",
    "AMD": "Advanced Micro Devices", "ASML": "ASML Holding", "XOM": "ExxonMobil", "V": "Visa",
    "JNJ": "Johnson & Johnson", "INTC": "Intel", "MA": "Mastercard", "BAC": "Bank of America", "ABBV": "AbbVie",
    "CSCO": "Cisco", "ORCL": "Oracle", "COST": "Costco", "PLTR": "Palantir", "LRCX": "Lam Research",
    "AMAT": "Applied Materials", "CVX": "Chevron", "CAT": "Caterpillar", "GE": "GE Aerospace", "KO": "Coca-Cola",
    "UNH": "UnitedHealth", "HSBC": "HSBC Holdings", "MS": "Morgan Stanley", "HD": "Home Depot",
    "PG": "Procter & Gamble", "MRK": "Merck", "NFLX": "Netflix", "DELL": "Dell Technologies",
    "PANW": "Palo Alto Networks", "GS": "Goldman Sachs", "TM": "Toyota", "RY": "Royal Bank of Canada",
    "RTX": "RTX Corp", "ARM": "Arm Holdings", "PM": "Philip Morris", "BABA": "Alibaba", "NVS": "Novartis",
    "GEV": "GE Vernova", "MUFG": "Mitsubishi UFJ", "WFC": "Wells Fargo", "KLAC": "KLA Corp", "SHEL": "Shell",
    "SAP": "SAP SE", "TXN": "Texas Instruments", "ANET": "Arista Networks", "SNDK": "Sandisk",
    "AZN": "AstraZeneca", "C": "Citigroup", "AXP": "American Express", "AMGN": "Amgen", "LIN": "Linde",
    "CRWD": "CrowdStrike", "IBM": "IBM", "STX": "Seagate", "BHP": "BHP Group", "TMO": "Thermo Fisher",
    "SAN": "Banco Santander", "APH": "Amphenol", "TD": "Toronto-Dominion", "NVO": "Novo Nordisk", "VZ": "Verizon",
}
