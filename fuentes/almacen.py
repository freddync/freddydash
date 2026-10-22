"""Datos guardados en el repositorio, que actualiza GitHub Actions (.github/workflows) con los scripts de scripts/.

  datos/precios/historia.parquet  cierres ajustados de ~7 años: empresas, ETFs e índices (se rehace una vez al mes)
  datos/precios/reciente.csv      los últimos 3 meses de los mismos tickers (se rehace varias veces al día)
  datos/fred.csv                  series de FRED (tasas e inflación)

Yahoo reajusta hacia atrás toda la historia de una acción cuando paga un dividendo o se divide. Por eso, al unir
los dos archivos, la historia de cada ticker se multiplica por el factor entre ambos en su primer día en común.
"""
from pathlib import Path

import pandas as pd

DATOS = Path(__file__).resolve().parent.parent / "datos"
HISTORIA = DATOS / "precios" / "historia.parquet"
RECIENTE = DATOS / "precios" / "reciente.csv"
FRED = DATOS / "fred.csv"


def version(*archivos):
    """Fecha de modificación de los archivos (por defecto, los de precios): cambia cuando se actualizan."""
    return tuple(f.stat().st_mtime if f.exists() else 0 for f in (archivos or (HISTORIA, RECIENTE)))


def leer_reciente():
    if not RECIENTE.exists():
        return pd.DataFrame()
    largo = pd.read_csv(RECIENTE, parse_dates=["fecha"])
    return largo.pivot(index="fecha", columns="ticker", values="cierre").rename_axis(columns=None)


def precios():
    """Cierres ajustados de todos los tickers guardados (DataFrame: fechas × tickers)."""
    h = pd.read_parquet(HISTORIA).astype(float) if HISTORIA.exists() else pd.DataFrame()
    r = leer_reciente()
    if h.empty or r.empty:
        return r if h.empty else h
    comun = h.index.intersection(r.index)
    factores = {}
    for t in h.columns.intersection(r.columns):
        par = pd.concat([h.loc[comun, t], r.loc[comun, t]], axis=1).dropna()
        if len(par):
            factores[t] = par.iloc[0, 1] / par.iloc[0, 0]
    antes = h[h.index < r.index[0]]
    antes = antes.mul(pd.Series(factores).reindex(antes.columns).fillna(1.0), axis=1)
    unido = pd.concat([antes, r]).sort_index()
    # Lo que no llegó en el archivo reciente se completa con la historia tal cual
    sin_reciente = h.columns.difference(r.columns[r.notna().any()])
    if len(sin_reciente):
        unido[sin_reciente] = h[sin_reciente].reindex(unido.index)
    return unido


def cierres(p, tickers):
    """Desde la tabla de precios(): ({ticker: serie}, [tickers sin datos guardados])."""
    ok = {t: p[t].dropna() for t in tickers if t in p and p[t].notna().any()}
    return ok, [t for t in tickers if t not in ok]


def fred(ids):
    """({id: serie}, [ids sin datos guardados]) desde datos/fred.csv."""
    df = pd.read_csv(FRED, index_col=0, parse_dates=True) if FRED.exists() else pd.DataFrame()
    ok = {i: df[i].dropna() for i in ids if i in df and df[i].notna().any()}
    return ok, [i for i in ids if i not in ok]


def guardar_historia(df):
    HISTORIA.parent.mkdir(parents=True, exist_ok=True)
    df.sort_index().astype("float32").to_parquet(HISTORIA, compression="zstd")


def guardar_reciente(df):
    """En formato largo (ticker, fecha, cierre) ordenado por ticker: cuando Yahoo reajusta una acción,
    cambian solo sus líneas y git guarda una diferencia chica."""
    RECIENTE.parent.mkdir(parents=True, exist_ok=True)
    largo = df.rename_axis(index="fecha", columns="ticker").stack().rename("cierre").reset_index()
    largo = largo[["ticker", "fecha", "cierre"]].sort_values(["ticker", "fecha"])
    largo.to_csv(RECIENTE, index=False, float_format="%.6g", date_format="%Y-%m-%d")


def guardar_fred(series):
    pd.DataFrame(series).sort_index().rename_axis("fecha").to_csv(FRED, float_format="%.6g", date_format="%Y-%m-%d")
