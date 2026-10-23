"""Baja las series de FRED de Macro · Tasas a datos/fred.csv (desde el año 2000).

Si alguna serie no llega, se conserva la que ya estaba guardada.

Uso:  python scripts/actualizar_fred.py
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from bloques.series import FRED  # noqa: E402
from fuentes import almacen, fred  # noqa: E402

DESDE = "2000-01-01"


def main():
    s, errores = fred.series(FRED)
    anterior, _ = almacen.fred(errores)
    s.update(anterior)
    if not s:
        sys.exit("FRED no respondió y no hay nada guardado.")
    almacen.guardar_fred({k: v[v.index >= DESDE] for k, v in s.items()})
    print(f"Guardado {almacen.FRED.relative_to(RAIZ)}: {len(s)} series. Sin actualizar: {', '.join(errores) or 'ninguna'}")


if __name__ == "__main__":
    main()
