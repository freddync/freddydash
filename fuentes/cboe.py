"""Opciones desde las cotizaciones diferidas públicas de Cboe (un archivo por empresa, sin API key).

Cboe limita la cantidad de pedidos: si responde 429 (demasiados pedidos), todos los hilos esperan lo que
indica Retry-After y se reintenta. Entre pedidos se respeta un intervalo mínimo compartido.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{}.json"
CABECERAS = {"User-Agent": "Mozilla/5.0"}
INTENTOS = 6
INTERVALO = 0.25  # segundos mínimos entre dos pedidos cualquiera (~4 por segundo en total)

_candado = threading.Lock()
_proximo = [0.0]  # momento a partir del cual se puede hacer el siguiente pedido


def _turno(espera_extra=0.0):
    """Reserva el próximo hueco para pedir; con espera_extra, frena a todos los hilos ese tiempo."""
    with _candado:
        ahora = time.monotonic()
        _proximo[0] = max(_proximo[0], ahora + espera_extra)
        mio = _proximo[0]
        _proximo[0] = mio + INTERVALO
    time.sleep(max(0.0, mio - time.monotonic()))


def _simbolo(ticker):
    return ticker.replace("-", ".")  # BRK-B (Yahoo) → BRK.B (Cboe)


def put_call(ticker):
    """Open interest y volumen de puts y calls, sumando todos los vencimientos. None si no hay datos."""
    for _ in range(INTENTOS):
        _turno()
        try:
            r = requests.get(URL.format(_simbolo(ticker)), headers=CABECERAS, timeout=30)
        except requests.RequestException:
            continue
        if r.status_code == 429:
            _turno(float(r.headers.get("Retry-After") or 20))
            continue
        if r.status_code in (403, 404):
            return None  # sin opciones listadas
        try:
            r.raise_for_status()
            opciones = r.json()["data"]["options"]
        except Exception:
            continue
        total = {"put_oi": 0, "call_oi": 0, "put_vol": 0, "call_vol": 0}
        for o in opciones:
            # Símbolo OCC: raíz + AAMMDD + C/P + strike (8 dígitos); el tipo va 9 caracteres antes del final
            tipo = "put" if o["option"][-9] == "P" else "call"
            total[f"{tipo}_oi"] += o.get("open_interest") or 0
            total[f"{tipo}_vol"] += o.get("volume") or 0
        return total
    return None


def put_call_varios(tickers, hilos=4):
    """Baja varias empresas en paralelo. Devuelve ({ticker: datos}, [tickers sin datos])."""
    with ThreadPoolExecutor(hilos) as ex:
        resultados = dict(zip(tickers, ex.map(put_call, tickers)))
    ok = {t: d for t, d in resultados.items() if d}
    return ok, [t for t in tickers if t not in ok]
