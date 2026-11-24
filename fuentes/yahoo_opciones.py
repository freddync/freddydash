"""Opciones desde la API pública de Yahoo Finance: open interest y volumen de puts y calls por empresa.

Yahoo entrega un vencimiento por pedido, así que cada empresa cuesta tantos pedidos como vencimientos
tenga (~5 a 25). La API pide una cookie y un "crumb" (una ficha que se saca una vez por sesión); si deja de
valer (401), se pide otra. Entre pedidos se respeta un intervalo mínimo compartido por todos los hilos, y si
Yahoo responde 429 (demasiados pedidos) todos esperan antes de reintentar.

(Hasta nov-2026 esto se bajaba de Cboe, que empezó a bloquear las descargas automáticas.)
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

URL = "https://query2.finance.yahoo.com/v7/finance/options/{}"
CABECERAS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")}
INTENTOS = 4
INTERVALO = 0.08    # segundos mínimos entre dos pedidos cualquiera (~12 por segundo en total)
ESPERA_429 = 30

_candado = threading.Lock()
_proximo = [0.0]
_sesion = {"s": None, "crumb": None}


def _turno(espera_extra=0.0):
    """Reserva el próximo hueco para pedir; con espera_extra, frena a todos los hilos ese tiempo."""
    with _candado:
        _proximo[0] = max(_proximo[0], time.monotonic() + espera_extra)
        mio = _proximo[0]
        _proximo[0] = mio + INTERVALO
    time.sleep(max(0.0, mio - time.monotonic()))


def _nueva_sesion(vieja=None):
    """Sesión con la cookie de Yahoo y su crumb. Si otro hilo ya la renovó, se usa esa."""
    with _candado:
        if _sesion["s"] is not None and _sesion["s"] is not vieja:
            return _sesion["s"], _sesion["crumb"]
        s = requests.Session()
        s.headers.update(CABECERAS)
        s.get("https://fc.yahoo.com", timeout=20)          # deja la cookie (responde 404, es normal)
        crumb = s.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=20).text.strip()
        _sesion.update(s=s, crumb=crumb)
        return s, crumb


def _pedir(ticker, fecha=None):
    """Resultado de la API para un vencimiento (o el primero si fecha es None). None si no se logró."""
    s, crumb = _sesion["s"], _sesion["crumb"]
    if s is None:
        s, crumb = _nueva_sesion()
    for _ in range(INTENTOS):
        _turno()
        params = {"crumb": crumb, **({"date": fecha} if fecha else {})}
        try:
            r = s.get(URL.format(ticker), params=params, timeout=30)
        except requests.RequestException:
            continue
        if r.status_code == 401:
            s, crumb = _nueva_sesion(s)
            continue
        if r.status_code == 429:
            _turno(ESPERA_429)
            continue
        if r.status_code == 404:
            return None
        try:
            r.raise_for_status()
            return r.json()["optionChain"]["result"][0]
        except Exception:
            continue
    return None


def _sumar(total, opciones):
    for lista, tipo in (("calls", "call"), ("puts", "put")):
        for o in opciones.get(lista, []):
            total[f"{tipo}_oi"] += o.get("openInterest") or 0
            total[f"{tipo}_vol"] += o.get("volume") or 0


def put_call(ticker):
    """Open interest y volumen de puts y calls, sumando todos los vencimientos. None si no hay opciones
    o si falló algún vencimiento (un total parcial daría un ratio engañoso)."""
    res = _pedir(ticker)
    if not res or not res.get("expirationDates") or not res.get("options"):
        return None
    total = {"put_oi": 0, "call_oi": 0, "put_vol": 0, "call_vol": 0}
    _sumar(total, res["options"][0])                       # el primer pedido ya trae el primer vencimiento
    for fecha in res["expirationDates"][1:]:
        r = _pedir(ticker, fecha)
        if not r or not r.get("options"):
            return None
        _sumar(total, r["options"][0])
    return total


def put_call_varios(tickers, hilos=4):
    """Baja varias empresas en paralelo. Devuelve ({ticker: datos}, [tickers sin datos])."""
    with ThreadPoolExecutor(hilos) as ex:
        resultados = dict(zip(tickers, ex.map(put_call, tickers)))
    ok = {t: d for t, d in resultados.items() if d}
    return ok, [t for t in tickers if t not in ok]
