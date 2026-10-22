"""Piezas compartidas por los bloques: selector de período y formato de gráficos."""
import pandas as pd
import streamlit as st

from fuentes import almacen

PERIODOS = {
    "1A": pd.DateOffset(years=1),
    "5A": pd.DateOffset(years=5),
}


def recortar(s, periodo, fin):
    """periodo: un nombre de PERIODOS ("1A", "5A") o un desfase fijo (pd.DateOffset)."""
    desde = PERIODOS[periodo] if isinstance(periodo, str) else periodo
    return s[s.index >= fin - desde]


def layout(fig, titulo, sufijo="%", alto=440):
    fig.update_layout(
        title=titulo, height=alto, hovermode="x unified",
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="top", y=-0.08),
        yaxis=dict(ticksuffix=sufijo),
    )
    return fig


def explicacion(texto):
    """Texto bajo un gráfico: qué muestra y cómo leerlo."""
    st.markdown(f"**Cómo leerlo.** {texto}")


@st.cache_data(show_spinner="Cargando precios…")
def _precios(version):
    """version: fechas de modificación de los archivos de precios, para recargar cuando se actualizan."""
    return almacen.precios()


def precios():
    """Cierres ajustados guardados en el repositorio (fechas × tickers)."""
    return _precios(almacen.version())


def cierres(tickers):
    """({ticker: serie}, [tickers sin datos guardados])."""
    return almacen.cierres(precios(), tickers)


def avisar_faltantes(errores):
    """Avisa qué series no están entre los datos guardados."""
    if errores:
        st.warning(f"Sin datos guardados de: {', '.join(errores)}. Se completarán en la próxima actualización "
                   "automática.")


def clave_cliqueada(evento):
    """Clave (sector o industria) de la franja cliqueada en una cinta con clic=True, o None."""
    for punto in (evento.selection.points if evento else []):
        dato = punto.get("customdata")
        if dato is not None:
            return dato[0] if isinstance(dato, (list, tuple)) else dato
    return None


def ir_a_empresas(sector, industria=None):
    """Abre Empresas filtrada por un sector (nombre en español) y, opcionalmente, una industria."""
    st.session_state["ir_a_filtros"] = {"sector": [sector], "industria": [industria] if industria else []}
    st.switch_page("paginas/empresas.py")
