"""FreddyDash: dashboard de inversión en tres partes.

Top: el mercado desde arriba (sectores → industrias) y su rotación por velocidad.
Down: el análisis de cada empresa.
Macro: el escenario (tendencias del mercado y economía).
"""
import hmac
import importlib
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Streamlit vuelve a correr app.py y la página cuando cambia el código (al publicar en GitHub, por ejemplo),
# pero los módulos propios quedan en memoria con su versión anterior. Si alguno cambió, se recargan todos,
# primero los que no dependen de otros, para que nadie quede usando funciones viejas.
ORDEN = ["fuentes.yahoo", "fuentes.fred", "fuentes.yahoo_opciones", "fuentes.almacen", "bloques.series", "bloques.indicadores",
         "bloques.comun", "bloques.relativo", "bloques.rotacion", "bloques.volatilidad", "bloques.tendencia", "bloques.tasas",
         "bloques.commodities", "bloques.sectores", "bloques.industrias", "bloques.empresas",
         "bloques.senales"]


def _recargar_si_cambiaron():
    propios = sorted((n for n in sys.modules if n.split(".")[0] in ("fuentes", "bloques") and "." in n),
                     key=lambda n: ORDEN.index(n) if n in ORDEN else len(ORDEN))
    fecha = {n: Path(sys.modules[n].__file__).stat().st_mtime for n in propios}
    if all(getattr(sys.modules[n], "_fecha_archivo", None) == fecha[n] for n in propios):
        return
    for n in propios:
        importlib.reload(sys.modules[n])
        sys.modules[n]._fecha_archivo = fecha[n]


_recargar_si_cambiaron()
from fuentes import almacen  # noqa: E402

st.set_page_config(page_title="FreddyDash", page_icon="📊", layout="wide")


def _pedir_clave():
    """Clave de acceso: se guarda en los secretos de Streamlit (`clave = "..."` en .streamlit/secrets.toml en
    local, o en Settings → Secrets de Streamlit Cloud), nunca en el código. Sin clave configurada no se
    muestra nada. Una vez ingresada, vale mientras la pestaña siga abierta."""
    if st.session_state.get("autenticado"):
        return
    try:
        clave = st.secrets.get("clave")
    except FileNotFoundError:
        clave = None
    st.title("FreddyDash")
    if not clave:
        st.error("Falta configurar la clave del dashboard (secreto `clave`).")
        st.stop()
    with st.form("acceso"):
        escrita = st.text_input("Clave", type="password")
        if st.form_submit_button("Entrar"):
            if hmac.compare_digest(escrita.encode(), str(clave).encode()):
                st.session_state["autenticado"] = True
                st.rerun()
            st.error("Clave incorrecta.")
    st.stop()


# La navegación se arma antes de pedir la clave (oculta mientras no se entra) para que, al entrar, se abra la
# página que estaba en la dirección y no la primera.
pagina = st.navigation({
    "Top": [
        st.Page("paginas/sectores.py", title="Sectores", icon=":material/donut_small:"),
        st.Page("paginas/industrias.py", title="Industrias", icon=":material/factory:"),
        st.Page("paginas/rotacion_sectores.py", title="Rotación Sectores", icon=":material/sync_alt:"),
        st.Page("paginas/rotacion_industrias.py", title="Rotación Industrias", icon=":material/autorenew:"),
    ],
    "Down": [
        st.Page("paginas/empresas.py", title="Empresas", icon=":material/apartment:"),
        st.Page("paginas/senales.py", title="Señales", icon=":material/notifications_active:"),
    ],
    "Macro": [
        st.Page("paginas/tendencias.py", title="Tendencias", icon=":material/trending_up:"),
        st.Page("paginas/economia.py", title="Economía", icon=":material/public:"),
    ],
}, position="sidebar" if st.session_state.get("autenticado") else "hidden")
_pedir_clave()
# Cuándo se bajaron los datos por última vez (los baja GitHub Actions; ver README)
sello = almacen.leer_sello()
lineas = [f"{nombre}: {pd.Timestamp(sello[clave]):%d-%m-%Y %H:%M} NY"
          for clave, nombre in (("precios", "Precios"), ("put_call", "Put/Call")) if clave in sello]
if lineas:
    st.sidebar.caption("Última actualización  \n" + "  \n".join(lineas))

pagina.run()
