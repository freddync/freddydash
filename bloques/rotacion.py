"""Top · Rotación por velocidad: lo que tiene la tendencia que más rápido le gana a SPY, elegido cada mes.

Velocidad de cada serie: filtro de Kalman sobre la pendiente diaria de log(SMA n), en % por día.
Velocidad relativa: la de la serie menos la de SPY (se muestra anualizada, ×252).
Cada fin de mes se eligen las más rápidas con un ensamble de configuraciones
(SMA 200/250 × cupos × con/sin buffer) y pesos proporcionales a su volatilidad de 63 días.
Con buffer, una elegida se mantiene mientras no caiga más de `buffer` puestos bajo el corte.

Para sectores viene del backtest de Analisis/rotacion_final.py (2000-2026, señal al cierre y ejecución al
open siguiente): 2 o 3 sectores de 11, buffer de 1 puesto. Para industrias se usa la misma regla con los
cupos escalados al tamaño del universo (5 u 8 de ~80, buffer de 3 puestos); esa versión no tiene backtest.
"""
import itertools

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from bloques.comun import clave_cliqueada, explicacion
from bloques.relativo import CUADRANTES

SMAS = (200, 250)
Q_VEL, R_VEL = 0.002, 0.35  # filtro de Kalman de la velocidad (equivale a una EMA de ~26 días)
VENTANA_VOL = 63
MINIMO_DIAS = 260  # historia mínima de una serie para poder elegirla
MESES = 60  # meses de la historia de selección (5 años)

AZUL = CUADRANTES[(False, True)][1]


def _kalman(valores, q, r):
    """Filtro de Kalman 1D causal (paseo aleatorio): cada dato sólo usa los anteriores."""
    out = np.full(len(valores), np.nan)
    x, p = None, 1.0
    for i, z in enumerate(valores):
        if np.isnan(z):
            out[i] = np.nan if x is None else x
            continue
        if x is None:
            x = z
        else:
            p_pred = p + q
            k = p_pred / (p_pred + r)
            x, p = x + k * (z - x), (1 - k) * p_pred
        out[i] = x
    return out


def velocidad_relativa(precios, claves, ref, sma):
    """Velocidad de la SMA de cada clave menos la de la referencia, en % por día."""
    pendiente = np.log(precios[[*claves, ref]].rolling(sma).mean()).diff() * 100
    vel = pendiente.apply(lambda c: pd.Series(_kalman(c.values, Q_VEL, R_VEL), index=c.index))
    return vel[claves].sub(vel[ref], axis=0)


def _fines_de_mes(indice, incluir_ultimo):
    """True el último día hábil de cada mes. El último dato sólo cuenta si incluir_ultimo
    (el mes en curso todavía no cierra: con True se ve la selección "si el mes cerrara hoy")."""
    mes = pd.Series(indice.to_period("M"), index=indice)
    fin = mes != mes.shift(-1)
    fin.iloc[-1] = incluir_ultimo
    return fin.values


def _top_k(score, valido, k, buffer, fines):
    """Selección top-k que sólo cambia a fin de mes; una elegida se mantiene mientras su rank ≤ k+buffer."""
    rk = score.where(valido).rank(axis=1, ascending=False, method="first").values
    out = np.zeros(rk.shape, dtype=bool)
    actual = np.zeros(rk.shape[1], dtype=bool)
    for d in range(rk.shape[0]):
        if fines[d]:
            r = np.nan_to_num(rk[d], nan=1e9)
            nuevo = actual & (r <= k + buffer)
            libres = max(k - nuevo.sum(), 0)
            candidatos = np.argsort(np.where(nuevo, 1e9, r))[:libres]
            nuevo[candidatos[r[candidatos] < 1e9]] = True
            actual = nuevo
        out[d] = actual & ~np.isnan(rk[d])
    return pd.DataFrame(out, index=score.index, columns=score.columns)


