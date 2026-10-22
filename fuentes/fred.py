"""Series de FRED desde su descarga pública en CSV (no pide API key)."""
import io
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def serie(sid):
    r = requests.get(URL, params={"id": sid}, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), index_col=0, parse_dates=True, na_values=".")
    return pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna().rename(sid)


def _intentar(sid):
    try:
        return sid, serie(sid)
    except Exception:
        return sid, None


def series(ids):
    """Baja varias series en paralelo. Devuelve ({id: serie}, [ids que fallaron])."""
    with ThreadPoolExecutor(8) as ex:
        resultados = list(ex.map(_intentar, ids))
    ok = {sid: s for sid, s in resultados if s is not None and not s.empty}
    return ok, [sid for sid, _ in resultados if sid not in ok]
