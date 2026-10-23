"""Precios diarios desde la API de gráficos de Yahoo Finance (un pedido por ticker, sin yfinance).

Se baja en varios hilos con una pausa corta después de cada pedido; si Yahoo responde 429 o 503
(demasiados pedidos), se espera y se reintenta.
"""
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}"
CABECERAS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")}
HILOS = 12
PAUSA = 0.4  # segundos después de cada pedido, por hilo
INTENTOS = 3


def _pedir(ticker, rango):
    """Respuesta de la API para un ticker (dict), o None si no se logró."""
    for intento in range(INTENTOS):
        try:
            r = requests.get(URL.format(ticker), params={"range": rango, "interval": "1d"},
                             headers=CABECERAS, timeout=30)
            if r.status_code == 200:
                return r.json()["chart"]["result"][0]
            if r.status_code in (429, 503):
                time.sleep(5 + intento * 10)
                continue
        except Exception:
            pass
        time.sleep(2 + intento * 3)
    return None


def _velas(res):
    """Velas diarias ajustadas por dividendos y splits: el factor del cierre ajustado se aplica a todo."""
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({"Open": q["open"], "High": q["high"], "Low": q["low"], "Close": q["close"],
                       "Volume": q["volume"]},
                      index=pd.to_datetime(res["timestamp"], unit="s").normalize())
    # Durante la sesión (o un rato después) Yahoo a veces deja vacío el cierre del día: va el último precio
    precio = res.get("meta", {}).get("regularMarketPrice")
    if len(df) and pd.isna(df["Close"].iloc[-1]) and precio:
        df.iloc[-1, df.columns.get_loc("Close")] = precio
    ajustado = res["indicators"].get("adjclose", [{}])[0].get("adjclose")
    if ajustado:
        factor = (pd.Series(ajustado, index=df.index) / df["Close"]).fillna(1.0)
        df[["Open", "High", "Low", "Close"]] = df[["Open", "High", "Low", "Close"]].mul(factor, axis=0)
    df = df.dropna(subset=["Close"])
    return df[~df.index.duplicated(keep="last")]


def _cierre(ticker, rango):
    res = _pedir(ticker, rango)
    time.sleep(PAUSA)
    try:
        s = _velas(res)["Close"].rename(ticker)
    except Exception:
        return ticker, None
    return ticker, s if len(s) else None


def cierres(tickers, rango="3mo", hilos=HILOS):
    """Cierres ajustados en paralelo. Devuelve ({ticker: serie}, [tickers que no se lograron bajar])."""
    with ThreadPoolExecutor(hilos) as ex:
        resultados = dict(ex.map(lambda t: _cierre(t, rango), tickers))
    ok = {t: s for t, s in resultados.items() if s is not None}
    return ok, [t for t in tickers if t not in ok]


def historial(ticker, rango="2y"):
    """Velas diarias ajustadas (Open, High, Low, Close, Volume) de una empresa. Vacío si falla."""
    res = _pedir(ticker, rango)
    try:
        return _velas(res)
    except Exception:
        return pd.DataFrame()
