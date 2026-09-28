"""Genera el notebook de EDA; las cifras se calculan en sus celdas ejecutables."""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
cells = []
def md(s):
    cells.append(nbf.v4.new_markdown_cell(s.strip()))
def code(s):
    cells.append(nbf.v4.new_code_cell(s.strip()))

md("""
# EDA enfocado: ¿dónde están los problemas de atención?
**Factored AI & Data Hackathon 2026 · Datos sintéticos de LATAM Bank**

Este notebook mide fricciones que sirven para elegir un flujo del hackathon.
Se limita a **interacciones y casos**, más **dos particiones diarias por mes** de
transacciones y eventos digitales. La ampliación examina descripciones de casos
y una muestra de transcripciones de esos mismos días. Las otras ocho tablas no se examinan.
Los resultados son históricos y sintéticos: no describen un banco real ni prometen
que todos los casos puedan automatizarse.
""")
md("""
## Context & Methods

**Decisión:** qué problema tiene suficiente volumen, dificultad de resolución y
evidencia disponible para justificar un flujo bancario enfocado.

| Fuente | Unidad | Alcance |
|---|---|---|
| `call_center_interactions` | Una interacción identificada por `interaction_id` | Todas las particiones; 14 columnas |
| `complaints` | Un caso, que puede ser queja, reclamo, solicitud o sugerencia | Todas las particiones; 19 columnas |
| `transactions` | Una transacción identificada por `transaction_id` | 2 días de partición por mes; 12 columnas |
| `digital_events` | Un evento identificado por `event_id` | Los mismos 2 días por mes; 12 columnas |
| `call_transcripts` (ampliación) | Una transcripción identificada por `transcript_id` | Los mismos días; 10 columnas, incluidos textos del cliente y agente |

La ampliación relee también ID, descripción y resolución de los casos. La lectura
principal conserva 19 campos de casos y estos dos textos adicionales se examinan
por separado, sin publicar filas ni identificadores.

**Muestreo:** días elegidos aleatoriamente sin reemplazo dentro de cada mes, semilla
`20260925`, sobre las fechas comunes de las dos tablas grandes. Es una muestra por
conglomerados (días de proceso), no de filas independientes. Los porcentajes de las
muestras se presentan sin extrapolarlos al universo ni atribuirles precisión de
una muestra aleatoria simple. Junio de 2023 y junio de 2026 son meses parciales.

**Motor:** DuckDB en CPU, 4 hilos, límite de memoria de DuckDB de 1.500 MB y caché
en disco. Sólo los agregados pasan a pandas. Un CSV requiere recorrer sus bytes
aunque conservemos pocas columnas; el muestreo reduce los archivos leídos.
La inspección inicial de esta laptop encontró una RTX 3050 Ti de 4 GB con 201 MiB
libres. Por ello se eligió CPU; **no se hizo una comparación de velocidad GPU/CPU**.

**Fuentes locales:** `dataset/_descarga/inventario-s3.json`, los CSV seleccionados,
el resumen y diccionario del organizador y `ANALISIS-REQUISITOS-HACKATHON.md`.
No se leen credenciales del PDF ni se consulta un servicio externo.
""")
code("""
from pathlib import Path
import sys, json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter
from IPython.display import display, Markdown

# Funciona ejecutando desde la raíz del proyecto o desde notebooks/.
ROOT = next((p for p in (Path.cwd(), *Path.cwd().parents)
             if (p / 'scripts' / 'eda_problemas.py').exists()), None)
assert ROOT is not None, 'Ejecuta este notebook dentro del proyecto descargado.'
sys.path.insert(0, str(ROOT / 'scripts'))
from eda_problemas import run
from validar_eda import validate
from eda_detalle import run_detail

OUT = ROOT / 'notebooks' / 'resultados'
FIG = ROOT / 'notebooks' / 'figuras'
FIG.mkdir(exist_ok=True)
REBUILD = False  # True relee sólo las cuatro selecciones, nunca las 13 tablas.
pd.set_option('display.max_columns', 12)
pd.set_option('display.max_rows', 15)
pd.set_option('display.float_format', lambda x: f'{x:,.2f}')
plt.rcParams.update({'figure.dpi': 120, 'savefig.dpi': 150,
                     'font.size': 10, 'axes.titlesize': 12,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.labelcolor': '#334155', 'text.color': '#172033',
                     'axes.titleweight': 'bold', 'figure.facecolor': 'white',
                     'axes.facecolor': 'white', 'font.family': 'DejaVu Sans'})
BLUE, ORANGE, MUTED, GOLD = '#2864A5', '#C65D24', '#7A8CA2', '#BA8B2F'
def get(name):
    return pd.read_csv(OUT / f'{name}.csv')
def count(x):
    return f'{int(x):,}'.replace(',', '.')
def pct(x):
    return f'{x:.2f}'.replace('.', ',') + ' %'
def showfig(fig, name):
    fig.savefig(FIG / f'{name}.png', bbox_inches='tight')
    plt.show()
    plt.close(fig)
""")
md("""
## Data

La primera ejecución prepara únicamente las selecciones descritas. Las siguientes
reutilizan una base local en `dataset/_eda_problemas/`. Se invalidan los datos
preparados si cambian rutas, tamaños, fechas de modificación o configuración.
La huella es de esos metadatos, **no una verificación criptográfica del contenido**.
Las consultas agregadas se recalculan siempre; están en `sql/eda/` para auditarlas.
""")
code("""
display(coverage[['table', 'scope', 'files', 'source_MB', 'raw_rows', 'analysis_rows',
                  'min_event_date', 'max_event_date']])
display(Markdown(
    f"Se examinaron **{execution['selected_source_bytes']/1e6:.1f} MB** de archivos "
    f"(**{execution['selected_source_bytes']/execution['inventory_source_bytes']*100:.2f} %** "
    f"de los bytes del inventario), con {len(execution['sampled_days'])} días de muestra "
    f"en {execution['sample_months']} meses. No se cargó el dataset completo. "
    f"La ampliación añade {detail_execution['new_unique_source_bytes']/1e6:.2f} MB de transcripciones; "
    f"la selección conjunta cubre {(execution['selected_source_bytes']+detail_execution['new_unique_source_bytes'])/1e6:.2f} MB "
    f"({(execution['selected_source_bytes']+detail_execution['new_unique_source_bytes'])/execution['inventory_source_bytes']*100:.2f} % del inventario)."))
""")
md("""
**Preparación:** se conservan los vacíos como nulos; las conversiones de fechas,
números y booleanos son explícitas y se cuentan los errores de conversión.
Se eliminan filas repetidas en **las columnas seleccionadas**. Si un ID tiene
versiones diferentes en esos campos, se excluyen todas sus versiones de las
métricas en lugar de escoger una arbitrariamente. También se excluyen IDs nulos.
Esto no certifica igualdad de todas las columnas originales ni el resto de tablas.

Los volúmenes aproximados de 800.000 interacciones y 80.000 casos en el PDF no
sustituyen los recuentos observados. Las 1.097 particiones de cada tabla están
presentes: la diferencia respecto al PDF, por sí sola, no demuestra una descarga
incompleta.
""")
code("""
display(coverage[['table', 'raw_rows', 'projected_duplicate_rows', 'null_key_rows',
                  'conflicting_keys', 'analysis_rows']])
invalid = get('invalid_types')
display(Markdown(f"**Conversiones inválidas en campos seleccionados:** {count(invalid.invalid_rows.sum())}. "
                 f"**Variantes de cabecera por tabla seleccionada:** "
                 + ', '.join(f"{r.table}: {r.schema_variants}" for r in get('schemas').itertuples()) + '.'))
load = pd.DataFrame(execution['load_metrics'])
display(load[['table', 'seconds_scan_clean', 'raw_rows', 'columns_retained']])
display(pd.DataFrame([{
    'Reutilizó caché': execution['cache_reused'],
    'Segundos del recálculo base': execution['wall_seconds'],
    'CPU-segundos base': execution['process_cpu_seconds'],
    'Pico RSS base (MiB)': execution['peak_process_rss_MiB_observed'],
    'Memoria DuckDB (MB)': 1500, 'Hilos': 4
}]))
display(Markdown('La tabla de lectura conserva los tiempos de preparación inicial. '
    'El tiempo y RSS de esta ejecución corresponden al recálculo cuando se reutiliza la caché; '
    'no son una medición del pico de toda la lectura inicial. RSS se muestrea cada 0,1 s '
    'y puede omitir picos breves. El límite de DuckDB no es un límite estricto de todo Python.'))
""")
md("""
## tl;dr

Las prioridades siguientes usan **volumen observado y tasas con denominador**,
sin crear una puntuación arbitraria que mezcle interacciones, casos y eventos.
""")
code("""
reason = get('calls_by_reason')
q = reason.loc[reason.reason == 'Queja'].iloc[0]
t = reason.loc[reason.reason == 'Técnico'].iloc[0]
tx_status = get('transactions_status')
declined = tx_status.loc[tx_status.status == 'Declined'].iloc[0]
digital = get('digital_channels')
sessions = get('digital_session_identity').iloc[0]
display(Markdown(f'''| Señal medida | Resultado | Qué sugiere |
|---|---:|---|
| Quejas sin resolver en el primer contacto | **{count(q.unresolved)} / {count(q.resolution_known)} ({pct(q.unresolved_pct)})** | Mayor volumen de contactos sin resolución |
| Motivos técnicos sin resolver | **{count(t.unresolved)} / {count(t.resolution_known)} ({pct(t.unresolved_pct)})** | Segundo grupo por contactos sin resolver |
| Casos con etiqueta de SLA incumplido | **{count(cases.sla_breached)} / {count(cases.sla_known)} ({pct(cases.sla_breached_pct)})** | Seguimiento y tiempos requieren atención |
| Casos sin ID de interacción de origen | **{count(links.cases-links.declared_links)} / {count(links.cases)}** | Bloquea el enlace directo reclamo–conversación |
| Transacciones rechazadas, muestra | **{count(declined.transactions)} / {count(tx_status.transactions.sum())} ({pct(declined.pct_sample)})** | Fricción operativa a investigar |
| Sesiones con al menos un Error, muestra | **{count(sessions.error_sessions)} / {count(sessions.sessions)} ({pct(sessions.error_session_pct)})** | Fricción digital observada, no causa probada de quejas |

Quejas y motivos técnicos reúnen **{pct((q.unresolved+t.unresolved)/calls.unresolved*100)}**
de las interacciones no resueltas. Esa concentración permite enfocar la exploración;
no demuestra qué parte resolvería una IA ni cuánto dinero se ahorraría.'''))
text_detail=get('detalle_transcript_quality').iloc[0]
case_detail=get('detalle_case_text_quality').iloc[0]
display(Markdown(f"**Hallazgo de la ampliación:** los casos sólo tienen "
    f"{count(case_detail.distinct_descriptions)} descripciones genéricas distintas. "
    f"Las {count(text_detail.transcripts)} transcripciones muestreadas hablan de saldo, "
    'incluidas las etiquetadas Queja/Técnico. El volumen de las etiquetas puede medirse, '
    'pero el texto revisado no explica sus causas. Ver secciones 7–10.'))
""")
md("""
## Results

### 1. Los campos que limitan una solución fiable

Los vacíos se revisan por contexto. Espera no registrada en email no equivale a
una llamada sin medición; una fecha de resolución vacía en un caso abierto es
esperable. Los cuatro denominadores del gráfico son distintos y se indican en
cada etiqueta. No deben sumarse.
""")
code("""
missing = get('missingness_context')
phone = missing[(missing.field=='wait_time_seconds') & (missing.segment=='Phone')].iloc[0]
rules = get('quality_rules').set_index('rule')
closed = rules.loc['resolved_closed_without_resolution_date']
evt_customer = get('missingness').query("table == 'digital_events' and column == 'customer_id'").iloc[0]
quality = pd.DataFrame([
    ['ID de interacción ausente en casos', links.cases-links.declared_links, links.cases, 'Completo'],
    ['Espera ausente en canal Phone', phone.missing, phone.rows, 'Completo'],
    ['Fecha de resolución ausente en Resolved/Closed', closed.affected, closed.eligible, 'Completo'],
    ['Cliente ausente en eventos digitales', evt_customer.null_rows, evt_customer.rows, 'Muestra'],
], columns=['Problema / limitación', 'Afectados', 'Denominador', 'Alcance'])
quality['Porcentaje'] = quality.Afectados/quality.Denominador*100
display(quality)
fig, ax = plt.subplots(figsize=(11, 4.6), layout='constrained')
labels = [f"{r[0]}\\n{r[3]} · n={count(r[2])}" for r in quality.itertuples(index=False, name=None)]
bars = ax.barh(labels, quality.Porcentaje, color=[ORANGE,BLUE,BLUE,MUTED], height=.6)
ax.invert_yaxis(); ax.set_xlim(0,118)
ax.set_xticks([0,25,50,75,100]); ax.xaxis.set_major_formatter(PercentFormatter(100))
ax.set_xlabel('Porcentaje del denominador indicado')
ax.set_title('El enlace entre casos e interacciones falta por completo', loc='left', pad=15)
ax.bar_label(bars, labels=[pct(v) for v in quality.Porcentaje], padding=6)
ax.grid(axis='x', alpha=.13); ax.set_axisbelow(True)
showfig(fig, '01_calidad')
""")
md("""
**Interpretación:** `origin_interaction_id` vacío impide validar un recorrido
conversación → reclamo usando esa llave. Compartir `customer_id` permitiría
buscar contexto del cliente, pero **no prueba que dos registros pertenezcan al
mismo caso**. Los eventos sin cliente pueden representar actividad anónima;
son una limitación para atribuirlos a una persona, no errores demostrados.

`contact_reason` y `reason_category` tienen el mismo valor en todas las
interacciones observadas: no aportan dos señales independientes ni identifican
la causa concreta de una queja. La muestra textual de la ampliación se revisa en la sección 10.
""")
code("""
display(get('complaint_call_links').T.rename(columns={0:'Conteo'}))
display(get('process_date_lags')[['scope','comparable','process_before_event_day',
                                'process_after_event_day','min_lag_days','max_lag_days']])
display(get('quality_rules').query("rule in ['resolved_closed_without_resolution_date', 'outcome_after_process_day', 'resolution_days_disagree_elapsed']"))
""")
md("""
**Tiempo y fuga de información:** parte de los eventos ocurre al día siguiente de
`process_date`. Como éste sólo tiene fecha y no documentamos aquí la zona horaria
ni el corte del lote, **no se interpreta automáticamente como un error o una
llegada tardía negativa**. Ninguna selección muestra un día de proceso posterior
al día del evento. Hace falta aclarar la semántica antes de evaluar latencia de
ingesta.

Todas las resoluciones con fecha aparecen después de `process_date`. Puede ser
un histórico enriquecido con resultados posteriores; no prueba por sí solo una
fila imposible. Sí significa que no podemos tratar `resolution_date`,
`resolution_days`, el estado final o `sla_breached` como información conocida al
abrir el caso. Un modelo necesitaría cortes temporales de disponibilidad o un
escenario controlado para evitar fuga del resultado.
""")
md("""
### 2. Atención: qué motivos concentran la falta de resolución

**Definición:** no resuelto = `was_resolved=False`. El diccionario describe
resolución en el primer contacto. La tasa usa sólo valores booleanos conocidos;
los nulos no se convierten en `False`. La resolución de una interacción tampoco
demuestra que el problema financiero del cliente quedó solucionado.
""")
code("""
display(reason[['reason','interactions','unresolved','unresolved_pct','followup','escalated']])
fig, axs = plt.subplots(1,2,figsize=(12,4.5), layout='constrained', sharey=True)
pos = np.arange(len(reason))
b = axs[0].barh(pos, reason.unresolved, color=[ORANGE]+[BLUE]*(len(reason)-1), height=.65)
axs[0].set_yticks(pos, reason.reason); axs[0].invert_yaxis()
axs[0].set_xlim(0, reason.unresolved.max()*1.24)
axs[0].bar_label(b, labels=[count(v) for v in reason.unresolved], padding=5)
axs[0].xaxis.set_major_formatter(FuncFormatter(lambda x,_: f'{x/1000:.0f} mil'))
axs[0].set_xlabel('Interacciones sin resolución en el primer contacto')
axs[0].set_title('Volumen sin resolución inicial', loc='left')
b = axs[1].barh(pos, reason.unresolved_pct, color=[ORANGE]+[BLUE]*(len(reason)-1), height=.65)
axs[1].set_xlim(0,70); axs[1].bar_label(b, labels=[pct(v) for v in reason.unresolved_pct], padding=5)
axs[1].xaxis.set_major_formatter(PercentFormatter(100))
axs[1].set_xlabel('No resueltas / interacciones del mismo motivo')
axs[1].set_title('Dificultad observada por motivo', loc='left')
for ax in axs: ax.grid(axis='x',alpha=.13); ax.set_axisbelow(True)
fig.suptitle('Quejas: mayor cantidad y mayor tasa de falta de resolución', fontsize=14, fontweight='bold')
showfig(fig,'02_atencion')
""")
code("""
channels = get('calls_by_channel')
phone_metrics = channels.loc[channels.channel=='Phone'].iloc[0]
repeat = get('repeat_contact').iloc[0]
display(channels[['channel','interactions','unresolved_pct','wait_known','wait_p50_s','wait_p95_s']])
display(Markdown(f'''En Phone, la espera registrada tiene mediana **{phone_metrics.wait_p50_s:.0f} s**
y percentil 95 **{phone_metrics.wait_p95_s:.0f} s** sobre **{count(phone_metrics.wait_known)}** llamadas
con espera conocida. Falta esa medición en **{pct(phone.missing_pct)}** de las llamadas:
no podemos suponer que las restantes esperaron lo mismo ni comparar la espera con email.

**Contactos repetidos:** {count(repeat.repeated_within_7d)} / {count(repeat.eligible_interactions)}
({pct(repeat.repeat_pct)}) tiene un contacto previo del mismo cliente y motivo en siete días.
Se excluyen los primeros siete días para evitar un historial incompleto por el inicio del archivo.
Es coincidencia de cliente/motivo, no prueba del mismo caso. Tampoco equivale al indicador
`is_repeat_complainer`, cuya definición documental usa 90 días.'''))
""")
md("""
### 3. Casos: SLA, estado y tiempos documentados

Se informa la etiqueta `sla_breached` del dataset. **No se recalcula cumplimiento
contractual:** no tenemos aquí una tabla de reglas ni fechas límite por caso.
`Open`, `In Process` y `Escalated` son estados activos registrados; no constituyen
un backlog real actualizado a septiembre de 2026, ni todos son casos vencidos.
""")
code("""
status = get('complaints_by_status')
cat = get('complaints_by_category')
display(get('complaints_by_type'))
display(cat[['category','cases','sla_breached','sla_breached_pct','active_status']])
display(Markdown(f'''Hay **{count(cases.active_status)} / {count(cases.cases)}** casos con estado activo
({pct(cases.active_status/cases.cases*100)}). La primera respuesta registrada tiene mediana de
**{cases.first_response_p50_hours:.0f} horas** y p95 de **{cases.first_response_p95_hours:.0f} horas**,
sólo sobre **{count(cases.first_response_known)}** casos con fecha de respuesta.
Entre Resolved/Closed con `resolution_days` conocido ({count(cases.resolution_days_known_closed)}),
la mediana es **{cases.resolution_days_p50_closed:.0f} días** y el p95 **{cases.resolution_days_p95_closed:.0f} días**.
Es una distribución condicionada a tener resolución y duración registradas; excluye pendientes.'''))
fig, axs = plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
bars=axs[0].barh(status.status,status.cases,color=[ORANGE if s in ['Open','In Process','Escalated'] else MUTED for s in status.status])
axs[0].invert_yaxis(); axs[0].set_xlim(0,status.cases.max()*1.27)
axs[0].bar_label(bars,labels=[count(v) for v in status.cases],padding=4)
axs[0].set_xlabel('Casos con cada estado registrado'); axs[0].set_title('Predominan estados activos',loc='left')
axs[0].xaxis.set_major_formatter(FuncFormatter(lambda x,_: f'{x/1000:.0f} mil'))
bars=axs[1].barh(cat.category,cat.sla_breached_pct,color=BLUE)
axs[1].invert_yaxis(); axs[1].set_xlim(0,27)
axs[1].bar_label(bars,labels=[pct(v) for v in cat.sla_breached_pct],padding=4)
axs[1].xaxis.set_major_formatter(PercentFormatter(100))
axs[1].set_xlabel('SLA marcado incumplido / casos de la categoría')
axs[1].set_title('Tasas de SLA similares entre categorías',loc='left')
for ax in axs: ax.grid(axis='x',alpha=.13); ax.set_axisbelow(True)
showfig(fig,'03_casos')
""")
md("""
La tabla `complaints` mezcla tipos de casos. El siguiente corte se limita a
**Complaint y Claim** para comprobar que el resultado no dependa sólo de incluir
solicitudes y sugerencias. Las categorías tienen tasas cercanas: una diferencia
pequeña en el ranking no justifica afirmar que una sucursal o producto cause más
incumplimientos. El dataset es sintético y puede reflejar decisiones del generador.
""")
code("""
display(get('complaints_claims_only'))
""")
md("""
### 4. Canales digitales: errores observados en la muestra

**Evento de error** = `event_type='Error'`. La tasa usa todos los eventos con tipo
conocido del grupo; no es una tasa de fallos por intento de pago. Una sesión con
al menos un error cuenta una vez. Sesiones sin ID se excluirían de ese cálculo;
se comprueba también que un ID de sesión no agrupe varios clientes identificados.
La muestra por días puede cortar sesiones y no representa todo el histórico.
""")
code("""
digital_cat = get('digital_categories')
display(digital)
display(get('digital_session_identity'))
display(get('digital_sessions'))
fig, axs=plt.subplots(1,2,figsize=(12,4.2),layout='constrained')
for ax,d,key,lim,title in [
    (axs[0],digital,'channel',3.1,'Tasa de error parecida por canal'),
    (axs[1],digital_cat,'event_category',8,'Errores etiquetados en dos categorías')]:
    bars=ax.barh(d[key],d.error_pct,color=BLUE)
    ax.invert_yaxis(); ax.set_xlim(0,lim)
    ax.bar_label(bars,labels=[pct(v) for v in d.error_pct],padding=4)
    ax.xaxis.set_major_formatter(PercentFormatter(100))
    ax.set_xlabel('Eventos Error / eventos del grupo · muestra')
    ax.set_title(title,loc='left'); ax.grid(axis='x',alpha=.13); ax.set_axisbelow(True)
showfig(fig,'04_digital')
""")
code("""
display(get('digital_error_actions'))
display(Markdown(f'''En la muestra, **{count(sessions.anonymous_sessions)}** sesiones no contienen un
cliente identificado y **{count(sessions.multiple_customer_sessions)}** agrupan varios clientes identificados.
Los errores aparecen en acciones de transferencias, pagos y consulta. Sin identificador de
transacción/caso y sin códigos técnicos de error analizados, no podemos afirmar que un error
digital causó un rechazo o un reclamo. Cero eventos Error en Authentication/Product tampoco
prueba que esos flujos estén libres de fallos: puede depender de cómo se etiquetó el evento.'''))
""")
md("""
### 5. Transacciones: rechazos, pendientes y reversos

Los estados son etiquetas observadas, no diagnósticos causales. Un reverso puede
ser una corrección válida y un pendiente puede ser transitorio; ninguno se suma
automáticamente a fraude o a pérdidas. Los importes USD están incompletos y no
se monetiza el problema ni se mezclan monedas.
""")
code("""
display(tx_status)
tx_problem = tx_status[tx_status.status!='Approved'].copy()
fig,ax=plt.subplots(figsize=(9,3.6),layout='constrained')
bars=ax.barh(tx_problem.status,tx_problem.pct_sample,color=[ORANGE,BLUE,MUTED])
ax.invert_yaxis(); ax.set_xlim(0,6.9)
ax.bar_label(bars, labels=[f'{pct(r.pct_sample)} · {count(r.transactions)}' for r in tx_problem.itertuples()],padding=5)
ax.xaxis.set_major_formatter(PercentFormatter(100)); ax.set_xlabel('Porcentaje de transacciones en la muestra')
ax.set_title(f'{count(tx_status.transactions.sum())} transacciones en {len(execution["sampled_days"])} particiones',loc='left')
ax.grid(axis='x',alpha=.13); ax.set_axisbelow(True)
showfig(fig,'05_transacciones')
display(get('transactions_channel')[['channel','transactions','declined','declined_pct','reversed','pending']])
""")
md("""
### 6. Evolución temporal en las dos tablas completas

Se comparan tasas mensuales con su propio denominador, no totales de meses de
distinta duración. El primer y último mes son parciales. Estas series no prueban
causalidad ni un efecto de una intervención.
""")
code("""
cm=get('calls_monthly'); sm=get('complaints_monthly')
fig,ax=plt.subplots(figsize=(11,3.8),layout='constrained')
x=np.arange(len(cm)); ax.plot(x,cm.unresolved_pct,color=ORANGE,label='Interacciones no resueltas / interacciones del mes',lw=2)
ax.plot(x,sm.sla_breached_pct,color=BLUE,label='SLA incumplido / casos del mes',lw=2)
ticks=list(range(0,len(cm),6))
if len(cm)-1 not in ticks: ticks.append(len(cm)-1)
ax.set_xticks(ticks,cm.month.iloc[ticks],rotation=20)
ax.set_ylim(0,max(cm.unresolved_pct.max(),sm.sla_breached_pct.max())*1.35)
ax.yaxis.set_major_formatter(PercentFormatter(100))
ax.axvspan(-.5,.5,color=MUTED,alpha=.12); ax.axvspan(len(cm)-1.5,len(cm)-.5,color=MUTED,alpha=.12)
ax.set_title('Lectura histórica; sombreado = mes parcial',loc='left')
ax.legend(loc='lower left',frameon=False,fontsize=9); ax.grid(axis='y',alpha=.16)
ax.set_xlabel('Mes del evento, sin ajuste de zona horaria')
showfig(fig,'06_evolucion')
""")
md("""
### Comprobaciones de los resultados

Se concilian totales y desgloses; se recalculan porcentajes; se comprueba que el
JOIN no multiplique casos y se contrastan dos CSV de extremos por tabla de
atención con el lector `csv` de Python. Estos controles verifican los cálculos,
**no certifican la veracidad de etiquetas sintéticas ni las ocho tablas omitidas**.
""")
code("""
validation = validate()
assert validation.passed.all()
display(Markdown(f'**{len(validation)} comprobaciones satisfactorias.** Detalle en `resultados/validacion.json`.'))
display(validation[['check','passed']].tail(8))
""")
md("""
## Takeaways

**Dirección provisional:** las etiquetas señalan recuperación y seguimiento de
quejas y problemas técnicos, pero la revisión textual limita esa recomendación.
Los casos distinguen cargos no reconocidos, cobros indebidos, problemas con app,
atención en sucursal y calidad de servicio; las descripciones no detallan causas.
Las transcripciones muestreadas son consultas de saldo aun cuando su etiqueta
indica Queja/Técnico. Estas etiquetas no deben tratarse como una clasificación
semántica validada para entrenar o evaluar un modelo.

Un prototipo útil podría mostrar qué se sabe de un caso, qué evidencia falta,
la siguiente acción permitida y cuándo debe intervenir una persona. Para
demostrar una resolución necesitará verificar el resultado de la acción; cambiar
un estado o redactar una respuesta no basta.

**Antes de prometer seguimiento automático entre fuentes:**

1. Resolver la ausencia de `origin_interaction_id`, o declarar los enlaces como
   escenarios controlados. Asociar sólo por cliente o proximidad temporal no
   equivale a verificar la identidad del caso.
2. Definir políticas de SLA, estados y fechas disponibles a cada instante. El
   estado final y las fechas futuras no deben entrar como características al
   predecir el desenlace inicial.
3. Conseguir ejemplos con causas específicas y etiquetas revisadas, o construir
   escenarios controlados claramente identificados. La muestra de transcripciones
   ya examinada no respalda el detalle semántico de Queja/Técnico. Ampliar la lectura
   tendría sentido sólo para comprobar si otros días contienen contenido distinto.
4. Reservar evaluación temporal y por cliente/caso; comparar con un baseline y
   medir resolución comprobada, derivación correcta, acciones indebidas y costo.
   La atención en portugués es un requisito del reto, no una cobertura demostrada
   por estas tablas.

**Lo que no queda probado:** causalidad entre errores, rechazos y reclamos;
ahorro económico; porcentaje automatizable; fidelidad del texto al audio; fraude
real; incumplimiento contractual; ni una probabilidad de ganar el hackathon.

### Reproducir y revisar

Instalar `requirements-eda.txt`, descargar los datos con el script del proyecto y
ejecutar todas las celdas. `REBUILD=False` permite reutilizar la selección validada;
`True` reconstruye esas selecciones. Los SQL están en `sql/eda/`, la preparación
en `scripts/eda_problemas.py` y los controles en `scripts/validar_eda.py`.
La ampliación usa `scripts/eda_detalle.py` y `sql/eda_detalle/`.
`resultados/` contiene sólo agregados; `figuras/` contiene los gráficos.
Las filas seleccionadas y el manifiesto detallado de selección quedan bajo
`dataset/_eda_problemas/`, excluido de Git.
""")
code("""
display(pd.DataFrame([{
    'Ejecución UTC': execution['executed_at_utc'],
    'Motor': f\"DuckDB {execution['duckdb_version']}\",
    'Python': execution['python'],
    'Semilla': execution['seed'],
    'Huella de metadatos': execution['source_fingerprint'],
}]).T.rename(columns={0:'Valor'}))
""")

