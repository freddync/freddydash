"""Macro · Tendencias: hacia dónde va el mercado y cuánto miedo hay."""
import streamlit as st

from bloques import tendencia, volatilidad
from bloques.comun import PERIODOS

st.title("Tendencias")
st.caption("¿Hacia dónde va el mercado y cuánto miedo hay? Tendencia del mercado y volatilidad.")

periodo = st.segmented_control("Período", list(PERIODOS), default="1A", key="periodo_tendencias") or "1A"

st.header("Tendencia")
st.markdown("¿El mercado está en alza o en baja, y el alza es pareja o depende de unas pocas empresas? Se mira "
            "el S&P 500 (SPY), el Nasdaq 100 (QQQ, tecnología y crecimiento), el Russell 2000 (IWM, empresas "
            "pequeñas) y el S&P 500 con pesos iguales (RSP).")
tendencia.mostrar(periodo)

st.header("Volatilidad")
st.markdown("¿Cuánto miedo hay en el mercado? Los índices de volatilidad miden cuánto movimiento esperan los "
            "inversionistas, a partir de lo que pagan por protegerse con opciones. Las zonas de color de fondo "
            "son referencias aproximadas: verde es calma, naranjo es tensión y rojo es pánico.")
volatilidad.mostrar(periodo)
