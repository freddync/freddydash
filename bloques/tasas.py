"""Macro · Tasas: inflación, Fed y curva del Tesoro de EE.UU. (todo desde FRED)."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from bloques.comun import avisar_faltantes, explicacion, layout, recortar
from fuentes import almacen

# Curva a plazo constante: todos los plazos con la misma metodología del Tesoro
PLAZOS = {"3M": "DGS3MO", "1A": "DGS1", "2A": "DGS2", "5A": "DGS5", "10A": "DGS10", "30A": "DGS30"}
IDS = ["DFEDTAR", "DFEDTARU", "CPIAUCSL", *PLAZOS.values()]


COLORES = {
    "CPI": "#e5534b", "FED": "#8957e5",
    "3M": "#2aa3b8", "1A": "#57ab5a", "2A": "#a0a0a0", "5A": "#e0823d", "10A": "#3b82f6", "30A": "#c69026",
}


def cargar():
    s, errores = almacen.fred(IDS)
    # La Fed fijaba una tasa única hasta 2008-12-15; desde ahí, un rango. Se usa el techo.
    if "DFEDTARU" in s:
        techo = s.pop("DFEDTARU")
        antes = s.pop("DFEDTAR", pd.Series(dtype=float))
        s["FED"] = pd.concat([antes[antes.index < techo.index[0]], techo])
    if "CPIAUCSL" in s:
        s["CPI"] = (s.pop("CPIAUCSL").pct_change(12) * 100).dropna()
    return s, errores


def grafico_estructura(s, periodo, fin):
    fig = go.Figure()

    def linea(clave, nombre, color, ancho=1.6, guion=None, forma="linear", visible=True):
        if clave in s:
            x = recortar(s[clave], periodo, fin)
            fig.add_scatter(x=x.index, y=x, name=nombre, line=dict(color=color, width=ancho, dash=guion, shape=forma),
                            visible=True if visible else "legendonly")

    linea("CPI", "Inflación CPI (interanual)", COLORES["CPI"], 2.3)
    fig.add_hline(y=2, line=dict(color=COLORES["CPI"], dash="dot", width=1), opacity=0.7,
                  annotation_text="Meta 2%", annotation_position="bottom left")
    linea("FED", "Fed (techo)", COLORES["FED"], 2.2, forma="hv")
    for plazo, sid in PLAZOS.items():
        linea(sid, f"Tesoro {plazo}", COLORES[plazo], 2.0 if plazo == "10A" else 1.4,
              guion=None if plazo == "10A" else "dot", visible=plazo not in ("2A", "30A"))
    return layout(fig, "Inflación, Fed y curva del Tesoro")


def mostrar(periodo):
    s, errores = cargar()
    avisar_faltantes(errores)
    if "DGS10" not in s:
        st.error("Sin datos del Tesoro a 10 años; no se puede mostrar el gráfico.")
        return
    st.plotly_chart(grafico_estructura(s, periodo, s["DGS10"].index[-1]), width="stretch")
    explicacion("La línea morada es la tasa que fija la Fed y la roja, la inflación (CPI, variación en 12 meses) "
                "contra la meta del 2%. Si la Fed está bien por encima de la inflación, su política es "
                "restrictiva: encarece el crédito para enfriar la economía. Si está por debajo, estimula. "
                "Las demás líneas son los bonos del Tesoro: los de corto plazo siguen de cerca a la Fed y los de "
                "largo plazo reflejan lo que el mercado espera de crecimiento e inflación. Los plazos de 2 y "
                "30 años están ocultos; se muestran con un clic en la leyenda.")
    st.caption("Fuente: FRED (Reserva Federal de St. Louis); los datos se actualizan solos cada día hábil.")
