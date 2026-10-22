"""Down · el análisis de cada empresa."""
import streamlit as st

from bloques import empresas

st.title("Empresas")
empresas.mostrar()
