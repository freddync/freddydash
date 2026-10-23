"""Fdash: dashboard de inversión en tres partes.

Top: el mercado desde arriba (sectores → industrias).
Down: el análisis de cada empresa.
Macro: el escenario (tendencias del mercado y economía).
"""
import pandas as pd
import streamlit as st

from fuentes import almacen

st.set_page_config(page_title="Fdash", page_icon="📊", layout="wide")

pagina = st.navigation({
    "Top": [
        st.Page("paginas/sectores.py", title="Sectores", icon=":material/donut_small:"),
        st.Page("paginas/industrias.py", title="Industrias", icon=":material/factory:"),
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