def seleccion(precios, claves, ref, cupos, buffers, incluir_ultimo=False):
    """Pesos diarios del ensamble (fechas × claves; suman 1 o 0), que sólo cambian a fin de mes."""
    valido = precios[claves].notna().cumsum() > MINIMO_DIAS
    vol = np.log(precios[claves]).diff().rolling(VENTANA_VOL).std()
    fines = _fines_de_mes(precios.index, incluir_ultimo)
    es_fin = pd.Series(fines, index=precios.index)
    pesos = []
    for sma in SMAS:
        v = velocidad_relativa(precios, claves, ref, sma)
        for k, b in itertools.product(cupos, buffers):
            elegidos = _top_k(v, valido & v.notna(), k, b, fines)
            # Pesos ∝ volatilidad, fijados el día de la elección
            bruto = vol.where(elegidos, 0.0).fillna(0.0)
            w = bruto.div(bruto.sum(axis=1).replace(0, np.nan), axis=0)
            pesos.append(w.where(es_fin, np.nan, axis=0).ffill().fillna(0.0))
    return sum(pesos) / len(pesos)


@st.cache_data(show_spinner="Calculando la rotación por velocidad…")
def calcular(precios, ref, cupos, buffers):
    """precios: fechas × (claves + ref). Devuelve {"vigente": pesos al último cierre de mes, "provisional": si el
    mes cerrara hoy, "velocidad": velocidad relativa anualizada (promedio SMA 200 y 250), "historia": pesos de
    cada fin de mes, "fecha_vigente", "fecha"}."""
    claves = [c for c in precios.columns if c != ref]
    # Un día sin dato dejaría la SMA vacía durante n días: se usa el último cierre conocido
    precios = precios.ffill()
    vigente = seleccion(precios, claves, ref, cupos, buffers, incluir_ultimo=False)
    provisional = seleccion(precios, claves, ref, cupos, buffers, incluir_ultimo=True)
    velocidad = sum(velocidad_relativa(precios, claves, ref, s) for s in SMAS) / len(SMAS) * 252
    fines = _fines_de_mes(precios.index, incluir_ultimo=False)
    historia = vigente[fines].iloc[-MESES:]
    historia = historia[historia.sum(axis=1) > 0]
    return {"vigente": vigente.iloc[-1], "provisional": provisional.iloc[-1], "velocidad": velocidad,
            "historia": historia, "fecha_vigente": historia.index[-1] if len(historia) else None,
            "fecha": precios.index[-1]}


def grafico_ranking(r, etiquetas, nombre, maximo=None, clic=None):
    """Barras: velocidad relativa de hoy, de la más rápida (arriba) a la más lenta; en azul las elegidas si el mes
    cerrara hoy. maximo: mostrar sólo las `maximo` más rápidas (más las elegidas que queden fuera)."""
    v = r["velocidad"].iloc[-1].dropna().sort_values(ascending=False)
    prov, vig = r["provisional"].reindex(v.index).fillna(0), r["vigente"].reindex(v.index).fillna(0)
    if maximo and len(v) > maximo:
        v = v[(np.arange(len(v)) < maximo) | (prov > 0).values | (vig > 0).values]
        prov, vig = prov[v.index], vig[v.index]
    v, prov, vig = v[::-1], prov[::-1], vig[::-1]  # Plotly dibuja la primera barra abajo
    detalle = [f"Velocidad {x:+.1f}% anual vs SPY<br>Peso si el mes cerrara hoy: {p:.0%}<br>Peso vigente: {w:.0%}"
               + (f"<br><i>{clic}</i>" if clic else "") for x, p, w in zip(v, prov, vig)]
    fig = go.Figure(go.Bar(x=v, y=[etiquetas.get(k, k) for k in v.index], orientation="h",
                           marker_color=[AZUL if p > 0 else "#484f58" for p in prov],
                           text=[f"{p:.0%}" if p > 0 else "" for p in prov], textposition="outside",
                           customdata=list(zip(v.index, detalle)),
                           hovertemplate="<b>%{y}</b><br>%{customdata[1]}<extra></extra>"))
    fig.add_vline(x=0, line=dict(color="#888", width=1))
    # Espacio a la derecha para el % y el 0 siempre visible
    margen = v.abs().max() * 0.25
    rango = [min(v.min(), 0) - (margen if v.min() < 0 else margen / 3), max(v.max(), 0) + margen]
    recorte = (f"las {maximo} más rápidas" if maximo and len(r["velocidad"].columns) > maximo
               else f"{'todas las' if nombre.endswith('as') else 'todos los'} {nombre}")
    fig.update_layout(title=f"Velocidad de la tendencia contra SPY al {r['fecha']:%d-%m-%Y} ({recorte})<br><sup>"
                            "Pendiente anualizada de la SMA 200/250 menos la de SPY. Azul y % = peso si el mes cerrara hoy</sup>",
                      height=max(440, 26 * len(v) + 140), margin=dict(l=10, r=10, t=70, b=10), showlegend=False,
                      xaxis=dict(ticksuffix="%", range=rango, title="Más lento que SPY ←  → Más rápido que SPY"))
    return fig


