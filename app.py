"""Fdash: dashboard de inversión en tres partes.

Top: el mercado desde arriba (sectores → industrias).
Down: el análisis de cada empresa.
Macro: el escenario (tendencias del mercado y economía).
"""
import streamlit as st

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
pagina.run()
