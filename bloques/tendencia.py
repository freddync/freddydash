"""Macro · Tendencia: SPY, QQQ, IWM y la amplitud del alza (RSP/SPY, IWM/SPY)."""
import plotly.graph_objects as go
import streamlit as st

from bloques.comun import avisar_faltantes, cierres, explicacion, layout, recortar
from bloques.series import ETFS

RATIOS = {"RSP/SPY": ("RSP", "SPY"), "IWM/SPY": ("IWM", "SPY")}

COLORES = {"SPY": "#3b82f6", "QQQ": "#8957e5", "IWM": "#e0823d", "RSP": "#57ab5a",
           "RSP/SPY": "#57ab5a", "IWM/SPY": "#e0823d", "SMA50": "#c69026", "SMA200": "#e5534b"}


def cargar():
    s, errores = cierres(list(ETFS))
    for nombre, (a, b) in RATIOS.items():
        if a in s and b in s:
            s[nombre] = (s[a] / s[b]).dropna()
    return s, errores


def cruces(s):
    """Fechas en que la SMA 50 cruza la SMA 200: True = cruce dorado, False = de la muerte."""
    sma50, sma200 = s.rolling(50).mean(), s.rolling(200).mean()
    arriba = (sma50 > sma200)[sma200.notna()]
    cambio = arriba.ne(arriba.shift()) & arriba.shift().notna()
    return arriba[cambio]


def grafico_detalle(serie, nombre, periodo, fin):
    sma50, sma200 = serie.rolling(50).mean(), serie.rolling(200).mean()
    fig = go.Figure()
    x = recortar(serie, periodo, fin)
    fig.add_scatter(x=x.index, y=x, name=nombre, line=dict(color=COLORES[nombre], width=1.8))
    for sma, etiqueta in ((sma50, "SMA50"), (sma200, "SMA200")):
        m = recortar(sma, periodo, fin)
        fig.add_scatter(x=m.index, y=m, name=etiqueta.replace("SMA", "SMA "),
                        line=dict(color=COLORES[etiqueta], width=1.3, dash="dot"))
    c = recortar(cruces(serie), periodo, fin)
    for dorado, simbolo, color, texto in ((True, "triangle-up", "#57ab5a", "Cruce dorado"),
                                          (False, "triangle-down", "#e5534b", "Cruce de la muerte")):
        f = c[c == dorado].index
        if len(f):
            fig.add_scatter(x=f, y=sma200.loc[f], mode="markers", name=texto,
                            marker=dict(symbol=simbolo, size=12, color=color))
    return layout(fig, f"{nombre}: precio y medias de 50 y 200 días", sufijo="", alto=460)


def grafico_amplitud(s, periodo, fin):
    fig = go.Figure()
    for nombre in RATIOS:
        if nombre in s:
            x = recortar(s[nombre], periodo, fin)
            fig.add_scatter(x=x.index, y=(x / x.iloc[0] - 1) * 100, name=nombre,
                            line=dict(color=COLORES[nombre], width=1.8))
    fig.add_hline(y=0, line=dict(color="#888", width=1))
    return layout(fig, "Amplitud: ¿el resto del mercado acompaña al S&P 500?")


def mostrar(periodo):
    s, errores = cargar()
    avisar_faltantes(errores)
    if "SPY" not in s:
        st.error("Sin datos de SPY; no se puede mostrar el bloque.")
        return

    fin = s["SPY"].index[-1]

    opciones = [t for t in ("SPY", "QQQ", "IWM", "RSP/SPY") if t in s]
    elegido = st.segmented_control("Detalle", opciones, default="SPY", key="detalle_tendencia") or "SPY"
    serie = s[elegido]
    st.plotly_chart(grafico_detalle(serie, elegido, periodo, fin), width="stretch")
    c = cruces(serie)
    ultimo = ""
    if len(c):
        tipo = "dorado" if c.iloc[-1] else "de la muerte"
        ultimo = f" El último cruce de {elegido} fue {tipo}, el {c.index[-1]:%d-%m-%Y}."
    explicacion("El precio junto a sus medias móviles de 50 días (tendencia de mediano plazo) y 200 días "
                "(tendencia de largo plazo). Sobre la media de 200 días, la tendencia de fondo es alcista; bajo "
                "ella, bajista. Cuando la media de 50 cruza hacia arriba a la de 200 es un cruce dorado (triángulo "
                "verde); hacia abajo, un cruce de la muerte (triángulo rojo). Son señales lentas: confirman un "
                "cambio de tendencia más que anticiparlo." + ultimo)

    st.plotly_chart(grafico_amplitud(s, periodo, fin), width="stretch")
    explicacion("Compara contra el S&P 500 normal, donde las empresas más grandes pesan mucho más. RSP/SPY sube "
                "cuando la empresa promedio le gana al índice: el alza es amplia y sana. Si baja mientras el "
                "S&P 500 sube, el índice depende de unas pocas gigantes. IWM/SPY mide lo mismo con las empresas "
                "pequeñas.")
    st.caption("Fuente: Yahoo Finance (precios ajustados por dividendos; durante la sesión, el último precio es "
               "intradía); se actualizan solos varias veces al día.")
