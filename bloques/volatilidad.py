"""Macro · Volatilidad: VIX, su estructura de plazos (VIX/VIX3M) y MOVE (bonos)."""
import math

import plotly.graph_objects as go
import streamlit as st

from bloques.comun import avisar_faltantes, cierres, explicacion, layout, recortar

TICKERS = {"^VIX": "VIX", "^VIX3M": "VIX3M", "^MOVE": "MOVE"}

# Zonas de referencia (aproximadas, por convención de mercado): (desde, hasta, nombre, color)
ZONAS = {
    "VIX": [(0, 15, "Calma", "#57ab5a"), (15, 20, "Normal", None),
            (20, 30, "Tensión", "#e0823d"), (30, math.inf, "Pánico", "#e5534b")],
    "VIX/VIX3M": [(0, 0.9, "Calma (curva normal)", "#57ab5a"), (0.9, 1, "Alerta", "#e0823d"),
                  (1, math.inf, "Estrés de corto plazo (curva invertida)", "#e5534b")],
    "MOVE": [(0, 80, "Calma", "#57ab5a"), (80, 120, "Normal", None),
             (120, 150, "Tensión", "#e0823d"), (150, math.inf, "Pánico", "#e5534b")],
}

COLORES = {"VIX": "#3b82f6", "VIX3M": "#8b949e", "VIX/VIX3M": "#8957e5", "MOVE": "#c69026"}


def cargar():
    datos, errores = cierres(list(TICKERS))
    s = {TICKERS[t]: v for t, v in datos.items()}
    if "VIX" in s and "VIX3M" in s:
        s["VIX/VIX3M"] = (s["VIX"] / s["VIX3M"]).dropna()
    return s, [TICKERS[t] for t in errores]


def _bandas(fig, nombre, maximo):
    """Pinta de fondo las zonas de referencia del indicador hasta el máximo visible."""
    for desde, hasta, _, color in ZONAS[nombre]:
        if color and desde < maximo:
            fig.add_hrect(y0=desde, y1=min(hasta, maximo), fillcolor=color, opacity=0.08, line_width=0)


def grafico_vix(s, periodo, fin):
    fig = go.Figure()
    vix = recortar(s["VIX"], periodo, fin)
    maximo = vix.max() * 1.05
    _bandas(fig, "VIX", maximo)
    fig.add_scatter(x=vix.index, y=vix, name="VIX (30 días)", line=dict(color=COLORES["VIX"], width=1.8))
    if "VIX3M" in s:
        v3 = recortar(s["VIX3M"], periodo, fin)
        fig.add_scatter(x=v3.index, y=v3, name="VIX3M (3 meses)", line=dict(color=COLORES["VIX3M"], width=1.3, dash="dot"))
    fig = layout(fig, "VIX: volatilidad esperada del S&P 500", sufijo="")
    fig.update_yaxes(range=[0, maximo])
    return fig


def grafico_simple(s, nombre, titulo, periodo, fin, linea=None):
    fig = go.Figure()
    x = recortar(s[nombre], periodo, fin)
    maximo = x.max() * 1.05
    _bandas(fig, nombre, maximo)
    fig.add_scatter(x=x.index, y=x, name=nombre, line=dict(color=COLORES[nombre], width=1.8))
    if linea is not None:
        fig.add_hline(y=linea, line=dict(color="#888", width=1))
    fig = layout(fig, titulo, sufijo="")
    fig.update_yaxes(range=[x.min() * 0.95, maximo])
    return fig


def mostrar(periodo):
    s, errores = cargar()
    avisar_faltantes(errores)
    if "VIX" not in s:
        st.error("Sin datos del VIX; no se puede mostrar el bloque.")
        return

    fin = s["VIX"].index[-1]
    st.plotly_chart(grafico_vix(s, periodo, fin), width="stretch")
    explicacion("El VIX es la volatilidad que el mercado espera para el S&P 500 en los próximos 30 días, en % "
                "anual. Bajo 15 hay calma, entre 15 y 20 es normal, entre 20 y 30 hay tensión y sobre 30 hay "
                "pánico. Sube cuando las acciones caen. Los saltos sobre 30 suelen coincidir con zonas de "
                "mínimos, porque el pánico ya está en los precios; un VIX muy bajo por mucho tiempo puede ser "
                "complacencia. La línea punteada es el VIX3M, la misma medida a 3 meses.")

    izq, der = st.columns(2)
    with izq:
        if "VIX/VIX3M" in s:
            st.plotly_chart(grafico_simple(s, "VIX/VIX3M", "Estructura de plazos: VIX / VIX3M", periodo, fin, linea=1),
                            width="stretch")
            explicacion("Divide el VIX de 30 días por el de 3 meses. Lo normal es que esté bajo 1: protegerse por "
                        "más tiempo cuesta más. Bajo 0.9 hay calma y entre 0.9 y 1 hay alerta. Sobre 1 la curva "
                        "se invierte: el mercado paga más por protegerse ya que más adelante, señal de estrés "
                        "inmediato. Suele ser una señal más clara que el nivel del VIX solo.")
    with der:
        if "MOVE" in s:
            st.plotly_chart(grafico_simple(s, "MOVE", "MOVE: volatilidad esperada de los bonos", periodo, fin),
                            width="stretch")
            explicacion("El \"VIX de los bonos\": la volatilidad que el mercado espera para los bonos del Tesoro. "
                        "Bajo 80 hay calma, entre 80 y 120 es normal, entre 120 y 150 hay tensión y sobre 150 "
                        "hay pánico. Como los bonos son la base para valorar todo lo demás, un salto del MOVE "
                        "suele anticipar estrés en las acciones.")
    st.caption("Fuente: Yahoo Finance; los datos se actualizan solos varias veces al día.")
