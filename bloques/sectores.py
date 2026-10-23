"""Top · Sectores: los 11 sectores del S&P 500 (ETFs SPDR) comparados contra SPY."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from bloques import relativo, volatilidad
from bloques.comun import avisar_faltantes, cierres, clave_cliqueada, layout, recortar
from bloques.series import SECTORES

CICLICOS = ["XLK", "XLY", "XLF", "XLI", "XLB", "XLE", "XLC"]
DEFENSIVOS = ["XLP", "XLV", "XLU", "XLRE"]

ETIQUETAS = {t: f"{n} ({t})" for t, n in SECTORES.items()}
PERIODO = pd.DateOffset(months=6)  # ventana fija de la fuerza relativa y de cíclicos contra defensivos


def cargar():
    return cierres([*SECTORES, "SPY"])


def rsi_por_sector():
    """RSI 5 promedio diario de las empresas del universo en cada sector (por ETF)."""
    from bloques import industrias  # aquí y no arriba: industrias importa este módulo
    universo, precios = industrias.empresas()
    grupos = universo[universo["ticker"].isin(precios.columns)].groupby("etf")["ticker"].apply(list).to_dict()
    return industrias.rsi_promedio(grupos)


def resumen():
    """Estado de hoy de cada sector contra SPY (lo usa Industrias para elegir sector).

    DataFrame indexado por ETF con: cuadrante (confirmado), por_confirmar (texto del cambio en curso, si lo hay),
    fuerza, momentum y semana (rendimiento de la última semana contra SPY, en puntos porcentuales).
    """
    s, errores = cargar()
    if errores:
        cargar.clear()
    fuerza, momentum = relativo.rrg(s, SECTORES, "SPY")
    cuad = relativo.cuadrantes_actuales(fuerza, momentum)
    pendientes = {k: relativo.texto_confirmar(*v) for k, v in relativo.por_confirmar(fuerza, momentum).items()}
    semana = relativo.relativo_semanal(s, SECTORES, "SPY", semanas=1).iloc[:, -1]
    return pd.DataFrame({"cuadrante": pd.Series(cuad), "por_confirmar": pd.Series(pendientes, dtype=object),
                         "fuerza": fuerza.ffill().iloc[-1],
                         "momentum": momentum.ffill().iloc[-1], "semana": semana}).reindex(list(SECTORES))


def grafico_ciclicos(s, periodo, fin):
    ratio = (relativo.canasta({k: s[k] for k in CICLICOS if k in s})
             / relativo.canasta({k: s[k] for k in DEFENSIVOS if k in s}))
    sma = ratio.rolling(50).mean()
    x, m = recortar(ratio, periodo, fin), recortar(sma, periodo, fin)
    base = x.iloc[0]
    fig = go.Figure()
    fig.add_scatter(x=x.index, y=(x / base - 1) * 100, name="Cíclicos / defensivos",
                    line=dict(color="#f0f6fc", width=1.8))
    fig.add_scatter(x=m.index, y=(m / base - 1) * 100, name="SMA 50",
                    line=dict(color="#8b949e", width=1.3, dash="dot"))
    fig.add_hline(y=0, line=dict(color="#888", width=1))
    return layout(fig, "Cíclicos contra defensivos, últimos 6 meses (variación)")


def mostrar():
    s, errores = cargar()
    avisar_faltantes(errores)
    if "SPY" not in s:
        st.error("Sin datos de SPY; no se puede mostrar el nivel.")
        return
    fin = s["SPY"].index[-1]

    st.markdown("¿En qué parte del mercado está la fuerza? Los 11 sectores del S&P 500 (ETFs SPDR), siempre "
                "comparados contra el S&P 500 (SPY): a este nivel no importa si un sector sube, sino si le gana "
                "al mercado. Los sectores que lideran o están mejorando son los que pasan a Industrias.")

    fuerza, momentum = relativo.rrg(s, SECTORES, "SPY")
    vix = volatilidad.cargar()[0].get("VIX")
    evento = st.plotly_chart(relativo.grafico_cinta(
        relativo.cuadrantes(fuerza, momentum), fuerza, momentum, DEFENSIVOS + CICLICOS,
        ETIQUETAS, None, fin, vix=vix, rotulos=ETIQUETAS, semanas=relativo.SEMANAS,
        valores=relativo.relativo_semanal(s, SECTORES, "SPY"), nombre_ref="SPY",
        separador=(DEFENSIVOS, "▼ Defensivos", "▲ Cíclicos"), clic="Clic para ver sus industrias",
        rsi=rsi_por_sector()),
        width="stretch", on_select="rerun", selection_mode="points", key="cinta_sectores")
    elegido = clave_cliqueada(evento)
    if elegido in SECTORES:
        # Abrir Industrias con ese sector elegido (Industrias usa esta clave para su sector activo)
        st.session_state["sector_industrias"] = elegido
        st.switch_page("paginas/industrias.py")

    st.markdown("##### Rotación relativa")
    st.plotly_chart(relativo.grafico_rrg(fuerza, momentum, relativo.COLA, ETIQUETAS, "SPY"), width="stretch")

    st.plotly_chart(relativo.grafico_grilla(s, SECTORES, "SPY", PERIODO, fin, ETIQUETAS,
                                            "Fuerza relativa de cada sector contra SPY, últimos 6 meses (100 = hace 6 meses)"
                                            "<br><sup>Color = cuadrante confirmado de hoy</sup>",
                                            cuadrante_hoy=relativo.cuadrantes_actuales(fuerza, momentum)),
                    width="stretch")

    st.plotly_chart(grafico_ciclicos(s, PERIODO, fin), width="stretch")
    st.caption("Fuente: Yahoo Finance (precios ajustados por dividendos); se actualizan solos varias veces al día.")
