"""Top · rotación de industrias por velocidad."""
import pandas as pd
import streamlit as st

from bloques import industrias, rotacion, sectores
from bloques.comun import ir_a_empresas

st.title("Rotación Industrias")
st.markdown("¿Qué industrias, de todos los sectores, tienen la tendencia que más rápido le gana al S&P 500? Es la "
            "misma regla de Rotación Sectores aplicada a las industrias: cada una es el promedio, con pesos "
            "iguales, de sus empresas del universo (mínimo 3), y cada fin de mes se eligen las 5 u 8 más rápidas.")

s_sec, _ = sectores.cargar()
if "SPY" not in s_sec:
    st.error("Sin datos de SPY; no se puede calcular la rotación.")
    st.stop()
miembros = industrias.todas()
indices = industrias.indices({ind: tickers for ind, (_, tickers) in miembros.items()})
precios = pd.DataFrame({**indices, "SPY": s_sec["SPY"]}).sort_index()
etiquetas = {ind: f"{ind} ({etf}, {len(t)})" for ind, (etf, t) in miembros.items()}

rotacion.mostrar(
    precios, "SPY", etiquetas, cupos=(5, 8), buffers=(0, 3), nombre="industrias", maximo=25,
    al_clic=lambda ind: ir_a_empresas(sectores.SECTORES[miembros[ind][0]], ind), clic="Clic para ver sus empresas",
    texto="Mide qué tan rápido sube la tendencia larga (media de 200 y 250 días) de cada industria comparada con la "
          "de SPY. Cada fin de mes se quedan las 5 u 8 más rápidas; una que ya estaba elegida se mantiene mientras no "
          "caiga más de tres puestos bajo el corte. El peso es mayor en las más volátiles. Entre paréntesis: su "
          "sector y cuántas empresas la forman. El ranking muestra las 25 más rápidas (y las elegidas, si alguna "
          "quedara fuera); la cinta, sólo las que fueron elegidas alguna vez en los últimos 5 años. Hasta el último "
          "día hábil del mes, la columna con * y los porcentajes son provisionales. A diferencia de los sectores, "
          "esta versión no tiene backtest, y las industrias se arman con las empresas de hoy: las que quebraron o "
          "salieron del universo no están en la historia.")
_, p_emp = industrias.empresas()
st.caption(f"Fuente: Yahoo Finance. Precios de empresas hasta el {p_emp.index[-1]:%d-%m-%Y}; clasificación de Yahoo.")
