"""Arma el universo de empresas de Fdash: datos/universo.csv.

El screener de NASDAQ (CSV exportados desde nasdaq.com/market-activity/stocks/screener)
define qué empresas entran: de EE.UU. y con capitalización sobre el mínimo. Yahoo define
su sector e industria, porque sus 11 sectores calzan con los ETFs SPDR de Sectores.

Se corre a mano y necesita yfinance (pip install yfinance), que el dashboard no usa.

Uso:  python scripts/actualizar_universo.py [carpeta_screener] [capitalizacion_minima_usd]
      (por defecto ../Screener y 10e9)
"""
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import yfinance as yf

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "datos" / "universo.csv"

# Sector de Yahoo → ETF sectorial SPDR
SECTOR_ETF = {
    "Technology": "XLK", "Financial Services": "XLF", "Healthcare": "XLV",
    "Consumer Cyclical": "XLY", "Consumer Defensive": "XLP", "Energy": "XLE",
    "Industrials": "XLI", "Basic Materials": "XLB", "Utilities": "XLU",
    "Real Estate": "XLRE", "Communication Services": "XLC",
}


def leer_screener(carpeta, minimo):
    df = pd.concat([pd.read_csv(f) for f in sorted(Path(carpeta).glob("*.csv"))], ignore_index=True)
    df["cap"] = pd.to_numeric(df["Market Cap"], errors="coerce")
    df = df[(df["Country"] == "United States") & (df["cap"] >= minimo)]
    # Sin acciones preferentes (^); las clases con "/" van con "-" en Yahoo (BRK/B → BRK-B)
    df = df[~df["Symbol"].str.contains(r"\^", regex=True)]
    df["ticker"] = df["Symbol"].str.replace("/", "-", regex=False)
    return df[["ticker", "Name", "cap"]].drop_duplicates("ticker")


def clasificar(ticker):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            info = yf.Ticker(ticker).info
        return {"ticker": ticker, "nombre": info.get("longName") or info.get("shortName"),
                "tipo": info.get("quoteType"), "sector": info.get("sector"), "industria": info.get("industry")}
    except Exception:
        return {"ticker": ticker}


def main():
    carpeta = sys.argv[1] if len(sys.argv) > 1 else RAIZ.parent / "Screener"
    minimo = float(sys.argv[2]) if len(sys.argv) > 2 else 10e9
    base = leer_screener(carpeta, minimo)
    print(f"Screener: {len(base)} empresas de EE.UU. con capitalización >= ${minimo / 1e9:.0f}B")

    with ThreadPoolExecutor(8) as ex:
        info = pd.DataFrame(list(ex.map(clasificar, base["ticker"])))
    df = base.merge(info, on="ticker", how="left")

    sin_datos = df[df["sector"].isna() | (df["tipo"] != "EQUITY")]
    df = df.drop(sin_datos.index)
    df["etf"] = df["sector"].map(SECTOR_ETF)

    # Una sola clase por empresa (GOOG/GOOGL, BRK-A/BRK-B): se queda la de mayor capitalización
    df = df.sort_values("cap", ascending=False).drop_duplicates("nombre")

    df = df[["ticker", "nombre", "cap", "sector", "etf", "industria"]].sort_values(["etf", "industria", "cap"],
                                                                                   ascending=[True, True, False])
    SALIDA.parent.mkdir(exist_ok=True)
    df.to_csv(SALIDA, index=False)
    print(f"Sin clasificación en Yahoo (descartadas): {len(sin_datos)}"
          + (f": {', '.join(sin_datos['ticker'].head(20))}" if len(sin_datos) else ""))
    print(f"Guardado {SALIDA.relative_to(RAIZ)}: {len(df)} empresas, {df['industria'].nunique()} industrias")


if __name__ == "__main__":
    main()
