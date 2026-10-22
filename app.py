"""Fdash: dashboard de inversión en dos partes.

Top: el mercado desde arriba (macro → sectores → industrias).
Down: el análisis de cada empresa.
"""
import streamlit as st

st.set_page_config(page_title="Fdash", page_icon="📊", layout="wide")

pagina = st.navigation({
    "Top": [
        st.Page("paginas/macro.py", title="Macro", icon=":material/public:"),
        st.Page("paginas/sectores.py", title="Sectores", icon=":material/donut_small:"),
        st.Page("paginas/industrias.py", title="Industrias", icon=":material/factory:"),
    ],
    "Down": [
        st.Page("paginas/empresas.py", title="Empresas", icon=":material/apartment:"),
    ],
})
pagina.run()
