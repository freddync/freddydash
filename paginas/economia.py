"""Macro · Economía: tasas, inflación y precios de commodities."""
import streamlit as st

from bloques import commodities, tasas
from bloques.comun import PERIODOS

st.title("Economía")
st.caption("¿En qué parte del ciclo está la economía? Tasas e inflación, y precios de commodities.")

periodo = st.segmented_control("Período", list(PERIODOS), default="1A", key="periodo_economia") or "1A"

st.header("Tasas e inflación")
st.markdown("Las tasas son el precio del dinero y el punto de partida para valorar cualquier activo: ¿la Fed "
            "está frenando o estimulando la economía?")
tasas.mostrar(periodo)

st.header("Commodities")
st.markdown("Las materias primas que mueve la economía real: energía, metales industriales y metales de refugio.")
commodities.mostrar(periodo)
