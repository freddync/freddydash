"""Down · Señales de la estrategia swing en megacaps (validada en Analisis/Tecnico, ver ESTRATEGIA.md).

Entrada ★ (al cierre de un día):
  1. la EMA 5 cruza hacia arriba la EMA 21,
  2. la SMA 100 está plana o bajando (subió ≤ 0,13% en 20 sesiones),
  3. el mercado está agitado: volatilidad de 20 días del QQQ > su volatilidad de 200 días.
Salida: el cierre cae 10% bajo el máximo cierre desde la entrada (trailing stop sobre cierres).
Cartera del modelo: 10 cupos, una posición por acción; si sobran señales, primero las de mayor capitalización.

FreddyDash guarda solo cierres, así que el modelo compra y vende al CIERRE del día siguiente a la señal
(el backtest original usaba la apertura; la diferencia es chica para operaciones de ~80 días).
Todo se calcula con sesiones cerradas: si la última vela es del día en curso, sus señales se muestran aparte
como provisorias.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from bloques import comun
from bloques.series import MEGACAPS
from fuentes import almacen

PEND_SMA100_MAX = 0.13      # % de cambio de la SMA 100 en 20 sesiones
VOL_CORTA, VOL_LARGA = 20, 200
TRAILING = 0.10
CUPOS = 10
INICIO_MODELO = "2023-01-01"
BRECHA_CERCA = 1.5          # "cerca de señal": EMA 5 a menos de este % bajo la EMA 21
CIERRE_NY = (16, 10)        # después de esta hora (NY) la vela del día se considera cerrada


# ---------------------------------------------------------------- cálculo

def volatilidad(cierre, n):
    """Volatilidad anualizada (%) de n días: desviación de los retornos logarítmicos diarios × √252."""
    return 100 * np.log(cierre).diff().rolling(n).std() * np.sqrt(252)


def indicadores(c, qqq):
    """c: cierres de las megacaps (fechas × tickers) en los días hábiles del QQQ."""
    ema5, ema21 = c.ewm(span=5, adjust=False).mean(), c.ewm(span=21, adjust=False).mean()
    sma100 = c.rolling(100).mean()
    pend = 100 * (sma100 / sma100.shift(20) - 1)
    arriba = (ema5 > ema21) & c.notna()
    cruce = arriba & ~arriba.shift(1, fill_value=True)
    v20, v200 = volatilidad(qqq, VOL_CORTA), volatilidad(qqq, VOL_LARGA)
    agitado = (v20 > v200).fillna(False)
    senal = cruce & (pend <= PEND_SMA100_MAX) & pd.DataFrame({t: agitado for t in c.columns})
    return {"ema5": ema5, "ema21": ema21, "sma100": sma100, "pend": pend, "senal": senal,
            "v20": v20, "v200": v200, "agitado": agitado}


def modelo(c, senal, inicio=INICIO_MODELO):
    """Recorre la estrategia día a día con cierres. Devuelve (abiertas, operaciones cerradas,
    señales del último día en orden de prioridad, ventas pendientes para el próximo día)."""
    fechas = c.index[c.index >= inicio]
    cols = list(c.columns)
    precio = c.loc[fechas].to_numpy()
    sen = senal.loc[fechas].to_numpy()
    pos, ops, compras, ventas = {}, [], [], []
    for k, f in enumerate(fechas):
        for j in ventas:                                     # se vende al cierre del día siguiente a la señal
            p = pos.pop(j)
            ops.append({"Ticker": cols[j], "Entrada": p["fecha"], "Precio entrada": p["px"], "Salida": f,
                        "Precio salida": precio[k, j], "Retorno %": 100 * (precio[k, j] / p["px"] - 1),
                        "Días": k - p["k"]})
        for j in compras:                                    # se compra al cierre del día siguiente a la señal
            if len(pos) >= CUPOS:
                break
            if np.isfinite(precio[k, j]):
                pos[j] = {"fecha": f, "px": precio[k, j], "max": precio[k, j], "k": k}
        ventas = []
        for j, p in pos.items():
            if np.isfinite(precio[k, j]):
                p["max"] = max(p["max"], precio[k, j])
                if precio[k, j] <= p["max"] * (1 - TRAILING):
                    ventas.append(j)
        compras = [j for j in range(len(cols)) if sen[k, j] and j not in pos]
    abiertas = [{"Ticker": cols[j], "Entrada": p["fecha"], "Precio entrada": p["px"], "Cierre": precio[-1, j],
                 "Retorno %": 100 * (precio[-1, j] / p["px"] - 1), "Máximo": p["max"],
                 "Stop": p["max"] * (1 - TRAILING), "Distancia al stop %": 100 * (precio[-1, j] / (p["max"] * (1 - TRAILING)) - 1),
                 "Vender": j in ventas}
                for j, p in pos.items()]
    return (pd.DataFrame(abiertas), pd.DataFrame(ops), [cols[j] for j in compras], [cols[j] for j in ventas])


def ultima_cerrada(indice, sello):
    """Última sesión cerrada: si la última vela es de hoy y se bajó antes del cierre de NY, es provisoria."""
    ultimo = indice[-1]
    if not sello:
        return ultimo, False
    bajada = pd.Timestamp(sello)
    if ultimo.date() == bajada.date() and (bajada.hour, bajada.minute) < CIERRE_NY and len(indice) > 1:
        return indice[-2], True
    return ultimo, False


@st.cache_data(max_entries=1, show_spinner="Calculando señales…")
def calcular(version, sello):
    """version / sello: cambian cuando llegan precios nuevos, para recalcular."""
    p = comun.precios()
    qqq = p["QQQ"].dropna()
    tickers = [t for t in MEGACAPS if t in p and p[t].notna().any()]
    faltan = [t for t in MEGACAPS if t not in tickers]
    c = p[tickers].reindex(qqq.index).ffill()
    c = c.where(p[tickers].reindex(qqq.index).bfill().notna())   # sin precios antes de que la acción cotice
    fecha, provisoria = ultima_cerrada(qqq.index, sello)
    oficial = indicadores(c.loc[:fecha], qqq.loc[:fecha])
    abiertas, ops, compras, ventas = modelo(c.loc[:fecha], oficial["senal"])
    prov = None
    if provisoria:
        todo = indicadores(c, qqq)
        ab_p, _, compras_p, _ = modelo(c, todo["senal"])
        prov = {"compras": compras_p, "agitado": bool(todo["agitado"].iloc[-1]), "fecha": c.index[-1],
                "v20": todo["v20"].iloc[-1], "v200": todo["v200"].iloc[-1],
                "ventas": ab_p[ab_p["Vender"]]["Ticker"].tolist() if len(ab_p) else []}
    return {"c": c.loc[:fecha], "ind": oficial, "abiertas": abiertas, "ops": ops, "compras": compras,
            "ventas": ventas, "fecha": fecha, "prov": prov, "faltan": faltan}


# ---------------------------------------------------------------- vista

def _nombre(t):
    return MEGACAPS.get(t, t)


def _interruptor(r):
    ind, fecha = r["ind"], r["fecha"]
    v20, v200 = ind["v20"], ind["v200"]
    on = bool(ind["agitado"].loc[fecha])
    estado = "🟢 **Encendido**: se pueden tomar señales de compra" if on else "⚪ **Apagado**: no se toman señales de compra"
    st.markdown(f"{estado}. Volatilidad del QQQ a 20 días **{v20.loc[fecha]:.1f}%** contra **{v200.loc[fecha]:.1f}%** "
                f"a 200 días.")
    a, b = comun.recortar(v20, "1A", fecha), comun.recortar(v200, "1A", fecha)
    fig = go.Figure()
    fig.add_scatter(x=a.index, y=a, name="Vol 20 días", line=dict(color="#58a6ff", width=1.5))
    fig.add_scatter(x=b.index, y=b, name="Vol 200 días", line=dict(color="#e3b341", width=2))
    encendido = comun.recortar(ind["agitado"], "1A", fecha)
    tramos = (encendido != encendido.shift()).cumsum()[encendido]
    for _, g in tramos.groupby(tramos):
        fig.add_vrect(x0=g.index[0], x1=g.index[-1], fillcolor="#3fb950", opacity=0.12, line_width=0)
    st.plotly_chart(comun.layout(fig, "Interruptor de mercado: volatilidad del QQQ", alto=300), width="stretch")
    comun.explicacion("Cuando la volatilidad de 20 días (azul) supera a la de 200 días (amarilla), el mercado está más "
                      "agitado que su promedio reciente y el interruptor se enciende (zonas verdes). Solo entonces se "
                      "toman las señales de compra: los mejores cruces del backtest salieron de correcciones con el "
                      "mercado nervioso.")


def _tabla_compras(r):
    ind, fecha = r["ind"], r["fecha"]
    abiertas = r["abiertas"]
    libres = CUPOS - len(abiertas) + int(abiertas["Vender"].sum() if len(abiertas) else 0)
    st.subheader("Comprar")
    if not r["compras"]:
        st.info("Sin señales de compra al último cierre.")
        return
    filas = [{"Ticker": t, "Empresa": _nombre(t), "Cierre": r["c"].at[fecha, t],
              "Pendiente SMA 100 %": ind["pend"].at[fecha, t],
              "Cupo del modelo": "Sí" if i < libres else "Sin cupo"} for i, t in enumerate(r["compras"])]
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch",
                 column_config={"Cierre": st.column_config.NumberColumn(format="$%.2f"),
                                "Pendiente SMA 100 %": st.column_config.NumberColumn(format="%.2f")})
    st.caption(f"Señales ★ del cierre del {fecha:%d-%m-%Y}: la EMA 5 cruzó sobre la EMA 21, con la SMA 100 plana o "
               f"bajando y el interruptor encendido. El modelo tiene {max(libres, 0)} de {CUPOS} cupos libres; el orden "
               "es de mayor a menor capitalización.")


def _tabla_posiciones(r):
    ab = r["abiertas"]
    st.subheader("Vender")
    vender = ab[ab["Vender"]] if len(ab) else ab
    if vender.empty:
        st.info("Ninguna posición del modelo tocó su stop.")
    else:
        st.dataframe(vender.assign(Empresa=vender["Ticker"].map(_nombre))[
            ["Ticker", "Empresa", "Entrada", "Precio entrada", "Cierre", "Retorno %", "Stop"]],
            hide_index=True, width="stretch", column_config=_formato())
        st.caption("Posiciones del modelo cuyo cierre cayó 10% o más bajo su máximo desde la entrada.")

    st.subheader("Posiciones del modelo")
    if ab.empty:
        st.info("El modelo no tiene posiciones abiertas.")
        return
    vista = ab.assign(Empresa=ab["Ticker"].map(_nombre)).sort_values("Distancia al stop %")
    st.dataframe(vista[["Ticker", "Empresa", "Entrada", "Precio entrada", "Cierre", "Retorno %", "Máximo", "Stop",
                        "Distancia al stop %"]], hide_index=True, width="stretch", column_config=_formato())
    comun.explicacion("Lo que tendría abierto el modelo si hubiera seguido todas las señales desde 2023 (10 cupos). "
                      "**Stop** es el máximo cierre desde la entrada menos 10%: si un cierre queda en o bajo ese nivel, "
                      "se vende. **Distancia al stop** es cuánto puede caer el precio antes de tocarlo. Tus posiciones "
                      "reales pueden ser otras: úsalas como referencia.")


def _formato():
    return {"Entrada": st.column_config.DateColumn(format="DD-MM-YYYY"),
            "Salida": st.column_config.DateColumn(format="DD-MM-YYYY"),
            "Precio entrada": st.column_config.NumberColumn(format="$%.2f"),
            "Precio salida": st.column_config.NumberColumn(format="$%.2f"),
            "Cierre": st.column_config.NumberColumn(format="$%.2f"),
            "Máximo": st.column_config.NumberColumn(format="$%.2f"),
            "Stop": st.column_config.NumberColumn(format="$%.2f"),
            "Retorno %": st.column_config.NumberColumn(format="%+.1f"),
            "Distancia al stop %": st.column_config.NumberColumn(format="%.1f")}


def _cerca(r):
    ind, fecha, c = r["ind"], r["fecha"], r["c"]
    en_cartera = set(r["abiertas"]["Ticker"]) if len(r["abiertas"]) else set()
    brecha = 100 * (ind["ema21"].loc[fecha] - ind["ema5"].loc[fecha]) / ind["ema21"].loc[fecha]
    plana = ind["pend"].loc[fecha] <= PEND_SMA100_MAX
    m = plana & (brecha > 0) & (brecha <= BRECHA_CERCA) & ~brecha.index.isin(en_cartera)
    st.subheader("Cerca de señal")
    if not m.any():
        st.info("Ninguna megacap está cerca de una señal.")
        return
    t = pd.DataFrame({"Ticker": brecha[m].index, "Empresa": [_nombre(x) for x in brecha[m].index],
                      "Cierre": c.loc[fecha, m], "EMA 5 bajo EMA 21 %": brecha[m],
                      "Pendiente SMA 100 %": ind["pend"].loc[fecha, m]}).sort_values("EMA 5 bajo EMA 21 %")
    st.dataframe(t, hide_index=True, width="stretch",
                 column_config={"Cierre": st.column_config.NumberColumn(format="$%.2f"),
                                "EMA 5 bajo EMA 21 %": st.column_config.NumberColumn(format="%.2f"),
                                "Pendiente SMA 100 %": st.column_config.NumberColumn(format="%.2f")})
    comun.explicacion(f"Megacaps con la SMA 100 plana o bajando y la EMA 5 a menos de {BRECHA_CERCA}% bajo la EMA 21: "
                      "si la EMA 5 cruza hacia arriba con el interruptor encendido, aparecerán en Comprar.")


def _grafico(r):
    st.subheader("Gráfico")
    c, ind, fecha = r["c"], r["ind"], r["fecha"]
    ab, ops = r["abiertas"], r["ops"]
    sugeridos = list(dict.fromkeys([*r["compras"], *(ab["Ticker"] if len(ab) else []), *c.columns]))
    t = st.selectbox("Empresa", sugeridos, format_func=lambda x: f"{x} · {_nombre(x)}", key="senales_ticker")
    s = comun.recortar(c[t].dropna(), "1A", fecha)
    fig = go.Figure()
    fig.add_scatter(x=s.index, y=s, name="Cierre", line=dict(color="#d0d7de", width=1.6))
    for nombre, serie, color in (("EMA 5", ind["ema5"][t], "#bc8cff"), ("EMA 21", ind["ema21"][t], "#58a6ff"),
                                 ("SMA 100", ind["sma100"][t], "#e3b341")):
        x = serie.loc[s.index]
        fig.add_scatter(x=x.index, y=x, name=nombre, line=dict(color=color, width=1.2))
    sen = ind["senal"][t].loc[s.index]
    sen = sen[sen]
    fig.add_scatter(x=sen.index, y=s.loc[sen.index] * 0.97, mode="markers", name="Señal ★",
                    marker=dict(symbol="star", size=14, color="#3fb950"))
    o = ops[ops["Ticker"] == t] if len(ops) else ops
    o = o[o["Salida"] >= s.index[0]] if len(o) else o
    if len(o):
        fig.add_scatter(x=o["Salida"], y=o["Precio salida"] * 1.03, mode="markers+text", name="Venta del modelo",
                        marker=dict(symbol="triangle-down", size=12, color="#f85149"),
                        text=[f"{x:+.1f}%" for x in o["Retorno %"]], textposition="top center")
    if len(ab) and t in set(ab["Ticker"]):
        p = ab[ab["Ticker"] == t].iloc[0]
        fig.add_hline(y=p["Stop"], line=dict(color="#f85149", dash="dash", width=1.2),
                      annotation_text=f"stop {p['Stop']:.2f}", annotation_position="bottom left")
        if p["Entrada"] >= s.index[0]:      # si entró hace más de un año, la línea alargaría el eje
            fig.add_vline(x=p["Entrada"], line=dict(color="#3fb950", dash="dot", width=1))
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    st.plotly_chart(comun.layout(fig, f"{t} · último año", sufijo="", alto=460), width="stretch")
    comun.explicacion("Estrellas verdes: señales ★ (cruce de la EMA 5 sobre la EMA 21 con la SMA 100 plana y el "
                      "interruptor encendido). Triángulos rojos: ventas del modelo, con su resultado. Si el modelo tiene "
                      "la acción, la línea punteada vertical marca la entrada y la roja horizontal el stop vigente.")


def _historial(r):
    ops = r["ops"]
    with st.expander("Historial del modelo desde 2023"):
        if ops.empty:
            st.caption("Sin operaciones cerradas.")
            return
        st.markdown(f"**{len(ops)} operaciones cerradas** · ganadoras {100 * (ops['Retorno %'] > 0).mean():.0f}% · "
                    f"retorno medio {ops['Retorno %'].mean():+.1f}% · mediana {ops['Retorno %'].median():+.1f}% · "
                    f"{ops['Días'].mean():.0f} días en promedio.")
        st.dataframe(ops.assign(Empresa=ops["Ticker"].map(_nombre)).sort_values("Salida", ascending=False)[
            ["Ticker", "Empresa", "Entrada", "Precio entrada", "Salida", "Precio salida", "Retorno %", "Días"]],
            hide_index=True, width="stretch", column_config=_formato())


def _advertencias():
    with st.expander("Antes de usar estas señales"):
        st.markdown(
            "- **Backtest 2023–2026** (74 megacaps, 10 cupos): +160% contra +100% del SPY y +150% del QQQ, con menos "
            "volatilidad y caída máxima de −15%.\n"
            "- **Sesgo de lista**: son las megacaps de hoy, las que ganaron. Mantener esa misma lista con la misma "
            "exposición rindió ~+130%; la ventaja contra SPY y QQQ viene en buena parte de la lista.\n"
            "- **La operación típica gana poco** (mediana ~+4%): el resultado depende de pocos ganadores grandes, "
            "así que es clave no cortar las posiciones antes del stop.\n"
            "- **Solo megacaps**: en large caps la estrategia perdió contra el SPY.\n"
            "- El interruptor (vol 20 > vol 200 del QQQ) se eligió después de probar varias variantes y los umbrales con "
            "datos 2023–2025: 2026 no es una prueba completamente limpia.")


def mostrar():
    sello = almacen.leer_sello().get("precios")
    r = calcular(almacen.version(), sello)
    comun.avisar_faltantes(r["faltan"])
    st.caption(f"Señales al cierre del **{r['fecha']:%d-%m-%Y}**. Se actúa el día hábil siguiente.")
    if r["prov"]:
        p = r["prov"]
        with st.expander(f"⏳ Provisorio: el día {p['fecha']:%d-%m-%Y} todavía no cierra"):
            st.markdown(f"Con el precio de la última actualización ({sello} NY), el interruptor estaría "
                        f"{'encendido' if p['agitado'] else 'apagado'} (vol 20 {p['v20']:.1f}% · vol 200 {p['v200']:.1f}%).  \n"
                        f"Compras posibles: {', '.join(p['compras']) or 'ninguna'} · "
                        f"Ventas posibles: {', '.join(p['ventas']) or 'ninguna'}.  \n"
                        "Puede cambiar hasta el cierre: la señal oficial es la del cierre.")
    _interruptor(r)
    c1, c2 = st.columns(2)
    with c1:
        _tabla_compras(r)
    with c2:
        _cerca(r)
    _tabla_posiciones(r)
    _grafico(r)
    _historial(r)
    _advertencias()
