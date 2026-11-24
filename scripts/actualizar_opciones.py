"""Baja el ratio Put/Call de las empresas de datos/universo.csv desde Yahoo Finance, en paralelo, a datos/put_call.csv.

Ratio Put/Call = open interest de puts / open interest de calls, sumando todos los vencimientos.
Las empresas sin opciones listadas quedan fuera del archivo. Si llegan menos de la mitad de las empresas
(Yahoo bloqueado o caído), no se toca el archivo anterior y el script termina con error.

Uso:  python scripts/actualizar_opciones.py [--si-falta]
       (--si-falta: no hace nada si ya se bajó hoy, hora de Nueva York)
"""
import sys
import time
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from fuentes import almacen, yahoo_opciones  # noqa: E402

UNIVERSO = RAIZ / "datos" / "universo.csv"
SALIDA = RAIZ / "datos" / "put_call.csv"
ZONA = "America/New_York"
MINIMO = 0.5   # fracción mínima de empresas con datos para guardar


def main():
    hoy = pd.Timestamp.now(tz=ZONA).strftime("%Y-%m-%d")
    if "--si-falta" in sys.argv and SALIDA.exists() and pd.read_csv(SALIDA)["fecha"].max().startswith(hoy):
        print(f"El Put/Call ya se bajó hoy ({hoy}): no se hace nada.")
        return
    tickers = list(pd.read_csv(UNIVERSO)["ticker"])
    t0 = time.time()
    datos, sin_datos = yahoo_opciones.put_call_varios(tickers)
    if len(datos) < MINIMO * len(tickers):
        sys.exit(f"Solo llegaron {len(datos)} de {len(tickers)} empresas: no se guarda nada "
                 f"(¿Yahoo bloqueado o caído?). Sin datos, por ejemplo: {', '.join(sin_datos[:15])}")
    df = pd.DataFrame(datos).T.rename_axis("ticker")
    df["put_call"] = (df["put_oi"] / df["call_oi"].where(df["call_oi"] > 0)).round(3)
    df["put_call_vol"] = (df["put_vol"] / df["call_vol"].where(df["call_vol"] > 0)).round(3)
    df["fecha"] = pd.Timestamp.now(tz=ZONA).strftime("%Y-%m-%d %H:%M NY")
    df.to_csv(SALIDA)
    almacen.guardar_sello("put_call")
    print(f"Guardado {SALIDA.relative_to(RAIZ)}: {len(df)} empresas en {time.time() - t0:.0f} s. "
          f"Sin opciones o sin respuesta: {len(sin_datos)}" + (f" ({', '.join(sin_datos[:15])})" if sin_datos else ""))


if __name__ == "__main__":
    main()
