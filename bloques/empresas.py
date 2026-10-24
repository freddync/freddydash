"""Down · screener general de empresas: RSI 5, MACD 6/13/5 y ratio Put/Call.

Universo: las empresas de datos/universo.csv (el mismo de Industrias), con los precios de
datos/precios y el Put/Call de datos/put_call.csv (scripts/actualizar_opciones.py).
"""
import hashlib

import pandas as pd
import streamlit as st
from plotly.subplots import make_subplots

from bloques import industrias, sectores
from bloques.indicadores import rsi
from fuentes import almacen, yahoo

COLUMNAS = ["Ticker", "Nombre", "Sector", "Industria", "RSI 5", "MACD 6/13/5", "Put/Call"]
ORDEN_MACD = ["Pre-cruce", "Alza", "Perdiendo fuerza", "Baja", "Mixta"]  # al ordenar por MACD
MESES_DETALLE = 12  # meses que muestra la ventana de detalle (con 2 años bajados, la SMA 200 queda completa)
MACD_RAPIDA, MACD_LENTA, MACD_SENAL = 6, 13, 5
# Medias sobre el precio en la ventana de detalle: (nombre, tipo, días, color)
MEDIAS = [("SMA 200", "sma", 200, "#f0f6fc"), ("SMA 100", "sma", 100, "#e3b341"),
          ("EMA 21", "ema", 21, "#58a6ff"), ("EMA 5", "ema", 5, "#bc8cff")]


def macd(precios, rapida=MACD_RAPIDA, lenta=MACD_LENTA, senal=MACD_SENAL):
    """(línea MACD, línea de señal, histograma) para cada columna."""
    linea = precios.ewm(span=rapida, adjust=False).mean() - precios.ewm(span=lenta, adjust=False).mean()
    linea_senal = linea.ewm(span=senal, adjust=False).mean()
    return linea, linea_senal, linea - linea_senal


def categoria_macd(linea, senal):
    """Categoría de hoy según el MACD, su señal y el histograma (comparados contra ayer), por columna.

    En orden de prioridad:
      Pre-cruce         MACD bajo cero y bajo su señal, con el histograma subiendo: se acerca al cruce al alza.
      Perdiendo fuerza  MACD sobre cero y sobre su señal, con el histograma bajando: se acerca al cruce a la baja.
      Alza              MACD y señal subiendo.
      Baja              MACD y señal bajando.
      Mixta             cualquier otra combinación.
    """
    hist = linea - senal
    m, s_, h = linea.iloc[-1], senal.iloc[-1], hist.iloc[-1]
    dm, ds, dh = m - linea.iloc[-2], s_ - senal.iloc[-2], h - hist.iloc[-2]
    cat = pd.Series("Mixta", index=linea.columns)
    cat[(dm < 0) & (ds < 0)] = "Baja"
    cat[(dm > 0) & (ds > 0)] = "Alza"
    cat[(m > 0) & (h > 0) & (dh < 0)] = "Perdiendo fuerza"
    cat[(m < 0) & (h < 0) & (dh > 0)] = "Pre-cruce"
    cat[m.isna() | s_.isna()] = None
    return cat


@st.cache_data(show_spinner="Calculando indicadores…")
def tabla(version):
    """version: fechas de modificación de los archivos de datos, para recalcular cuando se actualizan."""
    universo, precios = industrias.empresas()
    precios = precios.ffill()
    linea, senal, hist = macd(precios)
    ultimo = pd.DataFrame({
        "RSI 5": rsi(precios).iloc[-1],
        "MACD 6/13/5": categoria_macd(linea, senal),
        "MACD": linea.iloc[-1], "Señal MACD": senal.iloc[-1], "Histograma MACD": hist.iloc[-1],
    })
    archivo_pc = industrias.DATOS / "put_call.csv"
    put_call = pd.read_csv(archivo_pc, index_col="ticker") if archivo_pc.exists() else pd.DataFrame()
    t = universo.set_index("ticker")
    df = pd.DataFrame({
        "Nombre": t["nombre"],
        "Sector": t["etf"].map(sectores.SECTORES),
        "Industria": t["industria"],
    }).join(ultimo).join(put_call.get("put_call", pd.Series(dtype=float)).rename("Put/Call"))
    return df.rename_axis("Ticker").reset_index(), precios.index[-1], put_call.get("fecha", pd.Series()).max()


