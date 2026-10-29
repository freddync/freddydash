"""Top · rotación de sectores por velocidad."""
import pandas as pd
import streamlit as st

from bloques import rotacion, sectores
from bloques.comun import avisar_faltantes, ir_a_empresas

st.title("Rotación Sectores")
st.markdown("¿Qué sectores tienen la tendencia que más rápido le gana al S&P 500? Cada fin de mes se eligen los 2 "
            "o 3 más rápidos y se mantienen hasta el cierre del mes siguiente. Es una señal lenta, pensada para "
            "saber en qué sectores buscar empresas.")

s, errores = sectores.cargar()
avisar_faltantes(errores)
if "SPY" not in s:
    st.error("Sin datos de SPY; no se puede calcular la rotación.")
    st.stop()
precios = pd.DataFrame({k: s[k] for k in [*sectores.SECTORES, "SPY"] if k in s}).sort_index()

rotacion.mostrar(
    precios, "SPY", sectores.ETIQUETAS, cupos=(2, 3), buffers=(0, 1), nombre="sectores",
    orden=sectores.DEFENSIVOS + sectores.CICLICOS,
    al_clic=lambda etf: ir_a_empresas(sectores.SECTORES[etf]), clic="Clic para ver sus empresas",
    texto="Mide qué tan rápido sube la tendencia larga (media de 200 y 250 días) de cada sector comparada con la "
          "de SPY. Cada fin de mes se quedan los 2 o 3 sectores más rápidos; uno que ya estaba elegido se mantiene "
          "mientras no caiga más de un puesto bajo el corte, para no rotar por ruido. El peso es mayor en los "
          "sectores más volátiles. Hasta el último día hábil del mes, la columna con * y los porcentajes de las "
          "barras son provisionales. En el backtest 2000-2026 rindió parecido a SPY, con rachas largas por debajo: "
          "dice dónde está el impulso, no garantiza ganarle al mercado.")
st.caption("Fuente: Yahoo Finance (precios ajustados por dividendos); se actualizan solos varias veces al día.")
