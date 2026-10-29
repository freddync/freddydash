"""FreddyDash: dashboard de inversión en tres partes.

Top: el mercado desde arriba (sectores → industrias) y su rotación por velocidad.
Down: el análisis de cada empresa.
Macro: el escenario (tendencias del mercado y economía).
"""
import importlib
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Streamlit vuelve a correr app.py y la página cuando cambia el código (al publicar en GitHub, por ejemplo),
# pero los módulos propios quedan en memoria con su versión anterior. Si alguno cambió, se recargan todos,
# primero los que no dependen de otros, para que nadie quede usando funciones viejas.
ORDEN = ["fuentes.yahoo", "fuentes.fred", "fuentes.cboe", "fuentes.almacen", "bloques.series", "bloques.indicadores",
         "bloques.comun", "bloques.relativo", "bloques.rotacion", "bloques.volatilidad", "bloques.tendencia", "bloques.tasas",
         "bloques.commodities", "bloques.sectores", "bloques.industrias", "bloques.empresas"]


def _recargar_si_cambiaron():
    propios = sorted((n for n in sys.modules if n.split(".")[0] in ("fuentes", "bloques") and "." in n),
                     key=lambda n: ORDEN.index(n) if n in ORDEN else len(ORDEN))
    fecha = {n: Path(sys.modules[n].__file__).stat().st_mtime for n in propios}
    if all(getattr(sys.modules[n], "_fecha_archivo", None) == fecha[n] for n in propios):
        return
    for n in propios:
        importlib.reload(sys.modules[n])
        sys.modules[n]._fecha_archivo = fecha[n]


_recargar_si_cambiaron()
from fuentes import almacen  # noqa: E402

st.set_page_config(page_title="FreddyDash", page_icon="📊", layout="wide")

pagina = st.navigation({
    "Top": [
        st.Page("paginas/sectores.py", title="Sectores", icon=":material/donut_small:"),
        st.Page("paginas/industrias.py", title="Industrias", icon=":material/factory:"),
        st.Page("paginas/rotacion_sectores.py", title="Rotación Sectores", icon=":material/sync_alt:"),
        st.Page("paginas/rotacion_industrias.py", title="Rotación Industrias", icon=":material/autorenew:"),
    ],
    "Down": [
        st.Page("paginas/empresas.py", title="Empresas", icon=":material/apartment:"),
    ],
    "Macro": [
        st.Page("paginas/tendencias.py", title="Tendencias", icon=":material/trending_up:"),
        st.Page("paginas/economia.py", title="Economía", icon=":material/public:"),
    ],
})
# Cuándo se bajaron los datos por última vez (los baja GitHub Actions; ver README)
sello = almacen.leer_sello()
lineas = [f"{nombre}: {pd.Timestamp(sello[clave]):%d-%m-%Y %H:%M} NY"
          for clave, nombre in (("precios", "Precios"), ("put_call", "Put/Call")) if clave in sello]
if lineas:
    st.sidebar.caption("Última actualización  \n" + "  \n".join(lineas))

pagina.run()
