"""Top · Industrias: las industrias dentro de un sector, armadas con las empresas del universo.

Cada industria es un índice de pesos iguales de sus empresas (de datos/universo.csv, con los precios guardados
en datos/precios). Solo se forman industrias con al menos MIN_EMPRESAS empresas.
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from bloques import relativo, sectores, volatilidad
from bloques.comun import clave_cliqueada, ir_a_empresas, precios
from bloques.indicadores import rsi
from fuentes import almacen

DATOS = Path(__file__).resolve().parent.parent / "datos"
MIN_EMPRESAS = 3
PASAN = ("Liderando", "Mejorando")  # cuadrantes del RRG que pasan al nivel siguiente
REF = "SPY"  # las industrias siempre se comparan contra el S&P 500
AMPLITUD_MIN = 50  # % de empresas sobre su media de 50 días para pasar a Empresas


@st.cache_data(show_spinner="Cargando empresas…")
def cargar_empresas(version):
    """version: fechas de modificación de los archivos, para recargar cuando se actualizan."""
    universo = pd.read_csv(DATOS / "universo.csv")
    p = precios()
    return universo, p[[t for t in universo["ticker"] if t in p]].dropna(how="all")


def version():
    return almacen.version(DATOS / "universo.csv", almacen.HISTORIA, almacen.RECIENTE)


def empresas():
    return cargar_empresas(version())


@st.cache_data(show_spinner="Calculando RSI de las empresas…")
def _rsi_empresas(version):
    _, precios = cargar_empresas(version)
    return rsi(precios.ffill())


def rsi_promedio(grupos):
    """RSI 5 promedio diario de las empresas de cada grupo ({clave: [tickers]} → DataFrame por clave)."""
    r = _rsi_empresas(version())
    return pd.DataFrame({k: r[[t for t in ts if t in r]].mean(axis=1) for k, ts in grupos.items()})


def industrias_de(etf):
    """{industria: [tickers con precios]} del sector, solo las que tienen al menos MIN_EMPRESAS empresas."""
    universo, precios = empresas()
    grupos = universo[(universo["etf"] == etf) & universo["ticker"].isin(precios.columns)].groupby("industria")
    return {ind: list(g["ticker"]) for ind, g in grupos if len(g) >= MIN_EMPRESAS}


def todas():
    """{industria: (etf, [tickers])} de todos los sectores, sólo las que tienen al menos MIN_EMPRESAS empresas."""
    return {ind: (etf, tickers) for etf in sectores.SECTORES for ind, tickers in industrias_de(etf).items()}


def indices(miembros):
    _, precios = empresas()
    return {ind: relativo.canasta({t: precios[t].dropna() for t in tickers}) for ind, tickers in miembros.items()}


def amplitud(miembros):
    """% de empresas de cada industria sobre su media de 50 y de 200 días."""
    _, precios = empresas()
    filas = {}
    for ind, tickers in miembros.items():
        p = precios[tickers].ffill()
        filas[ind] = {f"SMA {n}": (p.iloc[-1] > p.rolling(n).mean().iloc[-1]).mean() * 100 for n in (50, 200)}
    return pd.DataFrame(filas).T


def evaluar(etf):
    """Datos del sector: (series, miembros, amplitud, cuadrantes vs SPY, industrias que pasan a Empresas)."""
    s_sec, _ = sectores.cargar()
    miembros = industrias_de(etf)
    s = {**indices(miembros), etf: s_sec[etf], "SPY": s_sec["SPY"]}
    amp = amplitud(miembros)
    cuad = relativo.cuadrantes_actuales(*relativo.rrg(s, miembros, REF))
    pasan = [i for i in miembros if cuad.get(i) in PASAN and amp.loc[i, "SMA 50"] > AMPLITUD_MIN]
    return s, miembros, amp, cuad, pasan


def _corto(texto, n=20):
    return texto if len(texto) <= n else texto[:n - 1] + "…"


def grafico_amplitud(amp, miembros):
    amp = amp.sort_values("SMA 50")
    etiquetas = [f"{i} ({len(miembros[i])})" for i in amp.index]
    fig = go.Figure()
    # Grises neutros: en esta página verde/amarillo/rojo/azul quedan reservados para los cuadrantes
    for col, color in (("SMA 50", "#d0d7de"), ("SMA 200", "#6e7681")):
        fig.add_bar(y=etiquetas, x=amp[col], name=f"Sobre su {col}", orientation="h", marker_color=color,
                    hovertemplate="%{y}: %{x:.0f}%<extra></extra>")
    fig.add_vline(x=AMPLITUD_MIN, line=dict(color="#ffffff", width=1, dash="dot"))
    fig.update_layout(title="Amplitud: % de empresas de cada industria sobre sus medias móviles",
                      barmode="group", height=max(320, 46 * len(amp) + 110), margin=dict(l=10, r=10, t=50, b=10),
                      xaxis=dict(range=[0, 100], ticksuffix="%"),
                      legend=dict(orientation="h", yanchor="top", y=-0.06))
    return fig


def _rgba(color, alfa):
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alfa})"


def elegir_sector():
    """Un botón por sector, pintado con su cuadrante contra SPY y con su semana, fuerza y momentum.

    Ordenados de mejor a peor cuadrante; por defecto queda elegido el primero. Devuelve el ETF elegido.
    """
    res = sectores.resumen()
    prioridad = ["Liderando", "Mejorando", "Debilitándose", "Rezagado"]
    opciones = sorted(res.index, key=lambda e: (prioridad.index(res.loc[e, "cuadrante"])
                                                if res.loc[e, "cuadrante"] in prioridad else 4, sectores.SECTORES[e]))
    if st.session_state.get("sector_industrias") not in opciones:
        st.session_state["sector_industrias"] = opciones[0]
    elegido = st.session_state["sector_industrias"]

    # Estilo de cada botón según su cuadrante (cada botón tiene la clase st-key-<key>)
    colores = {nombre: color for nombre, color in relativo.CUADRANTES.values()}
    css = []
    for e in opciones:
        color = colores.get(res.loc[e, "cuadrante"], "#8b949e")
        activo = e == elegido
        boton = f".st-key-sector_{e} button"
        # Mismo color con y sin el mouse encima (Streamlit lo cambia a gris al pasar el mouse o tras el clic)
        css.append(f"{boton}, {boton}:hover, {boton}:focus, {boton}:active, {boton}:focus-visible "
                   f"{{background:{_rgba(color, 0.55 if activo else 0.22)} !important;"
                   f"border:{'2px solid #ffffff' if activo else f'1px solid {color}'} !important;"
                   f"border-left:8px solid {color} !important;color:#f0f6fc !important;}}"
                   f"{boton}:hover {{filter:brightness(1.15);}}"
                   f"{boton} {{min-height:96px;justify-content:flex-start;text-align:left;}}"
                   f".st-key-sector_{e} button div {{display:block;width:100%;white-space:normal;overflow:visible;}}"
                   f".st-key-sector_{e} button p {{margin:0;line-height:1.35;white-space:normal;}}")
    st.markdown(f"<style>{''.join(css)}</style>", unsafe_allow_html=True)

    columnas = st.columns(4)
    for n, e in enumerate(opciones):
        fila = res.loc[e]
        cambio = f" {fila['por_confirmar']}" if pd.notna(fila["por_confirmar"]) else ""
        etiqueta = (f"**{sectores.ETIQUETAS[e]}**\n\n{fila['cuadrante']}{cambio} · semana {fila['semana']:+.1f} pp\n\n"
                    f"Fuerza {fila['fuerza']:.1f} · Momentum {fila['momentum']:.1f}")
        with columnas[n % 4]:
            st.button(etiqueta, key=f"sector_{e}", width="stretch", wrap=True,
                      on_click=lambda e=e: st.session_state.update(sector_industrias=e))
    st.caption("Color: cuadrante del sector contra SPY. Semana: rendimiento de la última semana contra SPY. "
               "Fuerza y momentum: 100 = igual a SPY.")
    return elegido


def mostrar():
    st.markdown("¿Qué industrias empujan al sector? Cada industria es el promedio, con pesos iguales, de las "
                "empresas de EE.UU. de más de $10B que la forman (mínimo 3). Por defecto se abre el sector "
                "que mejor salió de Sectores.")

    etf = elegir_sector()

    s, miembros, amp, cuad, pasan = evaluar(etf)
    if not miembros:
        st.info("Este sector no tiene industrias con al menos 3 empresas en el universo.")
        return
    ref = REF
    etiquetas = {i: f"{i} ({len(t)})" for i, t in miembros.items()}
    fin = s[ref].index[-1]

    fuerza, momentum = relativo.rrg(s, miembros, ref)

    # De arriba hacia abajo: Liderando, Mejorando, Debilitándose, Rezagado (la cinta se dibuja desde abajo)
    q = relativo.cuadrantes(fuerza, momentum)
    hoy = q.ffill().iloc[-1]
    prioridad = ["Liderando", "Mejorando", "Debilitándose", "Rezagado"]
    orden = sorted(miembros, key=lambda i: (prioridad.index(hoy[i]) if hoy.get(i) in prioridad else 4, i),
                   reverse=True)
    vix = volatilidad.cargar()[0].get("VIX")
    evento = st.plotly_chart(relativo.grafico_cinta(q, fuerza, momentum, orden, etiquetas, None,
                                                    fin, vix=vix, rotulos=etiquetas, semanas=relativo.SEMANAS,
                                                    valores=relativo.relativo_semanal(s, miembros, ref),
                                                    nombre_ref=ref, clic="Clic para ver sus empresas",
                                                    rsi=rsi_promedio(miembros)),
                             width="stretch", on_select="rerun", selection_mode="points", key=f"cinta_{etf}")
    elegida = clave_cliqueada(evento)
    if elegida in miembros:
        ir_a_empresas(sectores.SECTORES[etf], elegida)

    st.markdown("**Pasan a Empresas:** " + (", ".join(pasan) if pasan else "ninguna industria por ahora."))

    st.plotly_chart(relativo.grafico_rrg(fuerza, momentum, relativo.COLA, etiquetas, ref,
                                         cortas={i: _corto(i) for i in miembros}), width="stretch")

    st.plotly_chart(grafico_amplitud(amp, miembros), width="stretch")
    _, precios = empresas()
    st.caption(f"Fuente: Yahoo Finance. Precios de empresas hasta el {precios.index[-1]:%d-%m-%Y} "
               "(se actualizan solos varias veces al día); clasificación de Yahoo.")
