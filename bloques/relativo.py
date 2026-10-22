"""Comparaciones relativas contra una referencia, compartidas por Sectores e Industrias.

Todas las funciones reciben `s` ({clave: serie de precios}), las `claves` a comparar y la clave de
la referencia (`ref`), y `etiquetas` ({clave: nombre para mostrar}).
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from bloques.comun import recortar

SEMANAS = 52  # semanas de la cinta de rotación y de sus rendimientos semanales
COLA = 6  # semanas de recorrido (cola) en el gráfico de rotación

CUADRANTES = {  # (fuerza > 100, momentum > 100): (nombre, color)
    (True, True): ("Liderando", "#57ab5a"), (True, False): ("Debilitándose", "#c69026"),
    (False, False): ("Rezagado", "#e5534b"), (False, True): ("Mejorando", "#3b82f6"),
}



def canasta(series):
    """Índice de pesos iguales: promedio de los retornos diarios de las series disponibles cada día."""
    retornos = pd.DataFrame({k: v.pct_change() for k, v in series.items()}).mean(axis=1)
    return (1 + retornos.fillna(0)).cumprod()


def cierres_semanales(indice, semanas=None):
    """Último día con datos de cada semana (lunes a viernes); con `semanas`, solo las últimas."""
    idx = pd.DatetimeIndex(indice).unique().sort_values()
    fechas = pd.DatetimeIndex(pd.Series(idx, index=idx).groupby(idx.to_period("W-FRI")).last().values)
    return fechas[-semanas:] if semanas else fechas


def rotulos_semanas(fechas):
    """Rótulos dd-mm de cada semana; la semana en curso lleva asterisco porque todavía no termina."""
    hoy = pd.Timestamp.now().normalize().to_period("W-FRI")
    return [f"{f:%d-%m}" + ("*" if i == len(fechas) - 1 and f.to_period("W-FRI") == hoy else "")
            for i, f in enumerate(fechas)]


def relativo_semanal(s, claves, ref, semanas=SEMANAS):
    """Rendimiento de cada semana de cada clave menos el de la referencia, en puntos porcentuales.

    Columnas: las últimas `semanas` semanas, de la más antigua a la más reciente, rotuladas con el último
    día con datos de cada una (la semana en curso termina hoy).
    """
    precios = pd.DataFrame({k: s[k] for k in [*claves, ref] if k in s}).sort_index()
    # Hasta el último día con datos de las series comparadas: si la referencia está más al día (por ejemplo,
    # SPY en vivo frente a industrias armadas con precios guardados), la última semana quedaría sin dato
    hasta = max(precios[k].last_valid_index() for k in claves if k in precios)
    precios = precios.loc[:hasta]
    # Último cierre real de cada semana (lunes a viernes), no la fecha del viernes
    cierres = precios.loc[cierres_semanales(precios.index)]
    ret = cierres.pct_change().iloc[-semanas:] * 100
    rel = ret.drop(columns=ref).sub(ret[ref], axis=0)
    return rel.T


# Rotación relativa (RRG) diaria. No es la fórmula oficial: la del RRG de Julius de Kempenaer no es pública.
VENTANA_SUAVE = 5  # días para suavizar la relación serie/referencia
VENTANA_FUERZA = 300  # días del promedio contra el que se mide la fuerza relativa
VENTANA_MOMENTUM = 75  # días del promedio contra el que se mide el momentum
PERSISTENCIA = 3  # días seguidos en un cuadrante nuevo antes de aceptar el cambio
# Escalas fijas de las líneas de la cinta, centradas en 100 en la mitad de cada franja: la diferencia con 100
# que llega al borde de la franja (~95% de los valores quedan dentro; lo que pasa se dibuja en el borde).
ESCALA_FUERZA = 15
ESCALA_MOMENTUM = 10
GUIAS_FUERZA = (-10, 10)  # guías punteadas, en puntos de fuerza sobre/bajo 100


def rrg(s, claves, ref):
    """Rotación relativa diaria contra la referencia.

    Fuerza relativa: la relación serie/referencia (suavizada a 5 días) contra su promedio de 300 días;
    100 = en su promedio, >100 = le viene ganando a la referencia.
    Momentum: la fuerza relativa contra su promedio de 75 días; >100 = la ventaja se está acelerando.
    """
    fuerza, momentum = {}, {}
    for k in claves:
        if k in s:
            rs = (s[k] / s[ref]).dropna().rolling(VENTANA_SUAVE).mean()
            f = 100 * rs / rs.rolling(VENTANA_FUERZA).mean()
            fuerza[k], momentum[k] = f, 100 * f / f.rolling(VENTANA_MOMENTUM).mean()
    return pd.DataFrame(fuerza), pd.DataFrame(momentum)


def _filtrar(cuadrantes, n=PERSISTENCIA):
    """Acepta un cambio de cuadrante solo después de n días seguidos en el nuevo (evita el parpadeo)."""
    salida, actual, candidato, dias = [], None, None, 0
    for q in cuadrantes:
        if q is None:
            salida.append(actual)
            continue
        if actual is None:
            actual = q
        elif q == actual:
            candidato, dias = None, 0
        else:
            dias = dias + 1 if q == candidato else 1
            candidato = q
            if dias >= n:
                actual, candidato, dias = q, None, 0
        salida.append(actual)
    return salida


def cuadrantes(fuerza, momentum, n=PERSISTENCIA):
    """DataFrame diario con el nombre del cuadrante de cada serie, ya filtrado contra el parpadeo."""
    salida = {}
    for k in fuerza.columns:
        f, m = fuerza[k], momentum[k]
        crudo = [CUADRANTES[(fi > 100, mi > 100)][0] if pd.notna(fi) and pd.notna(mi) else None
                 for fi, mi in zip(f, m)]
        salida[k] = pd.Series(_filtrar(crudo, n) if n > 1 else crudo, index=f.index)
    return pd.DataFrame(salida)


def cuadrantes_actuales(fuerza, momentum):
    """{clave: nombre del cuadrante} hoy, ya filtrado contra el parpadeo."""
    q = cuadrantes(fuerza, momentum).ffill().iloc[-1]
    return {k: v for k, v in q.items() if pd.notna(v)}


def por_confirmar(fuerza, momentum):
    """{clave: (cuadrante nuevo, días que lleva en él)} para las series cuya posición de hoy ya está en otro
    cuadrante, pero el cambio todavía no cumple los PERSISTENCIA días seguidos para confirmarse."""
    crudo = cuadrantes(fuerza, momentum, n=1).ffill()
    confirmado = cuadrantes(fuerza, momentum).ffill()
    salida = {}
    for k in crudo:
        c = crudo[k].dropna()
        if c.empty or c.iloc[-1] == confirmado[k].iloc[-1]:
            continue
        dias = int((c[::-1] == c.iloc[-1]).cumprod().sum())
        salida[k] = (c.iloc[-1], dias)
    return salida


MEJORAN = ("Mejorando", "Liderando")  # cuadrantes con momentum sobre 100: la ventaja crece


def mejora(nuevo):
    """True si el cambio va hacia un cuadrante donde la ventaja crece (▲); False si va a uno donde se achica (▼)."""
    return nuevo in MEJORAN


def texto_confirmar(nuevo, dias):
    return f"{'▲' if mejora(nuevo) else '▼'} {nuevo} por confirmar ({dias} de {PERSISTENCIA} días)"


def grafico_rrg(fuerza, momentum, cola, etiquetas, nombre_ref, cortas=None):
    """Rotación relativa: una cola por serie con un punto por semana (el último día con datos de cada una).

    El color de cada punto es el cuadrante confirmado de esa semana, igual que en la cinta. Si hoy la serie ya
    está en otro cuadrante pero el cambio no se confirma, el punto grande lleva un anillo del color nuevo.
    cortas: {clave: texto corto} para rotular el punto actual (por defecto, la clave).
    """
    cortas = cortas or {}
    colores = {nombre: color for nombre, color in CUADRANTES.values()}
    pendientes = por_confirmar(fuerza, momentum)
    fechas = cierres_semanales(fuerza.index, cola)
    f, m = fuerza.ffill().reindex(fechas), momentum.ffill().reindex(fechas)
    q = cuadrantes(fuerza, momentum).ffill().reindex(fechas)
    # Cada eje con su escala, centrada en 100: el momentum se mueve en un rango más chico que la fuerza
    rx, ry = (f - 100).abs().max().max() * 1.15, (m - 100).abs().max().max() * 1.15
    limx, limy = [100 - rx, 100 + rx], [100 - ry, 100 + ry]
    fig = go.Figure()
    for (arriba_f, arriba_m), (nombre, color) in CUADRANTES.items():
        x0, x1 = (100, limx[1]) if arriba_f else (limx[0], 100)
        y0, y1 = (100, limy[1]) if arriba_m else (limy[0], 100)
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, fillcolor=color, opacity=0.08, line_width=0)
        fig.add_annotation(x=limx[1] if arriba_f else limx[0], y=limy[1] if arriba_m else limy[0], text=nombre,
                           showarrow=False, font=dict(color=color, size=13),
                           xanchor="right" if arriba_f else "left", yanchor="top" if arriba_m else "bottom")
    for k in f.columns:
        validos = f[k].notna() & m[k].notna()
        x, y, cq = f[k][validos], m[k][validos], q[k][validos]
        if x.empty:
            continue
        puntos = [colores.get(c, "#8b949e") for c in cq]
        nuevo, dias = pendientes.get(k, (None, 0))
        borde_color = ["rgba(0,0,0,0)"] * (len(x) - 1) + [colores[nuevo] if nuevo else "#ffffff"]
        borde_ancho = [0] * (len(x) - 1) + [3 if nuevo else 1.5]
        simbolo = "circle" if not nuevo else ("triangle-up" if mejora(nuevo) else "triangle-down")
        detalle = [f"{c}" for c in cq]
        if nuevo:
            detalle[-1] += " " + texto_confirmar(nuevo, dias)
        fig.add_scatter(x=x, y=y, mode="lines", line=dict(color="rgba(200,200,200,0.55)", width=1.5),
                        hoverinfo="skip", showlegend=False)
        fig.add_scatter(x=x, y=y, mode="markers+text", name=k, showlegend=False,
                        marker=dict(size=[6] * (len(x) - 1) + [18 if nuevo else 14], color=puntos,
                                    symbol=["circle"] * (len(x) - 1) + [simbolo],
                                    line=dict(color=borde_color, width=borde_ancho)),
                        text=[""] * (len(x) - 1) + [cortas.get(k, k)], textposition="top center",
                        customdata=list(zip([d.strftime("%d-%m-%Y") for d in x.index], detalle)),
                        hovertemplate=f"<b>{etiquetas[k]}</b><br>%{{customdata[0]}}: %{{customdata[1]}}"
                                      "<br>Fuerza %{x:.2f} · Momentum %{y:.2f}<extra></extra>")
    fig.update_layout(title=f"Rotación relativa contra {nombre_ref}: últimas {cola} semanas<br><sup>Color = "
                            "cuadrante confirmado de cada semana; ▲ / ▼ = va a mejorar / empeorar, por confirmar (borde = cuadrante nuevo)</sup>",
                      height=620, margin=dict(l=10, r=10, t=70, b=10), showlegend=False,
                      xaxis=dict(range=limx, title="Fuerza relativa →", zeroline=False),
                      yaxis=dict(range=limy, title="Momentum de la fuerza →", zeroline=False))
    fig.add_hline(y=100, line=dict(color="#888", width=1))
    fig.add_vline(x=100, line=dict(color="#888", width=1))
    return fig


def grafico_grilla(s, claves, ref, periodo, fin, etiquetas, titulo, cuadrante_hoy=None):
    """Un gráfico chico por serie: serie/referencia (100 = inicio del período) y su media de 50 días.

    cuadrante_hoy: {clave: cuadrante confirmado}; si se da, cada línea toma el color de su cuadrante (igual que
    en la cinta y el gráfico de rotación). Si no, verde/rojo según si está sobre o bajo su media de 50 días."""
    colores_q = {nombre: color for nombre, color in CUADRANTES.values()}
    claves = [k for k in claves if k in s]
    filas = -(-len(claves) // 4)
    fig = make_subplots(rows=filas, cols=4, subplot_titles=[etiquetas[k] for k in claves],
                        vertical_spacing=min(0.09, 0.3 / filas), horizontal_spacing=0.05)
    for i, k in enumerate(claves):
        rs = (s[k] / s[ref]).dropna()
        sma = rs.rolling(50).mean()
        x, m = recortar(rs, periodo, fin), recortar(sma, periodo, fin)
        if x.empty:
            continue
        base = x.iloc[0]
        if cuadrante_hoy is not None:
            color = colores_q.get(cuadrante_hoy.get(k), "#8b949e")
        else:
            color = "#57ab5a" if x.iloc[-1] > m.iloc[-1] else "#e5534b"
        fila, col = i // 4 + 1, i % 4 + 1
        fig.add_scatter(x=x.index, y=x / base * 100, line=dict(color=color, width=1.5), name=k,
                        hovertemplate="%{y:.1f}<extra></extra>", row=fila, col=col)
        fig.add_scatter(x=m.index, y=m / base * 100, line=dict(color="#8b949e", width=1, dash="dot"),
                        name="SMA 50", hoverinfo="skip", row=fila, col=col)
        fig.add_hline(y=100, line=dict(color="#555", width=0.8), row=fila, col=col)
    fig.update_layout(title=titulo, height=260 * filas, margin=dict(l=10, r=10, t=70, b=10), showlegend=False)
    fig.update_annotations(font_size=12)
    fig.update_xaxes(nticks=4, tickformat="%b %y", tickangle=0)
    for vacio in range(len(claves), filas * 4):
        fig.update_xaxes(visible=False, row=vacio // 4 + 1, col=vacio % 4 + 1)
        fig.update_yaxes(visible=False, row=vacio // 4 + 1, col=vacio % 4 + 1)
    return fig


def grafico_cinta(q, fuerza, momentum, orden, etiquetas, periodo, fin, vix=None, separador=None, rotulos=None,
                  semanas=None, valores=None, nombre_ref=None, clic=False, rsi=None):
    """Cinta cronológica: una franja por serie, pintada cada día según su cuadrante, con la fuerza relativa
    (línea blanca) y el momentum (línea negra) dibujados dentro de la franja, ambos con 100 en la mitad. orden: de abajo hacia arriba. separador: (claves del bloque de
    abajo, texto abajo, texto arriba) para dividir la cinta en dos bloques. vix: serie opcional para un panel inferior.
    rotulos: {clave: texto} para el eje vertical (por defecto, la clave).
    semanas: si se indica, una columna por semana (el cuadrante al cierre de cada una) en las últimas
    `semanas` semanas; si no, un día por columna.
    valores: rendimiento semanal contra la referencia (de relativo_semanal), que se escribe sobre cada celda en
    verde o rojo; solo con `semanas`. nombre_ref: nombre de la referencia, para el detalle al pasar el mouse."""
    orden = [k for k in orden if k in q]
    nombres = [nombre for nombre, _ in CUADRANTES.values()]
    colores = [color for _, color in CUADRANTES.values()]
    if semanas:
        fechas = cierres_semanales(q.index, semanas)
        q = q[orden].ffill().reindex(fechas)
        x = rotulos_semanas(fechas)
    else:
        q = recortar(q[orden], periodo, fin)
        x = q.index
    f = fuerza[orden].ffill().reindex(q.index)
    m = momentum[orden].ffill().reindex(q.index)
    # RSI 5 promedio (opcional): al último dato disponible de cada columna de la cinta
    r = rsi.reindex(columns=orden).ffill().reindex(q.index, method="ffill") if rsi is not None else None
    filas = 2 if vix is not None else 1
    # Alturas en píxeles: la cinta crece con el número de franjas y el VIX tiene altura fija
    alto_cinta, alto_vix = max((85 if valores is not None else 60) * len(orden), 200), 160
    fig = make_subplots(rows=filas, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        row_heights=[alto_cinta, alto_vix] if filas == 2 else [1])

    # Cuadrante como número (0-3) con una escala de colores discreta
    z = q.apply(lambda col: col.map({n: i for i, n in enumerate(nombres)})).T.values
    escala = []
    for i, c in enumerate(colores):
        escala += [[i / 4, c], [(i + 1) / 4, c]]
    if valores is not None:
        valores = valores.reindex(index=orden, columns=q.index)
    texto = [[f"{etiquetas[k]}<br>{fecha:%d-%m-%Y}: {cuad or '—'}<br>Fuerza {ff:.1f} · Momentum {mm:.1f}"
              + (f" · RSI 5 prom. {r.at[fecha, k]:.0f}" if r is not None and pd.notna(r.at[fecha, k]) else "")
              + (f"<br>Semana: {valores.loc[k, fecha]:+.2f} pp vs {nombre_ref}"
                 if valores is not None and pd.notna(valores.loc[k, fecha]) else "")
              for fecha, cuad, ff, mm in zip(q.index, q[k], f[k], m[k])] for k in orden]
    fig.add_heatmap(z=z, x=x, y=list(range(len(orden))), zmin=-0.5, zmax=3.5, colorscale=escala, ygap=3,
                    opacity=0.75 if valores is not None else 1,
                    xgap=1 if semanas else 0, showscale=False, text=texto,
                    hovertemplate=None if clic else "%{text}<extra></extra>", hoverinfo="skip" if clic else None,
                    row=1, col=1)

    # Para poder hacer clic en una franja: puntos invisibles (tres por celda, para cubrir su altura) que llevan
    # la clave de su fila en customdata. El detalle al pasar el mouse se muestra desde estos puntos.
    # clic puede ser el texto que se agrega al detalle (por ejemplo, adónde lleva el clic).
    if clic:
        px_, py_, cd_, tx_ = [], [], [], []
        for i, k in enumerate(orden):
            for j, col in enumerate(x):
                for dy in (-0.28, 0, 0.28):
                    px_.append(col)
                    py_.append(i + dy)
                    cd_.append(k)
                    tx_.append(texto[i][j] + f"<br><i>{clic if isinstance(clic, str) else 'Clic para ver más'}</i>")
        fig.add_scatter(x=px_, y=py_, mode="markers", customdata=cd_, text=tx_, showlegend=False, name="clic",
                        marker=dict(size=16, symbol="square", color="rgba(0,0,0,0)"),
                        selected=dict(marker=dict(opacity=0)), unselected=dict(marker=dict(opacity=0)),
                        hovertemplate="%{text}<extra></extra>", row=1, col=1)

    # Fuerza y momentum dentro de cada franja: 100 en la mitad, ±escala en los bordes (igual para todas)
    def altura(i, serie, escala):
        return i + (serie - 100).clip(-escala, escala) / escala * 0.42

    # Guías tenues (una sola traza por nivel; None corta la línea entre franjas): la mitad = 100 y ±10 de fuerza
    for nivel, estilo, opacidad in ((0, "solid", 0.4), *((g, "dot", 0.22) for g in GUIAS_FUERZA)):
        gx, gy = [], []
        for i in range(len(orden)):
            gx += [x[0], x[-1], None]
            gy += [i + nivel / ESCALA_FUERZA * 0.42] * 2 + [None]
        fig.add_scatter(x=gx, y=gy, mode="lines", hoverinfo="skip", showlegend=False, row=1, col=1,
                        line=dict(color=f"rgba(255,255,255,{opacidad})", width=1, dash=estilo))
    for i, k in enumerate(orden):
        fig.add_scatter(x=x, y=altura(i, m[k], ESCALA_MOMENTUM), mode="lines", hoverinfo="skip", showlegend=False,
                        line=dict(color="rgba(0,0,0,0.9)", width=1.8), row=1, col=1)
        if r is not None:
            # RSI con 30 y 70 sobre las guías punteadas de la fuerza y 50 en la mitad; los bordes quedan en 20 y 80
            guia = GUIAS_FUERZA[1] / ESCALA_FUERZA * 0.42
            fig.add_scatter(x=x, y=i + ((r[k] - 50) / 20 * guia).clip(-0.42, 0.42), mode="lines", hoverinfo="skip",
                            showlegend=False, line=dict(color="#fde047", width=1.6), row=1, col=1)
        fig.add_scatter(x=x, y=altura(i, f[k], ESCALA_FUERZA), mode="lines", hoverinfo="skip", showlegend=False,
                        line=dict(color="rgba(255,255,255,0.95)", width=1.8), row=1, col=1)
    # Cambio de cuadrante por confirmar hoy: triángulo del color nuevo arriba de la última columna,
    # hacia arriba si va a mejorar y hacia abajo si va a empeorar
    pendientes = por_confirmar(fuerza[orden], momentum[orden])
    if pendientes:
        filas_p = [i for i, k in enumerate(orden) if k in pendientes]
        fig.add_scatter(x=[x[-1]] * len(filas_p), y=[i + 0.3 for i in filas_p], mode="markers", showlegend=False,
                        marker=dict(symbol=["triangle-up" if mejora(pendientes[orden[i]][0]) else "triangle-down"
                                            for i in filas_p], size=14,
                                    color=[colores[nombres.index(pendientes[orden[i]][0])] for i in filas_p],
                                    line=dict(color="#ffffff", width=1.5)),
                        text=[f"{etiquetas[orden[i]]}: {q[orden[i]].iloc[-1]} {texto_confirmar(*pendientes[orden[i]])}"
                              for i in filas_p],
                        hovertemplate="%{text}<extra></extra>", row=1, col=1)
    for nombre, color in zip(nombres, colores):
        fig.add_scatter(x=[None], y=[None], mode="markers", marker=dict(color=color, size=11, symbol="square"),
                        name=nombre, row=1, col=1)
    if r is not None:
        fig.add_scatter(x=[None], y=[None], mode="lines", name="RSI 5 promedio", row=1, col=1,
                        line=dict(color="#fde047", width=2))
    if pendientes:
        for simbolo, texto_leyenda in (("triangle-up", "Va a mejorar (por confirmar)"),
                                       ("triangle-down", "Va a empeorar (por confirmar)")):
            fig.add_scatter(x=[None], y=[None], mode="markers", name=texto_leyenda, row=1, col=1,
                            marker=dict(symbol=simbolo, size=11, color="#8b949e", line=dict(color="#ffffff", width=1.5)))

    # Rendimiento semanal escrito sobre cada celda: verde si le ganó a la referencia, rojo si perdió.
    # Con muchas semanas las columnas son angostas y el número va en vertical. Sin caja de fondo, para no
    # tapar las líneas: la sombra oscura alrededor de cada número le da contraste sobre la celda.
    # Se agregan todas juntas al final: agregarlas una por una con add_annotation tarda decenas de segundos.
    numeros = []
    if valores is not None and semanas:
        vertical = len(x) > 20
        for i, k in enumerate(orden):
            for col, v in zip(x, valores.loc[k]):
                if pd.notna(v):
                    numeros.append(dict(x=col, y=i, xref="x", yref="y", text=f"<b>{v:+.1f}</b>", showarrow=False,
                                        textangle=-90 if vertical else 0,
                                        font=dict(color="#56d364" if v >= 0 else "#ff7b72",
                                                  size=10 if vertical else 12,
                                                  shadow="0 0 2px #000, 0 0 3px #000, 0 0 4px #000")))

    if separador:
        claves_abajo, abajo, arriba = separador
        i = sum(k in claves_abajo for k in orden)  # la línea va donde termina el bloque de abajo
        fig.add_hline(y=i - 0.5, line=dict(color="#58a6ff", width=2, dash="dash"), row=1, col=1)
        for texto_bloque, y, ancla in ((arriba, i - 0.5, "bottom"), (abajo, i - 0.5, "top")):
            fig.add_annotation(x=0.005, xref="x domain", y=y, yref="y", text=texto_bloque, showarrow=False,
                               xanchor="left", yanchor=ancla, font=dict(color="#58a6ff", size=11),
                               bgcolor="rgba(13,17,23,0.6)")
    rotulos = rotulos or {}
    fig.update_yaxes(tickvals=list(range(len(orden))), ticktext=[rotulos.get(k, k) for k in orden],
                     range=[-0.5, len(orden) - 0.5],
                     showgrid=False, row=1, col=1)

    if vix is not None:
        if semanas:
            v = pd.Series([vix.asof(f) for f in fechas], index=fechas)
            xv = x
        else:
            v = recortar(vix, periodo, fin)
            xv = v.index
        fig.add_scatter(x=xv, y=v, name="VIX", line=dict(color="#f472b6", width=1.3), row=2, col=1,
                        hovertemplate="VIX %{y:.2f}<extra></extra>")
        for nivel, color in ((20, "#e0823d"), (30, "#e5534b")):
            fig.add_hline(y=nivel, line=dict(color=color, width=1, dash="dash"), row=2, col=1)
        fig.update_yaxes(title_text="VIX", row=2, col=1)

    if semanas:
        fig.update_xaxes(type="category", tickangle=-90 if len(x) > 20 else 0, tickfont=dict(size=10))
    titulo = ("Cinta de rotación: cuadrante al cierre de cada semana" if semanas
              else "Cinta de rotación: cuadrante de cada día") + ", fuerza relativa (línea blanca) y momentum (línea negra)"
    titulo += (f"<br><sup>Mitad de cada franja = 100 en ambas líneas; arriba de la mitad, le gana a {nombre_ref or 'la referencia'}"
               " (fuerza) o la ventaja se acelera (momentum)"
               + (f". Números: rendimiento de cada semana contra {nombre_ref}, en puntos porcentuales" if valores is not None and semanas else "")
               + ("<br>Línea amarilla: RSI 5 promedio de sus empresas (punteadas = 30 y 70, mitad = 50, bordes = 20 y 80)"
                  if r is not None else "")
               + "</sup>")
    fig.update_layout(title=titulo,
                      height=alto_cinta + (alto_vix if filas == 2 else 0) + 220, margin=dict(l=10, r=10, t=95, b=70),
                      # Leyenda debajo del gráfico: arriba choca con el subtítulo cuando ocupa dos filas
                      legend=dict(orientation="h", yanchor="top", y=-0.04, x=0, xanchor="left"),
                      hovermode="closest")
    if numeros:
        fig.update_layout(annotations=[*fig.layout.annotations, *numeros])
    return fig
