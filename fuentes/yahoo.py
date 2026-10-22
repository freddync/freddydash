"""Precios diarios ajustados desde Yahoo Finance."""
import time
import warnings
from pathlib import Path

import pandas as pd
import yfinance as yf

INTENTOS, PAUSA = 3, 3  # Yahoo a veces rechaza pedidos por exceso de consultas: se reintenta lo que falta
# Última copia buena de cada serie, para no mostrar gráficos incompletos si Yahoo falla
RESPALDO = Path(__file__).resolve().parent.parent / "datos" / "respaldo_yahoo"


def _archivo(ticker, periodo):
    return RESPALDO / f"{ticker.replace('^', '_')}_{periodo}.parquet"


def _bajar(tickers, periodo):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = yf.download(tickers, period=periodo, auto_adjust=True, progress=False, threads=True)
    if df.empty:
        return {}
    close = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df[["Close"]].set_axis(tickers, axis=1)
    return {t: close[t].dropna() for t in tickers if t in close and close[t].notna().any()}


def cierres(tickers, periodo="max", respaldo=True):
    """Cierres ajustados (dividendos y splits). Devuelve ({ticker: serie}, [tickers que no se actualizaron]).

    Con respaldo=True, lo que no se logra bajar se completa con la última copia guardada (si existe),
    pero igual aparece en la lista de no actualizados para poder avisarlo.
    """
    ok, pendientes = {}, list(tickers)
    for intento in range(INTENTOS):
        if intento:
            time.sleep(PAUSA * intento)
        ok.update(_bajar(pendientes, periodo))
        pendientes = [t for t in tickers if t not in ok]
        if not pendientes:
            break
    if respaldo:
        RESPALDO.mkdir(parents=True, exist_ok=True)
        for t, serie in ok.items():
            serie.rename("cierre").to_frame().to_parquet(_archivo(t, periodo))
        for t in pendientes:
            if _archivo(t, periodo).exists():
                ok[t] = pd.read_parquet(_archivo(t, periodo))["cierre"].rename(t)
    return ok, pendientes


def historial(ticker, periodo="2y"):
    """Velas diarias ajustadas (Open, High, Low, Close, Volume) de una empresa. Vacío si falla."""
    for intento in range(INTENTOS):
        if intento:
            time.sleep(PAUSA * intento)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                h = yf.Ticker(ticker).history(period=periodo, auto_adjust=True)
        except Exception:
            continue
        if not h.empty:
            h.index = h.index.tz_localize(None).normalize()
            return h[["Open", "High", "Low", "Close", "Volume"]]
    return pd.DataFrame()
