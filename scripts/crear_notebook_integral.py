"""Genera el mismo notebook EDA_PROBLEMAS con alcance integral y cómputo CUDA."""
from pathlib import Path
import nbformat as nbf

ROOT=Path(__file__).resolve().parents[1]
cells=[]
def md(s):cells.append(nbf.v4.new_markdown_cell(s.strip()))
def code(s):cells.append(nbf.v4.new_code_cell(s.strip()))

md('''
# EDA integral de LATAM Bank · 13 tablas + GPU
**Factored AI & Data Hackathon 2026 · Datos sintéticos · Todo el inventario descargado**

Este notebook sustituye el muestreo exploratorio inicial por un **censo de todas
las filas y columnas de las 13 tablas**. Reúne quejas, problemas técnicos, SLA,
conversaciones, operaciones, satisfacción, clientes, productos y campañas.
Los textos y las uniones se procesan en CPU; los perfiles numéricos se calculan
por bloques en la GPU NVIDIA con CuPy/CUDA. Las salidas son agregadas.
''')
code('''
from pathlib import Path
import sys,json,contextlib,io,html
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter,PercentFormatter
from IPython.display import display,Markdown,HTML
ROOT=next((p for p in (Path.cwd(),*Path.cwd().parents) if (p/'scripts'/'eda_integral.py').exists()),None)
assert ROOT is not None,'Ejecutar desde el proyecto o notebooks/.'
sys.path.insert(0,str(ROOT/'scripts'))
from eda_integral import run
from validar_integral import validate
OUT=ROOT/'notebooks'/'resultados_integral'
FIG=ROOT/'notebooks'/'figuras_integral';FIG.mkdir(exist_ok=True)
REBUILD=False  # True vuelve a leer y perfilar TODAS las tablas, con CUDA.
pd.set_option('display.max_columns',12);pd.set_option('display.max_rows',15)
pd.set_option('display.float_format',lambda x:f'{x:,.2f}')
BLUE,ORANGE,MUTED,GOLD='#2864A5','#C65D24','#7A8CA2','#BA8B2F'
plt.rcParams.update({'figure.dpi':120,'savefig.dpi':150,'font.size':10,'axes.titlesize':12,
    'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold',
    'text.color':'#172033','axes.labelcolor':'#334155','figure.facecolor':'white','axes.facecolor':'white'})
def get(name):return pd.read_csv(OUT/f'{name}.csv')
def count(n):return f'{int(n):,}'.replace(',','.')
def pct(n):return f'{n:.2f}'.replace('.',',')+' %'
def showfig(fig,name):
    fig.savefig(FIG/f'{name}.png',bbox_inches='tight');plt.show();plt.close(fig)
def details(title,df):
    display(HTML('<details><summary><b>'+html.escape(title)+'</b></summary>'+df.to_html(index=False,escape=True)+'</details>'))
''')
md('''
### Ejecutar el análisis

La primera ejecución requiere el dataset completo y GPU NVIDIA compatible con
CUDA. Instalar `requirements-eda-gpu.txt`. `REBUILD=False` permite reutilizar
perfiles completos verificados por huellas de metadatos; recalcula las consultas
de negocio y la validación. No convierte una muestra en un censo por extrapolación.
''')
code('''
run_log=io.StringIO()
with contextlib.redirect_stdout(run_log):
    execution=run(rebuild=REBUILD)
    validation=validate()
coverage=get('coverage');numeric=get('numeric_gpu');columns=get('column_profile')
calls=get('calls_overall').iloc[0];cases=get('complaints_overall').iloc[0]
reason=get('calls_by_reason');tq=get('detalle_transcript_quality').iloc[0]
case_text=get('detalle_case_text_quality').iloc[0]
print(f"Censo calculado: {count(execution['raw_rows'])} filas, {execution['source_files']} archivos, 13 tablas.")
''')
md('''
## tl;dr

El resumen usa los datos completos. Las etiquetas sintéticas sirven para describir
los registros; su veracidad operativa y semántica se evalúa por separado.
''')
code('''
q=reason[reason.reason=='Queja'].iloc[0];t=reason[reason.reason=='Técnico'].iloc[0]
tx=get('transactions_status');declined=tx[tx.status=='Declined'].iloc[0]
sessions=get('digital_session_identity').iloc[0]
links=get('complaint_call_links').iloc[0]
owner_summary=get('integral_owner_consistency').set_index('relation')
wrong_owner=owner_summary.loc['complaints.product.customer']
display(Markdown(f''' + "'''" + '''| Hallazgo | Censo completo | Interpretación |
|---|---:|---|
| Quejas sin resolución inicial | {count(q.unresolved)} / {count(q.interactions)} ({pct(q.unresolved_pct)}) | Mayor grupo sin resolución por motivo declarado |
| Problemas técnicos sin resolución inicial | {count(t.unresolved)} / {count(t.interactions)} ({pct(t.unresolved_pct)}) | Segundo grupo por volumen sin resolver |
| SLA marcado incumplido | {count(cases.sla_breached)} / {count(cases.cases)} ({pct(cases.sla_breached_pct)}) | Etiqueta; falta la política contractual |
| Casos sin ID de interacción de origen | {count(links.cases-links.declared_links)} / {count(links.cases)} | No se puede enlazar el caso a su conversación por esa llave |
| Casos cuyo producto pertenece a otro cliente | {count(wrong_owner.mismatches)} / {count(wrong_owner.comparable)} comparables | El producto existe, pero no corresponde al cliente del caso |
| Transacciones rechazadas | {count(declined.transactions)} / {count(tx.transactions.sum())} ({pct(declined.pct_sample)}) | Estados observados; no identifica por qué se rechazaron |
| Sesiones con algún evento Error | {count(sessions.error_sessions)} / {count(sessions.sessions)} ({pct(sessions.error_session_pct)}) | Sesiones observadas; no es tasa de fallos por intento |

**Texto:** {count(tq.balance_mentions)} de {count(tq.transcripts)} textos del cliente mencionan saldo.
Los casos tienen {count(case_text.distinct_descriptions)} descripciones distintas.
Quejas y Técnico reúnen {pct((q.unresolved+t.unresolved)/calls.unresolved*100)} de las
interacciones no resueltas, pero esa concentración de etiquetas no demuestra causas ni ahorro potencial.''' + "'''" + '''))
''')
md('''
## Context & Methods

**Objetivo:** identificar problemas de atención, calidad y trazabilidad que puedan
sustentar un flujo de la hackathon. No se entrenó un modelo ni se implementaron
acciones bancarias.

- **Fuentes:** los 7.671 CSV del inventario local, el diccionario/resumen del
  organizador y `ANALISIS-REQUISITOS-HACKATHON.md`. Sin consultas a APIs bancarias.
- **Grano:** un registro por ID de cada tabla; tipos de cambio por
  `(date, source_currency, target_currency)`. Unidades diferentes no se suman como
  si fueran casos. «Caso» incluye Complaint, Claim, Request y Suggestion.
- **Limpieza:** blancos a nulo, conversiones explícitas y errores contados. Los
  grupos de clave repetida o nula se excluyen conservadoramente de las métricas de
  negocio hasta revisar su versión. Los perfiles de columnas y GPU usan todas las
  filas originales; la conciliación muestra las exclusiones.
- **Cardinalidad:** `approx_distinct` es una estimación de valores distintos;
  los conteos de filas, claves y métricas de negocio son exactos. Las variantes
  textuales informadas en el análisis de conversaciones se cuentan exactamente.
- **GPU:** CuPy calcula mínimo, máximo, media, desviación poblacional, negativos y
  ceros de los campos numéricos documentados, en bloques de 131.072 filas, con un
  pool limitado a 192 MiB. DuckDB usa hasta 1.500 MB y cuatro hilos para CSV,
  agregaciones categóricas y uniones. Estos límites no son el máximo de memoria
  total de Python o del contexto CUDA. [Instalación oficial de CuPy](https://docs.cupy.dev/en/stable/install.html).
- **Validación GPU:** cada campo se contrasta primero con NumPy en un bloque y
  después con agregaciones independientes de DuckDB sobre **todos** sus valores.
- **Caché:** `dataset/_eda_integral/` guarda las tablas locales. La huella considera
  rutas, tamaño, mtime y configuración; no es un hash criptográfico del contenido.

### Key Assumptions

`was_resolved=False` se interpreta como falta de resolución en el primer contacto,
según el diccionario. `sla_breached` se describe como etiqueta, no como un SLA
recalculado. Estados activos históricos no prueban pendientes actuales. No se
mezclan monedas para estimar pérdidas. No se supone que cliente común o proximidad
temporal identifique el mismo caso. No se atribuye causalidad a asociaciones.
''')
md('''
## Data

Las 13 tablas están incluidas. «Filas de análisis» indica lo que queda después del
control de claves, no una muestra. Los volúmenes aproximados del PDF se sustituyen
por recuentos observados; la totalidad de archivos se verifica contra el manifiesto.
''')
code('''
display(coverage[['table','files','columns','source_MB','raw_rows','analysis_rows','duplicate_key_groups','null_key_rows']])
display(Markdown(f"**{execution['source_bytes']/1e9:.3f} GB decimales**, "
    f"{count(execution['raw_rows'])} filas; {count(coverage['columns'].sum())} columnas sumadas entre tablas. "
    f"GPU utilizada: **{execution['gpu']['name']}**, CuPy {execution['gpu']['cupy']}."))
display(coverage[['table','seconds_prepare_profile']])
first_execution=json.loads((OUT/'primera_ejecucion.json').read_text(encoding='utf-8'))
display(pd.DataFrame([{'Medición':'Primera lectura y perfilado completo',
    'Segundos':first_execution['wall_seconds'],
    'Pico RSS observado MiB':first_execution['peak_process_RSS_MiB_observed']}]))
display(pd.DataFrame([{'Segundos de esta ejecución (puede reutilizar caché)':execution['wall_seconds'],
    'Pico RSS observado MiB (esta ejecución)':execution['peak_process_RSS_MiB_observed'],
    'Campos numéricos perfilados en CUDA':len(numeric),'Bloque de filas':execution['gpu_batch_rows'],
    'Pool CUDA máximo observado MiB':numeric.pool_peak_MiB.max()}]))
display(Markdown('Los tiempos por tabla corresponden a su preparación original, incluyendo compilaciones '
    'iniciales CUDA cuando ocurrieron. El recálculo con caché no mide lectura desde CSV. '
    'El RSS se muestrea cada 0,2 s y puede omitir picos. **No se afirma que GPU sea más rápida que CPU**: '
    'no se hizo un benchmark equivalente de toda la canalización.'))
''')
md('''
## Results

### 1. Calidad e integridad: qué impide confiar en los vínculos

Una referencia nula se distingue de una referencia declarada sin padre y de un
padre con ID repetido. Los nulos pueden ser legítimos según el campo. Un producto
existente tampoco garantiza que pertenezca al cliente indicado en el evento.
''')
code('''
relations=get('relations');owners=get('integral_owner_consistency')
display(relations[['child','foreign_key','nonnull_reference','null_reference','absent_parent','ambiguous_parent']])
owners['mismatch_pct_comparable']=owners.mismatches/owners.comparable.replace(0,np.nan)*100
display(owners)
quality=columns[(columns.null_rows>0)|(columns.invalid_type>0)].sort_values('null_pct',ascending=False)
display(quality[['table','column','rows','null_rows','null_pct','invalid_type']].head(15))
display(get('quality_rules'))
display(get('integral_date_domain_rules'))
branch_ref=relations[(relations.child=='customers')&(relations.foreign_key=='registration_branch_id')].iloc[0]
case_owner=owners[owners.relation=='complaints.product.customer'].iloc[0]
display(Markdown(f"**Problemas de integridad confirmados:** {count(case_owner.mismatches)} / "
    f"{count(case_owner.comparable)} casos con producto comparable apuntan a un producto de otro cliente. "
    f"Además, {count(branch_ref.absent_parent)} / {count(branch_ref.nonnull_reference)} referencias "
    'de sucursal de registro de clientes no encuentran su ID en branches. Ambos hallazgos se '
    'comprobaron de nuevo leyendo los CSV con Python. No se corrigieron IDs ni se inventaron enlaces. '
    'En eventos digitales, una referencia a producto tampoco acredita propiedad; el significado '
    'del campo debe aclararse antes de cualquier consulta o acción sobre una cuenta.'))
details('Comprobación independiente sobre CSV originales',pd.DataFrame([json.loads((OUT/'source_crosscheck.json').read_text(encoding='utf-8'))]).T.rename(columns={0:'Valor'}))
''')
md('''
### 2. Qué tipos de queja hay

Son las subcategorías declaradas en casos, no causas inferidas de la conversación.
El grupo sin subcategoría se conserva. No se les asigna la tasa de no resolución
de las interacciones, porque falta el enlace de origen entre ambas tablas.
''')
code('''
sub=get('detalle_subcategories')
display(sub[['subtype','cases','sla_breached','sla_pct','active_status','repeat_flag','high_critical']])
fig,ax=plt.subplots(figsize=(11,4.6),layout='constrained')
ax.barh(sub.subtype,sub.cases-sub.sla_breached,color=MUTED,label='Sin etiqueta de incumplimiento')
ax.barh(sub.subtype,sub.sla_breached,left=sub.cases-sub.sla_breached,color=ORANGE,label='SLA marcado incumplido')
ax.invert_yaxis();ax.set_xlim(0,sub.cases.max()*1.22)
for y,r in enumerate(sub.itertuples()):ax.text(r.cases+100,y,count(r.cases),va='center')
ax.xaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{x/1000:.0f} mil'))
ax.set_title('Tipos de casos en todo el histórico',loc='left')
ax.set_xlabel('Casos; incluye solicitudes y sugerencias');ax.legend(loc='lower right',fontsize=8,frameon=False)
showfig(fig,'01_tipos_quejas')
display(get('detalle_generic_text_by_category'))
display(Markdown(f"Las {count(case_text.generic_category_description)} descripciones genéricas "
    'no permiten separar comisiones, compras concretas, contraseña, conectividad u otras causas. '
    f"Las {count(case_text.resolutions_known)} resoluciones con texto tienen sólo "
    f"{count(case_text.distinct_resolution_texts)} frases distintas. No prueban la ejecución de un ajuste o pago."))
''')
md('''
### 3. Atención y seguimiento de las interacciones no resueltas

Se compara volumen y tasa dentro del motivo. La etiqueta `requires_followup` no
prueba que una acción de seguimiento se ejecutó. Usarla como predictor del
desenlace del mismo contacto podría introducir fuga de información.
''')
code('''
display(reason[['reason','interactions','unresolved','unresolved_pct','followup','escalated']])
fig,axs=plt.subplots(1,2,figsize=(12,4.5),layout='constrained',sharey=True)
y=np.arange(len(reason));colors=[ORANGE]+[BLUE]*(len(reason)-1)
b=axs[0].barh(y,reason.unresolved,color=colors);axs[0].set_yticks(y,reason.reason);axs[0].invert_yaxis()
axs[0].set_xlim(0,reason.unresolved.max()*1.25);axs[0].bar_label(b,labels=[count(v) for v in reason.unresolved],padding=4)
axs[0].xaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{x/1000:.0f} mil'))
axs[0].set_title('Volumen sin resolución inicial',loc='left');axs[0].set_xlabel('Interacciones')
b=axs[1].barh(y,reason.unresolved_pct,color=colors);axs[1].set_xlim(0,70)
axs[1].bar_label(b,labels=[pct(v) for v in reason.unresolved_pct],padding=4)
axs[1].xaxis.set_major_formatter(PercentFormatter(100));axs[1].set_title('Tasa dentro del motivo',loc='left')
axs[1].set_xlabel('No resueltas / motivo conocido');showfig(fig,'02_resolucion')
display(get('detalle_focus_outcomes'))
display(get('calls_by_channel')[['channel','interactions','unresolved_pct','wait_known','wait_p50_s','wait_p95_s']])
display(get('repeat_contact'))
''')
md('''
La espera sólo se compara donde está registrada; en Phone hay faltantes y en
otros canales puede no aplicar. Contacto repetido en siete días usa cliente y
motivo, excluyendo los primeros siete días del archivo. No demuestra repetición
del mismo caso y no equivale al flag de reclamante repetido en 90 días.
''')
md('''
### 4. SLA, prioridad, estado y tiempos

SLA significa compromiso/plazo de atención. No hay una política por caso para
recalcularlo. Los intervalos de 24/48 horas y 7/15/22 días son cortes exploratorios,
no plazos contractuales. Las duraciones de resolución sólo representan casos con
estado Resolved/Closed y duración conocida; no incluyen la espera de los pendientes.
''')
code('''
pri=get('detalle_sla_priority');mat=get('detalle_sla_matrix')
display(pri);display(get('complaints_by_status'))
display(get('detalle_sla_response_bins'));display(get('detalle_sla_resolution_bins'))
rates=mat.pivot(index='category',columns='priority',values='sla_pct').reindex(columns=['Critical','High','Medium','Low'])
ns=mat.pivot(index='category',columns='priority',values='cases').reindex_like(rates)
fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
im=ax.imshow(rates,cmap='Blues',vmin=0,vmax=40,aspect='auto')
ax.set_xticks(range(4),['Crítica','Alta','Media','Baja']);ax.set_yticks(range(len(rates)),rates.index)
for i in range(len(rates)):
    for j in range(4):ax.text(j,i,f'{pct(rates.iloc[i,j])}\\nn={count(ns.iloc[i,j])}',ha='center',va='center',color='#122237')
ax.set_title('SLA marcado incumplido por categoría y prioridad',loc='left',pad=12)
fig.colorbar(im,ax=ax,label='Porcentaje dentro de la celda',shrink=.85)
showfig(fig,'03_sla')
candidate=pri[pri.priority.isin(['High','Critical'])].active_and_sla.sum()
display(Markdown(f"**{count(candidate)} registros** combinan prioridad alta/crítica, estado activo y SLA marcado incumplido. "
    'Es un corte del histórico, no una lista de pendientes vigentes. Las tasas similares entre '
    'duraciones no permiten deducir un plazo ni demuestran que el SLA esté mal etiquetado.'))
''')
md('''
### 5. Problemas técnicos: acciones con Error en todos los eventos

Las tasas son eventos Error divididos por eventos de la misma acción, no intentos
únicos ni clientes. Los eventos sin acción se mantienen en la tabla, aunque no se
grafican como si fueran una acción identificada. Sin logs/códigos de backend no se
atribuyen errores a caída, contraseña, conectividad o saldo.
''')
code('''
actions=get('detalle_technical_actions');display(actions)
visible=actions[actions.action!='Sin acción'].sort_values('error_pct',ascending=False)
fig,ax=plt.subplots(figsize=(10,4.6),layout='constrained')
b=ax.barh(visible.action,visible.error_pct,color=[ORANGE if c=='Transaction' else BLUE for c in visible.event_category])
ax.invert_yaxis();ax.set_xlim(0,max(8,visible.error_pct.max()*1.35))
ax.bar_label(b,labels=[f'{pct(r.error_pct)} · {count(r.error_events)}' for r in visible.itertuples()],padding=5,fontsize=9)
ax.xaxis.set_major_formatter(PercentFormatter(100));ax.set_xlabel('Eventos Error / eventos de la acción · censo')
ax.set_title('Errores digitales: se conoce la acción, no la causa',loc='left');showfig(fig,'04_errores_digitales')
display(get('digital_channels'));display(get('digital_session_identity'))
''')
md('''
Una sesión con cualquier Error cuenta una vez. Se comprueba si un ID de sesión
agrupa varios clientes y se cuentan sesiones anónimas. El censo evita recortes de
días intermedios, pero los límites inicial/final del archivo aún pueden truncar
sesiones. Cero eventos Error de una categoría no prueba ausencia de fallos.
''')
md('''
### 6. Qué dicen realmente todas las transcripciones

Se examinan todos los archivos de `call_transcripts`. La clasificación por familia
usa prefijos explícitos y los indicadores léxicos usan regex visibles en el código;
no son un modelo validado. Los IDs se verifican antes de interpretar los textos.
''')
code('''
topics=get('detalle_transcript_topics');families=get('detalle_text_families')
display(get('detalle_transcript_quality').T.rename(columns={0:'Conteo'}))
display(topics);display(families);display(get('detalle_transcript_metadata'))
fig,ax=plt.subplots(figsize=(10,4),layout='constrained')
y=np.arange(len(topics));ax.barh(y,topics.transcripts,color=MUTED,label='Total de transcripciones')
b=ax.barh(y,topics.balance_mentions,height=.5,color=BLUE,label='Texto de cliente menciona saldo')
ax.set_yticks(y,topics.declared_topic);ax.invert_yaxis();ax.set_xlim(0,topics.transcripts.max()*1.22)
ax.bar_label(b,labels=[count(v) for v in topics.balance_mentions],padding=4)
ax.set_title('Tema declarado frente al contenido del texto del cliente',loc='left')
ax.set_xlabel('Transcripciones · histórico completo');ax.legend(loc='lower right',frameon=False,fontsize=8)
showfig(fig,'05_textos')
display(Markdown(f"**{count(tq.agent_placeholders)}** respuestas del agente conservan placeholders como "
    '`{monto}` o `{moneda}`. Si Queja/Técnico contiene consultas de saldo, la coincidencia '
    'de etiquetas entre tablas no valida la semántica. Entrenar y probar con variantes '
    'de la misma plantilla puede inflar resultados; separar familias y revisar etiquetas.'))
''')
md('''
### 7. Transacciones y cobertura monetaria

Un rechazo no se interpreta automáticamente como fraude o error técnico. Un
pendiente puede ser transitorio y un reverso una corrección válida. No se suman
importes de monedas diferentes ni se convierten faltantes USD en cero.
''')
code('''
display(tx);display(get('transactions_channel'));display(get('integral_currency_usd_coverage'))
problem=tx[tx.status!='Approved']
fig,ax=plt.subplots(figsize=(9,3.6),layout='constrained')
b=ax.barh(problem.status,problem.pct_sample,color=[ORANGE,BLUE,MUTED][:len(problem)])
ax.invert_yaxis();ax.set_xlim(0,max(7,problem.pct_sample.max()*1.5))
ax.bar_label(b,labels=[f'{pct(r.pct_sample)} · {count(r.transactions)}' for r in problem.itertuples()],padding=5)
ax.xaxis.set_major_formatter(PercentFormatter(100));ax.set_title(f'Estados de {count(tx.transactions.sum())} transacciones',loc='left')
ax.set_xlabel('Porcentaje de todas las transacciones de análisis');showfig(fig,'06_transacciones')
display(get('integral_exchange_pairs'))
display(get('integral_fraud_flags'))
''')
md('''
La columna heredada `pct_sample` de la consulta significa porcentaje del conjunto
consultado; en esta carpeta integral su denominador es el **censo completo**.
Los tipos de cambio se perfilan por par y fecha, sin sumar tasas entre monedas.
`is_fraud` y `fraud_score` son etiquetas/puntuaciones suministradas; no validan
fraude real ni sirven como verdad independiente para evaluar el mismo sistema que
las produjo. La procedencia del score debe aclararse antes de utilizarlo como predictor.
''')
md('''
### 8. Satisfacción: CSAT, NPS y CES se calculan por separado

CSAT favorable = puntuaciones 4–5 entre respuestas válidas 1–5.
NPS = porcentaje de promotores 9–10 menos detractores 0–6 entre respuestas válidas
0–10, expresado en puntos. CES se muestra sin asumir cuál extremo es favorable:
se necesita la formulación de la pregunta. No se promedian juntas las tres escalas.
Las encuestas observadas no representan a todos los clientes o interacciones.
Las escalas registradas también se revisan: en este archivo no aparecen notas 5
de CSAT ni promotores 9–10 de NPS. Esa distribución limita la interpretación y
puede reflejar cómo se generaron los datos sintéticos.
''')
code('''
scores=get('integral_survey_scores');sm=get('integral_survey_metrics');dist=get('integral_survey_distribution')
display(scores);display(sm);display(get('integral_survey_response_coverage'))
cs=sm[sm.survey_type=='CSAT'].iloc[0];np_=sm[sm.survey_type=='NPS'].iloc[0]
display(Markdown(f"**CSAT favorable:** {pct(cs.csat_satisfied/cs.csat_eligible*100)} "
    f"({count(cs.csat_satisfied)}/{count(cs.csat_eligible)} respuestas válidas). "
    f"**NPS:** {(np_.promoters-np_.detractors)/np_.nps_eligible*100:.2f} puntos "
    f"sobre {count(np_.nps_eligible)} respuestas válidas. Son métricas de este dataset sintético."))
fig,axs=plt.subplots(1,3,figsize=(12,3.8),layout='constrained')
for ax,kind in zip(axs,['CSAT','NPS','CES']):
    d=dist[(dist.survey_type==kind)&dist.main_score.notna()]
    total=dist[dist.survey_type==kind].surveys.sum()
    ax.bar(d.main_score,d.surveys/total*100,color=BLUE)
    ax.set_title(f'{kind} · n={count(total)}',loc='left');ax.set_xlabel('Puntuación registrada')
    ax.set_ylabel('% de respuestas del tipo');ax.yaxis.set_major_formatter(PercentFormatter(100))
showfig(fig,'07_satisfaccion')
details('Puntuación por motivo y resolución (sólo enlaces con mismo cliente)',get('integral_survey_resolution'))
''')
md('''
### 9. Clientes, productos y capacidad de atención

Estos son estados del archivo, sin fecha de disponibilidad de cada cambio. Las
tasas por experiencia del agente no ajustan mezcla de casos ni prueban desempeño
causal. Morosidad usa `days_past_due`, no un diagnóstico financiero; el denominador
incluye sólo productos del tipo con ese valor conocido.
''')
code('''
display(get('integral_customer_country'));display(get('integral_customer_segment'))
health=get('integral_product_health');display(health)
fig,ax=plt.subplots(figsize=(10,4.5),layout='constrained')
health=health.sort_values('over_30_pct_known',ascending=False)
b=ax.barh(health.product_type,health.over_30_pct_known,color=BLUE)
ax.invert_yaxis();ax.set_xlim(0,max(5,health.over_30_pct_known.max()*1.3))
ax.bar_label(b,labels=[pct(v) if pd.notna(v) else 'Sin dato' for v in health.over_30_pct_known],padding=4)
ax.xaxis.set_major_formatter(PercentFormatter(100));ax.set_xlabel('Productos con days_past_due > 30 / valor conocido del tipo')
ax.set_title('Días de atraso registrados por tipo de producto',loc='left');showfig(fig,'08_productos')
display(get('integral_product_currency'));display(get('integral_branch_country'));display(get('integral_agent_experience'))
''')
md('''
### 10. Campañas: entrega, conversión y coherencia temporal

Las tasas usan envíos, no clientes únicos. Apertura, clic y conversión son flags;
no se supone que formen etapas perfectamente anidadas. «Conversión» no significa
que la campaña causó la compra. Consentimiento y estados del cliente son snapshots:
un desacuerdo con envíos históricos requiere trazabilidad, no demuestra una infracción.
WhatsApp y Voice tienen cero conversiones marcadas. Antes de comparar eficacia
entre canales habría que verificar la cobertura de esa medición; los ceros por
sí solos no demuestran que esos canales no conviertan.
''')
code('''
campaigns=get('integral_campaigns_channel');display(campaigns)
fig,axs=plt.subplots(1,2,figsize=(11,4),layout='constrained',sharey=True)
y=np.arange(len(campaigns))
for ax,col,title in [(axs[0],'delivery_pct','Entregados / envíos'),(axs[1],'conversion_pct_all_sends','Conversión marcada / envíos')]:
    b=ax.barh(y,campaigns[col],color=BLUE);ax.set_xlim(0,max(1.2,campaigns[col].max()*1.25))
    ax.bar_label(b,labels=[pct(v) for v in campaigns[col]],padding=4)
    ax.xaxis.set_major_formatter(PercentFormatter(100));ax.set_title(title,loc='left')
axs[0].set_yticks(y,campaigns.send_channel);axs[0].invert_yaxis();showfig(fig,'09_campanas')
display(get('integral_campaign_rules'));display(get('integral_campaign_date_alignment'))
display(get('integral_consent_send_flags'))
details('Motivos de envíos fallidos / rebotados / bloqueados',get('integral_campaign_failure_reason'))
details('Catálogo de campañas',get('integral_campaign_catalog'))
''')
md('''
### 11. Temporalidad y fuga del resultado

`process_date` sólo tiene fecha. Eventos del día siguiente requieren aclarar el
corte del lote y la zona horaria, sin etiquetarlos automáticamente como llegadas
negativas. Fechas de resolución posteriores pueden ser resultados añadidos al
histórico: no deben considerarse conocidas cuando se abrió el caso.
''')
code('''
display(get('process_date_lags'))
cm=get('calls_monthly');sm=get('complaints_monthly')
fig,ax=plt.subplots(figsize=(11,3.8),layout='constrained');x=np.arange(len(cm))
ax.plot(x,cm.unresolved_pct,color=ORANGE,lw=2,label='No resueltas / interacciones del mes')
ax.plot(x,sm.sla_breached_pct,color=BLUE,lw=2,label='SLA marcado / casos del mes')
ticks=list(range(0,len(cm),6));ax.set_xticks(ticks,cm.month.iloc[ticks],rotation=20)
ax.set_ylim(0,35);ax.yaxis.set_major_formatter(PercentFormatter(100))
ax.axvspan(-.5,.5,color=MUTED,alpha=.12);ax.axvspan(len(cm)-1.5,len(cm)-.5,color=MUTED,alpha=.12)
ax.set_title('Evolución histórica · meses extremos parciales',loc='left');ax.legend(loc='lower left',frameon=False)
showfig(fig,'10_tiempo')
details('Cobertura de todos los campos de fecha',get('date_profile'))
''')
md('''
### 12. Perfiles completos y validación

Los desplegables incluyen **todas las columnas** de cada tabla y todos los campos
numéricos procesados en CUDA. Son conteos y estadísticas; no contienen nombres,
contactos, IDs individuales ni transcripciones. Las medias numéricas son perfiles
técnicos: no equivalen a valores económicos comparables cuando mezclan unidades.
''')
code('''
for table in coverage.table:
    d=columns[columns.table==table][['column','rows','non_null','null_pct','approx_distinct','expected_type','invalid_type']]
    details(f'{table}: perfil de todas sus columnas',d)
details('Todos los perfiles numéricos calculados en GPU',numeric[['table','column','rows_examined','finite_values','min','max','mean','std_population','negative','zero']])
details('Comparación independiente GPU vs CPU sobre todos los valores',get('gpu_vs_cpu_full'))
assert validation.passed.all()
display(Markdown(f'**{len(validation)} comprobaciones satisfactorias.** Incluyen conciliaciones, referencias, CSV independiente y perfiles GPU vs CPU completos.'))
details('Detalle de comprobaciones',validation)
tables=[]
for path in sorted(OUT.glob('*.csv')):
    frame=pd.read_csv(path)
    tables.append('<details><summary>'+html.escape(path.name)+'</summary>'
        +frame.to_html(index=False,escape=True)+'</details>')
display(HTML('<details><summary><b>Anexo: todas las tablas de resultados completas ('
    +str(len(tables))+'), sin recortar filas o columnas</b></summary>'
    +''.join(tables)+'</details>'))
''')
md('''
## Takeaways

**Qué se puede afirmar:** el archivo permite medir volumen, resolución etiquetada,
estados, SLA declarado, fricción digital y relaciones entre registros. Los tipos
de queja explícitos permiten delimitar candidatos como cargo no reconocido,
cobro indebido o problema de app. Eso no proporciona automáticamente causas,
reglas del banco ni ejemplos semánticos adecuados para entrenar.

**Qué cambia la decisión:** antes de construir recuperación de casos o un radar
de incidentes, comprobar enlaces y propietarios, revisar la correspondencia de
texto/etiquetas y definir qué información estaba disponible en cada instante.
Los productos de los casos comparables están asociados a clientes distintos y
casi todas las referencias de sucursal de registro no encuentran padre. Estos
enlaces necesitan reparación o escenarios controlados explícitos; no deben
autorizar operaciones por el simple hecho de que el ID del producto exista.
Un log con flag de seguimiento o frase de resolución no acredita una acción
ejecutada. Las afirmaciones de resolución deben apoyarse en estado verificable
de herramientas y en casos de prueba explícitos.

**Para el hackathon:** elegir un flujo, documentar sus límites y probar resolución
normal, ambigüedad y derivación humana. Comparar el componente aprendido con un
baseline y reservar casos por tiempo/cliente/familia textual según corresponda.
Mantener español y portugués en la evaluación; la cobertura bilingüe no se deduce
de datos etiquetados sólo en español. No se ha elegido ni desplegado una solución.

**Reproducción:** `requirements-eda-gpu.txt`, `scripts/eda_integral.py`,
`scripts/validar_integral.py`, `scripts/crear_notebook_integral.py` y los SQL de
`sql/eda/`, `sql/eda_detalle/`, `sql/eda_integral/`. Las carpetas `resultados_integral/`
y `figuras_integral/` son acompañantes auditables; las salidas principales ya están
guardadas en este ipynb. Las tablas originales y la caché permanecen en `dataset/`,
fuera de Git. Las versiones exploratorias previas no definen los denominadores
del presente notebook integral.
''')
code('''
details('Registro de ejecución y dispositivo CUDA',pd.DataFrame([
    {'Dato':'Ejecución UTC','Valor':execution['executed_at_utc']},
    {'Dato':'GPU','Valor':execution['gpu']['name']},
    {'Dato':'CuPy / CUDA runtime','Valor':str(execution['gpu']['cupy'])+' / '+str(execution['gpu']['cuda_runtime'])},
    {'Dato':'Motor tabular','Valor':execution['engine_tabular']},
    {'Dato':'Python','Valor':execution['python']},
    {'Dato':'Alcance','Valor':execution['scope']},
]))
''')

nb=nbf.v4.new_notebook(cells=cells)
nb.metadata={'kernelspec':{'display_name':'Python (Factored EDA GPU)','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.12.14'}}
for i,c in enumerate(nb.cells):
 if c.cell_type=='code':compile(c.source,f'cell_{i}','exec')
nb.cells[1].metadata['jupyter']={'source_hidden':True}
nb.cells[3].metadata['jupyter']={'source_hidden':True}
nbf.validate(nb)
path=ROOT/'notebooks'/'EDA_PROBLEMAS.ipynb';nbf.write(nb,path)
print(f'Notebook integral preparado: {len(cells)} celdas, {sum(c.cell_type=="code" for c in cells)} ejecutables.')
