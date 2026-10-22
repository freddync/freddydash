"""Indicadores técnicos compartidos (los usan Empresas, Industrias y Sectores)."""
RSI_PERIODO = 5


def rsi(precios, n=RSI_PERIODO):
    """RSI de Wilder (suavizado exponencial con alfa 1/n) para cada columna."""
    cambio = precios.diff()
    sube = cambio.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    baja = (-cambio.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + sube / baja)