@st.cache_data(ttl=3600, show_spinner="Bajando la historia de la empresa…")
def historial(ticker):
    return yahoo.historial(ticker)


def grafico_detalle(h, ticker):
    """Precio (velas con medias SMA 200/100 y EMA 21/5), volumen, RSI 5 y MACD 6/13/5 de los últimos
    MESES_DETALLE meses. Todo se calcula con la historia completa y después se recorta."""
    cierre = h[["Close"]].rename(columns={"Close": ticker})
    r = rsi(cierre)[ticker]
    linea, senal, hist = (x[ticker] for x in macd(cierre))
    medias = {nombre: (h["Close"].rolling(n).mean() if tipo == "sma" else h["Close"].ewm(span=n, adjust=False).mean())
              for nombre, tipo, n, _ in MEDIAS}
    desde = h.index[-1] - pd.DateOffset(months=MESES_DETALLE)
    h, r, linea, senal, hist = (x[x.index >= desde] for x in (h, r, linea, senal, hist))
    medias = {k: v[v.index >= desde] for k, v in medias.items()}
    sube = h["Close"] >= h["Open"]

    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.46, 0.14, 0.2, 0.2],
                        subplot_titles=("Precio", "Volumen", "RSI 5", "MACD 6/13/5"))
    fig.add_candlestick(x=h.index, open=h["Open"], high=h["High"], low=h["Low"], close=h["Close"], name="Precio",
                        increasing_line_color="#3fb950", decreasing_line_color="#f85149", row=1, col=1,
                        showlegend=False)
    for nombre, _, _, color in MEDIAS:
        m = medias[nombre]
        fig.add_scatter(x=m.index, y=m, name=nombre, line=dict(color=color, width=1.3), row=1, col=1)
    fig.add_bar(x=h.index, y=h["Volume"], name="Volumen", row=2, col=1, showlegend=False,
                marker_color=["#3fb950" if s else "#f85149" for s in sube], opacity=0.7)
    fig.add_scatter(x=r.index, y=r, name="RSI 5", line=dict(color="#d0d7de", width=1.5), row=3, col=1,
                    showlegend=False)
    for nivel, color in ((70, "#f85149"), (30, "#3fb950")):
        fig.add_hline(y=nivel, line=dict(color=color, width=1, dash="dot"), row=3, col=1)
    fig.add_bar(x=hist.index, y=hist, name="Histograma", row=4, col=1, showlegend=False,
                marker_color=["#3fb950" if v >= 0 else "#f85149" for v in hist], opacity=0.6)
    fig.add_scatter(x=linea.index, y=linea, name="MACD", line=dict(color="#d0d7de", width=1.5), row=4, col=1,
                    showlegend=False)
    fig.add_scatter(x=senal.index, y=senal, name="Señal", line=dict(color="#e0823d", width=1.3), row=4, col=1,
                    showlegend=False)
    fig.update_yaxes(range=[0, 100], row=3, col=1)
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])], rangeslider_visible=False)
    fig.update_layout(height=840, margin=dict(l=10, r=10, t=60, b=10), hovermode="x unified",
                      legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0))
    return fig


@st.cache_data(ttl=1800, show_spinner="Buscando noticias…")
def noticias(ticker):
    try:
        return yahoo.noticias(ticker), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _md(texto):
    """Texto tal cual en markdown: sin que $ se lea como fórmula ni [] como enlace."""
    for c in ("\\", "$", "[", "]", "*", "_"):
        texto = texto.replace(c, "\\" + c)
    return texto


def mostrar_noticias(ticker):
    with st.expander("📰 Últimas noticias", expanded=False):
        notas, error = noticias(ticker)
        if error:
            st.caption(f"No se pudieron cargar las noticias: {error}")
        elif not notas:
            st.caption("Yahoo no tiene noticias recientes para esta empresa.")
        else:
            for n in notas:
                cuando = f"{n['fecha']:%d-%m-%Y %H:%M} NY" if n["fecha"] is not None else ""
                otros = f" · también: {', '.join(n['otros'][:4])}" if n["otros"] else ""
                st.markdown(f"[{_md(n['titulo'])}]({n['link']})  \n"
                            f"<small style='color:#8b93a3'>{_md(n['fuente'])} · {cuando}{otros}</small>",
                            unsafe_allow_html=True)
            st.caption("Fuente: Yahoo Finance (se actualiza cada 30 minutos).")


