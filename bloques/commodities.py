"""Macro · Economía: precios de commodities (energía, metales preciosos e industriales)."""
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from bloques import tendencia
from bloques.comun import avisar_faltantes, cierres, explicacion, layout, recortar
from bloques.series import COMMODITIES
from fuentes import almacen

COLORES = {"Petróleo WTI": "#8957e5", "Gas natural": "#2aa3b8", "Oro": "#e3b341", "Plata": "#d0d7de",
           "Cobre": "#db6d28", "Cobre/Oro": "#db6d28", "Tesoro 10A": "#3b82f6"}


def cargar():
    datos, errores = cierres(list(COMMODITIES))
    s = {COMMODITIES[t]: v for t, v in datos.items()}
    if "Cobre" in s and "Oro" in s:
        s["Cobre/Oro"] = (s["Cobre"] / s["Oro"]).dropna()
    return s, [COMMODITIES[t] for t in errores]


def grafico_rendimiento(s, periodo, fin):
    fig = go.Figure()
    for nombre in COMMODITIES.values():
        if nombre in s:
            x = recortar(s[nombre], periodo, fin)
            fig.add_scatter(x=x.index, y=(x / x.iloc[0] - 1) * 100, name=nombre,
                            line=dict(color=COLORES[nombre], width=1.8))
    fig.add_hline(y=0, line=dict(color="#888", width=1))
    return layout(fig, "Rendimiento acumulado en el período")


def grafico_cobre_oro(s, tasa, periodo, fin):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    x = recortar(s["Cobre/Oro"], periodo, fin)
    fig.add_scatter(x=x.index, y=x * 1000, name="Cobre/Oro (×1000)", line=dict(color=COLORES["Cobre/Oro"], width=1.8))
    if tasa is not None:
        t = recortar(tasa, periodo, fin)
        fig.add_scatter(x=t.index, y=t, name="Tesoro 10A (eje derecho)", secondary_y=True,
                        line=dict(color=COLORES["Tesoro 10A"], width=1.5, dash="dot"))
        fig.update_yaxes(ticksuffix="%", secondary_y=True, showgrid=False)
    layout(fig, "Cobre/Oro y la tasa del Tesoro a 10 años", sufijo="")
    return fig


def mostrar(periodo):
    s, errores = cargar()
    avisar_faltantes(errores)
    if not s:
        st.error("Sin datos de commodities; no se puede mostrar el bloque.")
        return
    fin = max(v.index[-1] for v in s.values())

    st.plotly_chart(grafico_rendimiento(s, periodo, fin), width="stretch")
    explicacion("Cuánto subió o bajó cada commodity desde el inicio del período. El petróleo y el gas siguen la "
                "demanda de energía y los conflictos de oferta; el cobre, la actividad industrial (se le dice "
                "\"el doctor cobre\" porque anticipa el ciclo); el oro y la plata suben cuando se busca refugio o "
                "se teme inflación. Un petróleo en alza presiona la inflación y, con ella, las tasas.")

    opciones = [n for n in COMMODITIES.values() if n in s]
    elegido = st.segmented_control("Detalle", opciones, default=opciones[0], key="detalle_commodities") or opciones[0]
    st.plotly_chart(tendencia.grafico_detalle(s[elegido], elegido, periodo, fin, color=COLORES[elegido]),
                    width="stretch")
    explicacion("El precio junto a sus medias de 50 y 200 días: sobre la media de 200, la tendencia de fondo es "
                "alcista. Los triángulos marcan los cruces de las medias (verde, dorado; rojo, de la muerte).")

    if "Cobre/Oro" in s:
        tasa, _ = almacen.fred(["DGS10"])
        st.plotly_chart(grafico_cobre_oro(s, tasa.get("DGS10"), periodo, fin), width="stretch")
        explicacion("El cobre se usa para producir y el oro, para protegerse: si el cobre le gana al oro, el mercado "
                    "apuesta por crecimiento; si pierde, por desaceleración o miedo. Por eso suele moverse junto "
                    "con la tasa del Tesoro a 10 años, que también sube con las expectativas de crecimiento e "
                    "inflación. Cuando se separan, una de las dos se está adelantando.")
    st.caption("Fuente: Yahoo Finance (futuros del contrato más cercano; los cambios de contrato pueden dejar saltos "
               "chicos) y FRED; se actualizan solos varias veces al día.")