def grafico_historia(r, orden, etiquetas, nombre):
    """Cinta mensual: una franja por serie; cada mes, el peso que tuvo en la selección (más azul = más peso).
    orden: de abajo hacia arriba."""
    h = r["historia"].reindex(columns=orden).fillna(0.0)
    prov = r["provisional"].reindex(orden).fillna(0.0)
    meses = [f"{f:%m-%y}" for f in h.index]
    if r["fecha"] > h.index[-1]:  # el mes en curso: selección provisional, con asterisco
        h = pd.concat([h, prov.to_frame(r["fecha"]).T])
        meses.append(f"{r['fecha']:%m-%y}*")
    z = h.T.values
    # Las columnas son angostas para escribir el %: va en el detalle al pasar el mouse
    detalle = [[f"{etiquetas.get(k, k)}<br>{m}: peso {p:.0%}" for m, p in zip(meses, fila)]
               for k, fila in zip(orden, z)]
    fig = go.Figure(go.Heatmap(z=z, x=meses, y=[etiquetas.get(k, k) for k in orden], zmin=0, zmax=0.6,
                               colorscale=[[0, "#161b22"], [0.15, "#1e3a5f"], [1, "#58a6ff"]], showscale=False,
                               xgap=1, ygap=3, customdata=detalle, hovertemplate="%{customdata}<extra></extra>"))
    elegidos = "elegidas" if nombre.endswith("as") else "elegidos"
    fig.update_layout(title=f"{nombre.capitalize()} {elegidos} al cierre de cada mes (últimos 5 años)<br><sup>Más azul = "
                            "más peso; * = mes en curso, provisional hasta su último día hábil</sup>",
                      height=max(34 * len(orden), 300) + 110, margin=dict(l=10, r=10, t=70, b=10),
                      xaxis=dict(type="category", tickangle=-90, tickfont=dict(size=10)))
    return fig


def mostrar(precios, ref, etiquetas, cupos, buffers, nombre, orden=None, maximo=None, al_clic=None, clic=None,
            texto=""):
    """Sección completa: selección vigente, ranking de hoy, historia mensual y "Cómo leerlo".

    precios: fechas × (claves + ref). nombre: "sectores" o "industrias" (para títulos).
    orden: orden de la historia, de abajo hacia arriba (por defecto, de menos a más peso acumulado).
    maximo: barras a mostrar en el ranking. al_clic(clave): qué hacer al cliquear una barra; clic: texto del aviso.
    texto: explicación de la página, para el "Cómo leerlo".
    """
    r = calcular(precios, ref, tuple(cupos), tuple(buffers))
    if r["fecha_vigente"] is None:
        st.info("Todavía no hay historia suficiente para la rotación por velocidad.")
        return
    vig = r["vigente"][r["vigente"] > 0.005].sort_values(ascending=False)
    st.markdown(f"**Selección vigente** (cierre del {r['fecha_vigente']:%d-%m-%Y}): "
                + ", ".join(f"{etiquetas.get(k, k)} {p:.0%}" for k, p in vig.items()))
    evento = st.plotly_chart(grafico_ranking(r, etiquetas, nombre, maximo, clic), width="stretch",
                             on_select="rerun" if al_clic else "ignore", selection_mode="points",
                             key=f"ranking_{nombre}")
    elegido = clave_cliqueada(evento) if al_clic else None
    if elegido is not None:
        al_clic(elegido)
    if orden is None:
        # Sólo las que alguna vez fueron elegidas en la ventana, de menos a más peso acumulado
        h = r["historia"].sum()
        orden = list(h[h > 0].sort_values().index)
        orden += [k for k in r["provisional"][r["provisional"] > 0].index if k not in orden]
    st.plotly_chart(grafico_historia(r, orden, etiquetas, nombre), width="stretch")
    explicacion(texto)
