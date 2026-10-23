"""Baja los cierres ajustados de las empresas de datos/universo.csv y de los ETFs e índices del Top.

  historia  ~7 años → datos/precios/historia.parquet (una vez al mes)
  reciente  3 meses → datos/precios/reciente.csv     (varias veces al día)

Un pedido por ticker a la API de gráficos de Yahoo, en paralelo (fuentes/yahoo.py); lo que falla se
reintenta después de una pausa. Si un ticker no se logra bajar, se conserva lo que ya había en el archivo.

Uso:  python scripts/actualizar_precios.py [historia|reciente]
"""
import sys
import time
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from bloques.series import MERCADO  # noqa: E402
from fuentes import almacen, yahoo  # noqa: E402

UNIVERSO = RAIZ / "datos" / "universo.csv"
# historia: 5 años de gráfico más ~1.5 años para calentar la rotación (5 + 300 + 75 días); Yahoo no tiene
# un rango de 7 años, así que se pide 10 y se recorta. reciente: tiene que solaparse con la historia,
# que se rehace cada mes.
RANGOS = {"historia": "10y", "reciente": "3mo"}
ANIOS_HISTORIA = 7
REINTENTOS, ESPERA = 2, 30


def bajar(tickers, rango):
    """({ticker: serie}, [tickers que no se lograron bajar])."""
    t0 = time.time()
    precios, pendientes = yahoo.cierres(tickers, rango)
    print(f"  {len(precios)} ok, {len(pendientes)} fallaron ({time.time() - t0:.0f} s)", flush=True)
    for intento in range(1, REINTENTOS + 1):
        if not pendientes:
            break
        time.sleep(ESPERA * intento)
        ok, pendientes = yahoo.cierres(pendientes, rango, hilos=2)
        precios.update(ok)
        print(f"  reintento {intento}: {len(ok)} ok, {len(pendientes)} siguen fallando", flush=True)
    return precios, pendientes


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "reciente"
    if modo not in RANGOS:
        sys.exit(f"Modo desconocido: {modo}. Usa historia o reciente.")
    tickers = list(pd.read_csv(UNIVERSO)["ticker"]) + MERCADO
    precios, pendientes = bajar(tickers, RANGOS[modo])
    df = pd.DataFrame(precios).sort_index()
    if modo == "historia":
        df = df[df.index >= df.index[-1] - pd.DateOffset(years=ANIOS_HISTORIA)]

    anterior = almacen.precios() if modo == "historia" else almacen.leer_reciente()
    conservar = [t for t in pendientes if t in anterior]
    if conservar:
        df = df.join(anterior[conservar], how="outer")
        print(f"Se conserva lo anterior de {len(conservar)} tickers")
    if len(precios) < len(tickers) * 0.9:
        sys.exit(f"Solo llegaron {len(precios)} de {len(tickers)} tickers: no se guarda nada.")

    (almacen.guardar_historia if modo == "historia" else almacen.guardar_reciente)(df)
    print(f"Guardado {modo}: {df.shape[1]} tickers, {len(df)} sesiones, {df.index[0]:%Y-%m-%d} a "
          f"{df.index[-1]:%Y-%m-%d}. Sin datos: {', '.join(pendientes) or 'ninguno'}")


if __name__ == "__main__":
    main()