# El resumen calculado aparece primero; los detalles técnicos quedan después.
initial_run = nbf.v4.new_code_cell('''import contextlib, io
run_log = io.StringIO()
with contextlib.redirect_stdout(run_log):
    execution = run(rebuild=REBUILD)
    detail_execution = run_detail(rebuild=REBUILD)
coverage = get('coverage')
calls = get('calls_overall').iloc[0]
cases = get('complaints_overall').iloc[0]
links = get('complaint_call_links').iloc[0]
print('EDA acotado calculado. Los detalles de cobertura y rendimiento aparecen abajo.')''')
cells = [cells[0], cells[7], cells[2], initial_run, cells[8], cells[1], cells[3],
         cells[4], cells[5], cells[6], *cells[9:]]
cells[2].metadata['jupyter'] = {'source_hidden': True}
cells[3].metadata['jupyter'] = {'source_hidden': True}
from celdas_detalle_eda import detail_cells
detail_position = next(i for i,c in enumerate(cells) if c.cell_type=='markdown' and c.source.startswith('### Comprobaciones de los resultados'))
cells[detail_position:detail_position] = detail_cells()
nb = nbf.v4.new_notebook(cells=cells)
nb.metadata = {"kernelspec": {"display_name": "Python (Factored EDA)", "language": "python", "name": "python3"},
               "language_info": {"name": "python", "version": "3.12.14"}}
nbf.validate(nb)
for i, cell in enumerate(nb.cells):
    if cell.cell_type == 'code':
        compile(cell.source, f'notebook_cell_{i}', 'exec')
dest = ROOT / "notebooks" / "EDA_PROBLEMAS.ipynb"
dest.parent.mkdir(exist_ok=True)
nbf.write(nb, dest)
print(f"Creado {dest.name}: {len(cells)} celdas, {sum(c.cell_type=='code' for c in cells)} ejecutables.")
