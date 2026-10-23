# Fdash

Dashboard de inversión en tres partes: **Top** (Sectores → Industrias), **Down** (Empresas) y **Macro** (Tendencias y Economía).
Publicado en https://freddydash.streamlit.app.

## Datos

La app no baja nada al abrirse (salvo las velas de la ventana de una empresa): lee los archivos de `datos/`,
que actualizan los GitHub Actions de `.github/workflows` con los scripts de `scripts/`.

| Workflow | Qué actualiza | Script |
|---|---|---|
| `actualizar-precios.yml` | `datos/precios/reciente.csv` (3 meses) y `datos/fred.csv` | `actualizar_fred.py`, `actualizar_precios.py reciente` |
| `actualizar-historia.yml` | `datos/precios/historia.parquet` (~7 años) | `actualizar_precios.py historia` |
| `actualizar-opciones.yml` | `datos/put_call.csv` (~35 minutos) | `actualizar_opciones.py --si-falta` |

El universo de empresas (`datos/universo.csv`) se rehace a mano con `scripts/actualizar_universo.py`, a partir
de los CSV del screener de NASDAQ en `../Screener`.

## Lanzar los Actions a la hora (cron-job.org)

GitHub atrasa sus tareas programadas (horas, a veces) o se las salta. Por eso los workflows se lanzan desde
[cron-job.org](https://console.cron-job.org) con la API de GitHub; el `schedule` de cada workflow queda de
respaldo. Si una corrida llega repetida, no pasa nada: los precios solo hacen commit si cambiaron, y el
Put/Call no hace nada si ya se bajó ese día.

**Token.** En GitHub → Settings → Developer settings → Fine-grained tokens → Generate new token:
- Repository access: *Only select repositories* → `freddync/freddydash`
- Permissions → Repository → **Actions: Read and write**
- Al vencer, crear otro y reemplazarlo en los trabajos de cron-job.org.

**Trabajos.** Se clonaron de los del dashboard anterior (mismo token). En todos, zona horaria **America/New_York** (así el cambio de horario se ajusta solo):

| Trabajo | Horario (NY) | URL |
|---|---|---|
| Fdash precios 9:31 | lun-vie, 9:31 | `.../workflows/actualizar-precios.yml/dispatches` |
| Fdash precios horario | lun-vie, 10:00 a 16:00 cada hora | `.../workflows/actualizar-precios.yml/dispatches` |
| Fdash precios 16:30 (respaldo cierre) | lun-vie, 16:30 | `.../workflows/actualizar-precios.yml/dispatches` |
| Fdash opciones 8:40 | lun-vie, 8:40 | `.../workflows/actualizar-opciones.yml/dispatches` |
| Fdash historia (día 1) | día 1 de cada mes, 2:00 | `.../workflows/actualizar-historia.yml/dispatches` |

donde `...` es `https://api.github.com/repos/freddync/freddydash/actions`. En la pestaña *Advanced* de cada trabajo:

- Request method: **POST**
- Headers:
  - `Accept: application/vnd.github+json`
  - `Authorization: Bearer <token>`
  - `X-GitHub-Api-Version: 2022-11-28`
- Request body: `{"ref":"main"}`

GitHub responde **204** cuando acepta el pedido; la corrida aparece en la pestaña Actions del repo.
