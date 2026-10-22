"""Baja los cierres ajustados de las empresas de datos/universo.csv y de los ETFs e índices del Top.

  historia  ~7 años → datos/precios/historia.parquet (una vez al mes)
  reciente  3 meses → datos/precios/reciente.csv     (varias veces al día)

Yahoo limita los pedidos masivos, así que se baja en tandas con pausas y se reintenta lo que falla.
Si un ticker no se logra bajar, se conserva lo que ya había en el archivo.

Uso:  python scripts/actualizar_precios.py [historia|reciente]
"""
import sys
import time
import warnings
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from bloques import sectores, tendencia, volatilidad  # noqa: E402
from fuentes import almacen, yahoo  # noqa: E402

UNIVERSO = RAIZ / "datos" / "universo.csv"
MERCADO = list(dict.fromkeys([*sectores.SECTORES, "SPY", *tendencia.ETFS, *volatilidad.TICKERS]))
# historia: 5 años de gráfico más ~1.5 años para calentar la rotación (5 + 300 + 75 días).
# reciente: tiene que alcanzar a solaparse con la historia, que se rehace cada mes.
PERIODOS = {"historia": "7y", "reciente": "3mo"}
TANDA, PAUSA, INTENTOS = 80, 8, 4


def bajar(tickers, periodo):
    """({ticker: serie}, [tickers que no se lograron bajar])."""
    precios, pendientes = {}, tickers
    for intento in range(1, INTENTOS + 1):
        fallidos = []
        for i in range(0, len(pendientes), TANDA):
            tanda = pendientes[i:i + TANDA]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ok, mal = yahoo.cierres(tanda, periodo=periodo, respaldo=False)
            precios.update(ok)
            fallidos += mal
            print(f"  intento {intento}, tanda {i // TANDA + 1}: {len(ok)} ok, {len(mal)} fallaron", flush=True)
            time.sleep(PAUSA)
        pendientes = fallidos
        if not pendientes:
            break
        print(f"Quedan {len(pendientes)}; espero {PAUSA * 4 * intento} s antes de reintentar", flush=True)
        time.sleep(PAUSA * 4 * intento)
    return precios, pendientes


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "reciente"
    if modo not in PERIODOS:
        sys.exit(f"Modo desconocido: {modo}. Usa historia o reciente.")
    tickers = list(pd.read_csv(UNIVERSO)["ticker"]) + MERCADO
    precios, pendientes = bajar(tickers, PERIODOS[modo])
    df = pd.DataFrame(precios).sort_index()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()

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