@st.dialog("Empresa", width="large")
def ver_empresa(fila):
    st.subheader(f"{fila['Nombre']} ({fila['Ticker']})")
    st.caption(f"{fila['Sector']} · {fila['Industria']}")
    h = historial(fila["Ticker"])
    if h.empty:
        st.error("No se pudo bajar la historia de esta empresa desde Yahoo.")
        return
    pc = f"{fila['Put/Call']:.2f}" if pd.notna(fila["Put/Call"]) else "sin datos"
    st.markdown(f"**RSI 5:** {fila['RSI 5']:.1f} · **MACD 6/13/5:** {fila['MACD 6/13/5']} · **Put/Call:** {pc} · "
                f"**Último cierre:** ${h['Close'].iloc[-1]:,.2f} ({h.index[-1]:%d-%m-%Y})")
    mostrar_noticias(fila["Ticker"])
    st.plotly_chart(grafico_detalle(h, fila["Ticker"]), width="stretch")


def _filtrar_y_ordenar(df):
    # Si se llegó desde una cinta (clic en un sector o industria), aplicar ese filtro
    destino = st.session_state.pop("ir_a_filtros", None)
    if destino:
        st.session_state["filtro_sector"] = destino["sector"]
        st.session_state["filtro_industria"] = destino["industria"]
    c1, c2, c3, c4 = st.columns([2, 3, 1.6, 2])
    elegidos_sec = c1.multiselect("Sector", sorted(df["Sector"].dropna().unique()), key="filtro_sector",
                                  placeholder="Todos")
    if elegidos_sec:
        df = df[df["Sector"].isin(elegidos_sec)]
    elegidas_ind = c2.multiselect("Industria", sorted(df["Industria"].dropna().unique()), key="filtro_industria",
                                  placeholder="Todas")
    if elegidas_ind:
        df = df[df["Industria"].isin(elegidas_ind)]
    columna = c3.selectbox("Ordenar por", COLUMNAS, index=COLUMNAS.index("RSI 5"), key="orden_columna")
    sentido = c4.segmented_control("Orden", ["Menor a mayor", "Mayor a menor"], default="Menor a mayor",
                                   key="orden_sentido") or "Menor a mayor"
    clave = None
    if columna == "MACD 6/13/5":
        clave = lambda s: s.map({c: i for i, c in enumerate(ORDEN_MACD)})  # noqa: E731
    estado = repr((sorted(elegidos_sec), sorted(elegidas_ind), columna, sentido))
    return df.sort_values(columna, ascending=sentido == "Menor a mayor", key=clave, na_position="last"), estado


def mostrar():
    df, fecha_precios, fecha_pc = tabla(industrias.version() + almacen.version(industrias.DATOS / "put_call.csv"))
    vista, estado = _filtrar_y_ordenar(df)
    vista = vista[COLUMNAS].reset_index(drop=True)

    # La tabla recuerda la POSICIÓN de la fila elegida, no la empresa: si cambian el orden o los filtros, otra
    # empresa queda en esa posición y se abriría su ventana. Por eso la clave cambia con ellos y la selección
    # parte de cero.
    clave_tabla = "tabla_empresas_" + hashlib.md5(estado.encode()).hexdigest()[:10]
    evento = st.dataframe(
        vista, hide_index=True, width="stretch", height=640, key=clave_tabla,
        on_select="rerun", selection_mode="single-row",
        column_config={
            "RSI 5": st.column_config.NumberColumn(format="%.1f"),
            "Put/Call": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    st.caption(f"{len(vista)} de {len(df)} empresas. Haz clic en una fila para ver su precio, volumen, RSI 5 y "
               f"MACD. Precios al {fecha_precios:%d-%m-%Y}; Put/Call de Cboe al "
               f"{fecha_pc if isinstance(fecha_pc, str) else 'sin datos'} (se actualiza solo cada día hábil): open "
               "interest de puts / calls, todos los vencimientos.")

    # Abrir la ventana solo cuando se elige una empresa nueva (no en cada recarga mientras siga elegida)
    filas = evento.selection.rows
    elegida = (clave_tabla, vista.iloc[filas[0]]["Ticker"]) if filas else None
    if elegida != st.session_state.get("empresa_vista"):
        st.session_state["empresa_vista"] = elegida
        if elegida:
            ver_empresa(vista.iloc[filas[0]])
