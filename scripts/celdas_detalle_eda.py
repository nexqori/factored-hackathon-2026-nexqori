"""Celdas de ampliación del notebook; conservan el análisis base."""
import nbformat as nbf


def detail_cells():
    cells=[]
    def md(s): cells.append(nbf.v4.new_markdown_cell(s.strip()))
    def code(s): cells.append(nbf.v4.new_code_cell(s.strip()))
    md('''
### 7. Detalle de quejas: cinco subtipos y su seguimiento

**Ampliación solicitada:** distinguir motivos concretos, prioridad y SLA; comprobar
si los textos explican el problema. Se reutiliza la caché y se añaden tres columnas
de los archivos de casos (ID, descripción y resolución) y 74 particiones de
transcripciones, en los mismos días ya seleccionados. No se amplía el muestreo de
transacciones o eventos. SQL auditable: `sql/eda_detalle/`.

Las subcategorías siguientes pertenecen a la tabla de **casos**, que también
incluye solicitudes y sugerencias. No equivalen a los motivos Queja/Técnico de la
tabla de interacciones, pues falta su enlace de origen. No se atribuye la tasa de
no resolución de las interacciones a un subtipo de caso.
''')
    code('''
subtypes=get('detalle_subcategories')
display(subtypes[['subtype','cases','sla_breached','sla_pct','active_status','repeat_flag']].rename(columns={
    'subtype':'Subtipo registrado','cases':'Casos','sla_breached':'SLA marcado incumplido',
    'sla_pct':'SLA %','active_status':'Estado activo','repeat_flag':'Reclamante repetido (etiqueta)'}))
fig,ax=plt.subplots(figsize=(11,4.6),layout='constrained')
not_breached=subtypes.cases-subtypes.sla_breached
ax.barh(subtypes.subtype,not_breached,color=MUTED,label='Sin etiqueta de incumplimiento')
ax.barh(subtypes.subtype,subtypes.sla_breached,left=not_breached,color=ORANGE,label='SLA marcado incumplido')
ax.invert_yaxis(); ax.set_xlim(0,subtypes.cases.max()*1.22)
for y,r in enumerate(subtypes.itertuples()):
    ax.text(r.cases+100,y,count(r.cases),va='center',fontsize=10)
ax.set_xlabel('Casos de todo el histórico · incluye solicitudes y sugerencias')
ax.xaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{x/1000:.0f} mil'))
ax.set_title('Cinco subtipos registrados; cerca de un quinto marcado con SLA incumplido',loc='left')
ax.legend(loc='lower right',fontsize=8,frameon=False)
ax.grid(axis='x',alpha=.13); ax.set_axisbelow(True)
showfig(fig,'07_subtipos')
''')
    md('''
**Qué significan las categorías:** cargos no reconocidos y cobros indebidos
son dos etiquetas diferentes; no tenemos detalle textual para saber qué cargos,
comisiones o operaciones originaron cada caso. «Problema con app» tampoco separa
inicio de sesión, contraseña, transferencias u otros fallos. Se conserva el grupo
sin subcategoría en el denominador.
''')
    code('''
case_text=get('detalle_case_text_quality').iloc[0]
display(get('detalle_generic_text_by_category'))
display(Markdown(f"**Granularidad del texto:** {count(case_text.generic_category_description)} de "
    f"{count(case_text.cases)} descripciones son la frase genérica “Queja relacionada con [categoría]”. "
    f"Sólo hay {count(case_text.distinct_descriptions)} textos distintos. Las "
    f"{count(case_text.resolutions_known)} resoluciones con texto usan "
    f"{count(case_text.distinct_resolution_texts)} frases distintas; "
    f"{count(case_text.resolved_without_text)} casos Resolved/Closed no tienen texto de resolución. "
    'Esas frases no prueban que hubo ajuste, pago o compensación: faltan evidencias de la operación.'))
''')
    md('''
### 8. SLA: prioridades, tiempos y una cola candidata

**SLA** es el plazo o compromiso de atención acordado. Aquí sólo disponemos de la
bandera `sla_breached`; no se documentó un plazo aplicable a cada caso. Los cortes
24/48 horas y 7/15/22 días son **intervalos exploratorios**, no obligaciones del banco.
El gráfico usa la misma escala de color para todas las celdas y muestra el tamaño
de cada grupo. Las diferencias pequeñas no se presentan como causas del incumplimiento.
''')
    code('''
priority=get('detalle_sla_priority')
matrix=get('detalle_sla_matrix')
order=['Critical','High','Medium','Low']
rates=matrix.pivot(index='category',columns='priority',values='sla_pct').reindex(columns=order)
denoms=matrix.pivot(index='category',columns='priority',values='cases').reindex_like(rates)
display(priority[['priority','cases','sla_breached','sla_pct','active_and_sla','response_p50_hours']])
fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
im=ax.imshow(rates.to_numpy(),cmap='Blues',vmin=0,vmax=40,aspect='auto')
ax.set_xticks(range(4),['Crítica','Alta','Media','Baja'])
ax.set_yticks(range(len(rates)),rates.index)
for i in range(len(rates)):
    for j in range(4):
        ax.text(j,i,f'{pct(rates.iloc[i,j])}\\nn={count(denoms.iloc[i,j])}',ha='center',va='center',fontsize=10,color='#122237')
fig.colorbar(im,ax=ax,label='Casos con SLA marcado incumplido (%)',shrink=.85)
ax.set_title('SLA cercano al 20 % en las combinaciones de categoría y prioridad',loc='left',pad=14)
ax.set_xlabel('Prioridad registrada · cada n corresponde a casos de esa celda')
showfig(fig,'08_sla_prioridad')
candidate=priority[priority.priority.isin(['Critical','High'])]
display(Markdown(f"**Corte para explorar seguimiento:** {count(candidate.active_and_sla.sum())} registros "
    'combinan prioridad alta/crítica, estado activo y SLA marcado incumplido. '
    'Es una selección del archivo histórico, no una lista de pendientes vigentes hoy. '
    'Prioridad y SLA serían reglas de selección; no evidencia de que conocemos la solución del caso.'))
''')
    code('''
display(get('detalle_sla_response_bins').rename(columns={'response_group':'Primera respuesta','cases':'Casos','sla_breached':'SLA incumplido','sla_pct':'SLA %'}))
display(get('detalle_sla_resolution_bins').rename(columns={'duration_group':'Duración registrada','cases':'Casos','sla_breached':'SLA incumplido','sla_pct':'SLA %'}))
display(get('detalle_sla_channels')[['reception_channel','cases','sla_breached','sla_pct','response_known','response_p50_hours']])
''')
    md('''
Las tasas de la etiqueta SLA siguen cercanas a un quinto tanto con respuesta
temprana/tardía como entre casos resueltos en pocos o muchos días. Las medianas
de primera respuesta por prioridad son parecidas. **No podemos derivar un plazo
contractual ni validar un predictor de vencimiento a partir de esta bandera sola**.
Esto puede reflejar el generador sintético o reglas no entregadas; el EDA no
demuestra independencia estadística ni que las etiquetas sean falsas.
''')
    md('''
### 9. Quejas y problemas técnicos: seguimiento registrado y señal digital

Se revisa si falta la marca de seguimiento o derivación después de una interacción
no resuelta. Son flags del mismo registro, no un log de acciones realizadas.
''')
    code('''
focus=get('detalle_focus_outcomes')
display(focus[['contact_reason','unresolved','unresolved_with_followup','unresolved_escalated','unresolved_without_flags','unresolved_negative']])
display(Markdown(f"Las {count(focus.unresolved.sum())} interacciones no resueltas de Queja/Técnico "
    f"incluyen {count(focus.unresolved_with_followup.sum())} marcadas para seguimiento; "
    f"{count(focus.unresolved_escalated.sum())} están marcadas como escaladas. "
    'No aparece un grupo “sin seguimiento” según esos flags. Esto no acredita que el '
    'seguimiento se ejecutara o resolviera el caso. Usar `requires_followup` para '
    'predecir `was_resolved` podría filtrar información del desenlace y exige revisar su origen.'))
display(get('detalle_focus_channels')[['contact_reason','channel','interactions','unresolved_pct']])
''')
    code('''
actions=get('detalle_technical_actions')
display(actions[['action','event_category','events','error_events','error_pct']].rename(columns={
    'action':'Acción registrada','event_category':'Categoría','events':'Eventos','error_events':'Eventos Error','error_pct':'Error %'}))
visible=actions[actions.action!='Sin acción'].sort_values('error_pct',ascending=False)
fig,ax=plt.subplots(figsize=(10,4.6),layout='constrained')
bars=ax.barh(visible.action,visible.error_pct,color=[ORANGE if c=='Transaction' else BLUE for c in visible.event_category])
ax.invert_yaxis(); ax.set_xlim(0,8)
ax.bar_label(bars,labels=[f'{pct(r.error_pct)} · {count(r.error_events)}' for r in visible.itertuples()],padding=5,fontsize=9)
ax.xaxis.set_major_formatter(PercentFormatter(100))
ax.set_title('La muestra identifica acciones con Error, pero no su causa técnica',loc='left')
ax.set_xlabel('Eventos Error / eventos de la misma acción · 74 particiones muestreadas')
ax.grid(axis='x',alpha=.13); ax.set_axisbelow(True)
showfig(fig,'09_acciones_tecnicas')
''')
    md('''
Hay errores etiquetados al iniciar transferencias y pagos, consultar movimientos
y navegar. Los denominadores son **eventos de la acción**, no intentos únicos ni
clientes afectados. No se han analizado códigos de error, excepciones o logs de
backend: no podemos distinguir saldo insuficiente, caída del servicio, contraseña,
conectividad u otra causa. Tampoco se enlazan estos errores con las quejas por
coincidencia temporal.
''')
    md('''
### 10. Transcripciones: el detalle semántico no respalda las categorías

Se examinan **todas las transcripciones de las 74 particiones seleccionadas**, de
todos los motivos; no se seleccionaron sólo textos con «saldo». El texto queda en
la caché local y el notebook conserva únicamente agregados. Las reglas de palabras
son explícitas en `scripts/eda_detalle.py` y no constituyen un clasificador validado.
Se revisaron también las variantes textuales distintas para comprobar la estructura.
''')
    code('''
tq=get('detalle_transcript_quality').iloc[0]
topics=get('detalle_transcript_topics')
families=get('detalle_text_families')
display(pd.DataFrame([
    ['Transcripciones examinadas',tq.transcripts],
    ['Interacción y cliente coinciden',tq.same_customer],
    ['Texto del cliente menciona saldo',tq.balance_mentions],
    ['Texto del agente conserva placeholders',tq.agent_placeholders],
    ['Textos de cliente exactamente distintos',tq.distinct_customer_texts],
],columns=['Comprobación','Registros / variantes']))
display(topics[['declared_topic','transcripts','balance_mentions','complaint_keyword','technical_keyword']])
display(families)
display(get('detalle_transcript_metadata'))
fig,ax=plt.subplots(figsize=(10,4),layout='constrained')
pos=np.arange(len(topics))
ax.barh(pos,topics.transcripts,color=MUTED,label='Transcripciones muestreadas')
bars=ax.barh(pos,topics.balance_mentions,color=BLUE,height=.5,label='Texto que menciona saldo')
ax.set_yticks(pos,topics.declared_topic); ax.invert_yaxis()
ax.set_xlim(0,topics.transcripts.max()*1.23)
ax.bar_label(bars,labels=[count(v) for v in topics.balance_mentions],padding=5)
ax.set_title('Todas las categorías de la muestra contienen consultas de saldo',loc='left')
ax.set_xlabel('Transcripciones por tema declarado · no son motivos inferidos del texto')
ax.legend(loc='lower right',frameon=False,fontsize=8)
ax.grid(axis='x',alpha=.13); ax.set_axisbelow(True)
showfig(fig,'10_textos_vs_etiquetas')
''')
    md('''
**Lo observado:** las dos familias son consultas de saldo de cuenta de ahorros o
tarjeta, con cierres genéricos como agradecimientos. Los campos `main_topics` y
`contact_reason` sí coinciden entre tablas y los IDs enlazan al mismo cliente;
la limitación es **semántica**, no un JOIN roto en la muestra.

Los agentes conservan marcadores de plantilla como `{monto}` y `{moneda}`.
La intención detectada es `consulta_general` o falta. Las transcripciones
etiquetadas como Queja/Técnico no permiten extraer subproblemas técnicos ni causas
de reclamo a partir de este corpus muestreado. **No se extrapola esta conclusión
a transcripciones fuera de los 74 días.**

Para un componente aprendido, estas etiquetas requieren revisión. Un split
aleatorio podría repartir versiones de las mismas plantillas entre entrenamiento
y prueba y dar una impresión engañosa de capacidad; conviene separar por familia
textual y evaluar también con casos de otro origen, claramente declarados.
''')
    code('''
detail_checks=pd.read_json(OUT/'detalle_validacion.json')
assert detail_checks.passed.all()
display(Markdown(f"**Ampliación validada:** {len(detail_checks)} comprobaciones adicionales. "
    f"Se añadieron {detail_execution['new_unique_source_bytes']/1e6:.2f} MB de archivos nuevos "
    'de transcripciones; las descripciones de casos se releyeron de los archivos ya incluidos.'))
display(pd.DataFrame(detail_execution['counts']))
''')
    return cells
