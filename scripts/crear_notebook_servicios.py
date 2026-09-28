"""Generate the aggregate-only Nexqori analysis notebook."""
from pathlib import Path
import nbformat as nbf
ROOT=Path(__file__).resolve().parents[1]
md=nbf.v4.new_markdown_cell
code=nbf.v4.new_code_cell
nb=nbf.v4.new_notebook()
nb.cells=[
md("""# Nexqori · servicios que necesita la base
**Censo sintético histórico, consultado el 28 de septiembre de 2026.**
La prioridad propuesta es cuentas/tarjetas, movimientos, transferencias, pagos y continuidad de solicitudes.
Las cifras describen el dataset; no prueban demanda real, causas, conversión o impacto.
Este cuaderno usa agregados sin identificadores de clientes. El script
scripts/analizar_servicios_nexqori.py contiene las 18 consultas completas de sólo lectura.
El manifiesto registra SQL, versiones, huellas SHA-256 y 13 comprobaciones."""),
code("""from pathlib import Path
import hashlib,json
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display,Image
ROOT=Path.cwd() if (Path.cwd()/'package.json').exists() else Path.cwd().parent
DATA=ROOT/'notebooks/servicios_nexqori'
FIG=ROOT/'docs/figures'
FIG.mkdir(parents=True,exist_ok=True)
manifest=json.loads((DATA/'analysis.json').read_text(encoding='utf-8'))
assert all(manifest['metadata']['checks'].values())
for name,expected in manifest['metadata']['result_sha256'].items():
    assert hashlib.sha256((DATA/name).read_bytes()).hexdigest()==expected,name
frames={p.stem:pd.read_csv(p) for p in DATA.glob('*.csv')}
q=frames['quality'].iloc[0]
display(pd.DataFrame([{'control':k,'resultado':'PASS' if v else 'FAIL'} for k,v in manifest['metadata']['checks'].items()]))
display(frames['quality'].T)"""),
md("""## Cobertura y unidades
150.000 clientes, 400.000 productos, 4.425.008 transacciones, 15.620.994 eventos,
686.296 interacciones de atención y 67.095 reclamos. El censo previo completo abarca 13 tablas y
23.495.188 filas. Productos es una fotografía; transacciones y eventos son registros históricos.
El alcance de clientes es distinto por grupo y **no se suma** entre grupos.

Transacciones y eventos: 2023-06-17 a 2026-06-18, sin zona horaria declarada en el origen.
Junio de 2023 y junio de 2026 son parciales y no permiten comparar meses completos."""),
code("""plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'figure.facecolor':'#FFFCF9',
'axes.facecolor':'#FFFCF9','text.color':'#392C27','axes.labelcolor':'#392C27',
'xtick.color':'#76645B','ytick.color':'#392C27','axes.spines.top':False,'axes.spines.right':False,'axes.spines.left':False})
def savefig(fig,name):
    fig.savefig(FIG/name,dpi=155,bbox_inches='tight',facecolor='#FFFCF9')
    plt.close(fig)
    display(Image(filename=str(FIG/name)))
p=frames['product_adoption'].sort_values('products')
fig,ax=plt.subplots(figsize=(11,5.8))
bars=ax.barh(p.product_type,p.products/1000,color='#9A4B32',height=.63)
ax.bar_label(bars,labels=[f'{n:,.0f} · {share:.1f}%' for n,share in zip(p.products,p.product_share_pct)],padding=8,fontsize=10)
ax.set_xlim(0,154);ax.set_xlabel('Productos, miles · denominador: 400.000 productos')
ax.set_title('Cuentas y tarjetas reúnen el 90,1 % de los productos',loc='left',fontweight='bold',pad=22)
ax.grid(axis='x',alpha=.12);ax.set_axisbelow(True)
fig.text(.02,-.025,'Fuente: product_adoption.csv · Censo sintético. Tenencia no equivale a uso ni a clientes exclusivos.',fontsize=9,color='#76645B')
savefig(fig,'productos.png')
display(frames['product_adoption'])"""),
md("""Cuenta de ahorro llega al 55,13 % de los 150.000 clientes y tarjeta de crédito al 48,78 %;
pueden ser las mismas personas. 139.578 clientes tienen al menos un producto.
La vinculación de una app no prueba actividad reciente. La base necesita cuentas y tarjetas
separadas, saldos por moneda, historial propio y acceso a los demás servicios."""),
code("""tx=frames['transaction_usage'].set_index('transaction_type')
recent=frames['transaction_recent'].set_index('transaction_type')
comparison=tx[['transactions','customers','share_pct','declined_pct']].join(recent[['share_pct']].rename(columns={'share_pct':'share_recent_pct'}))
comparison['difference_pp']=comparison.share_recent_pct-comparison.share_pct
display(comparison.round(3))
names={'Purchase':'Compras','Withdrawal':'Retiros','Transfer':'Transferencias','Payment':'Pagos','Deposit':'Depósitos','Adjustment':'Ajustes'}
t=tx.sort_values('transactions')
fig,ax=plt.subplots(figsize=(11,4.8))
bars=ax.barh([names[k] for k in t.index],t.transactions/1e6,color='#9A4B32',height=.6)
ax.bar_label(bars,labels=[f'{n:,.0f} · {share:.2f}%' for n,share in zip(t.transactions,t.share_pct)],padding=8,fontsize=10)
ax.set_xlim(0,1.43);ax.set_xlabel('Registros, millones · denominador: 4.425.008 transacciones')
ax.set_title('El historial reúne seis tipos de actividad',loc='left',fontweight='bold',pad=20)
ax.grid(axis='x',alpha=.12);ax.set_axisbelow(True)
fig.text(.02,-.025,'Fuente: transaction_usage.csv · Todos los estados. No son operaciones completadas ni clientes únicos.',fontsize=9,color='#76645B')
savefig(fig,'actividad.png')
country=frames['transaction_country'].pivot(index='transaction_type',columns='country',values='country_share_pct')
display(country.round(3))
print('Mayor diferencia entre países (puntos porcentuales):',round((country.max(axis=1)-country.min(axis=1)).max(),3))
display(frames['status_domains'])
display(frames['transaction_channel'])
display(frames['transaction_product'])"""),
md("""El mix de marzo–mayo de 2026, tres meses completos, difiere menos de 0,12 puntos porcentuales
del histórico por tipo. La similitud entre países pertenece a este dataset sintético;
no es evidencia para ofertas ni preferencias regionales reales.
El origen usa Approved, Declined, Pending y Reversed, no Completed. Los totales incluyen todos los estados.
POS y ATM están incluidos: volumen bancario total no equivale a actividad digital."""),
code("""display(frames['digital_action'])
pairs=frames['digital_action_type']
auth=pairs[pairs.action_name.isin(['login','logout'])]
bad=auth[((auth.action_name=='login')&(auth.event_type=='Logout'))|((auth.action_name=='logout')&(auth.event_type=='Login'))]
print('Eventos anónimos (%):',round(100*q.anonymous_events/q.digital_events,3))
print('Acciones ausentes (%):',round(100*q.missing_actions/q.digital_events,3))
print('Login/logout contradictorios:',int(bad.events.sum()),'de',int(auth.events.sum()))
display(pairs[pairs.action_name.isin(['initiate_transfer','initiate_payment'])])
display(frames['digital_channel'])
display(frames['digital_pages'])"""),
md("""Las etiquetas initiate_payment (902.225 eventos) e initiate_transfer (901.824) apoyan que ambas
rutas sean visibles. **No son pagos ni transferencias completados.** Casi 24 % de eventos son
anónimos y 10 % carecen de acción. Login/logout contradicen su tipo en aproximadamente la mitad de
sus registros: no calcular conversión o un embudo de autenticación sin reparar la semántica."""),
code("""c=frames['contact_needs'].sort_values('interactions')
fig,axes=plt.subplots(1,2,figsize=(12,5),gridspec_kw={'width_ratios':[1.4,1]})
b=axes[0].barh(c.reason,c.interactions/1000,color='#9A4B32',height=.62)
axes[0].bar_label(b,labels=[f'{n:,.0f}' for n in c.interactions],padding=5,fontsize=10)
axes[0].set_xlim(0,305);axes[0].set_xlabel('Interacciones, miles')
axes[0].set_title('Volumen por motivo',loc='left',pad=16)
b=axes[1].barh(c.reason,c.unresolved_pct,color='#A4775F',height=.62)
axes[1].bar_label(b,labels=[f'{n:.1f}%' for n in c.unresolved_pct],padding=5,fontsize=10)
axes[1].set_xlim(0,73);axes[1].set_yticks([]);axes[1].set_xlabel('% no resuelto dentro de cada motivo')
axes[1].set_title('Estado declarado',loc='left',pad=16)
for ax in axes: ax.grid(axis='x',alpha=.12);ax.set_axisbelow(True)
fig.suptitle('Mucho contacto transaccional; más falta de resolución en quejas',x=.02,ha='left',fontweight='bold',fontsize=13,y=1.02)
fig.text(.02,-.025,'Fuente: contact_needs.csv · 686.296 interacciones con estado conocido. No se atribuye causalidad.',fontsize=9,color='#76645B')
savefig(fig,'atencion.png')
display(frames['contact_needs'])
display(frames['contact_channels'])
display(frames['complaint_needs'])
display(frames['campaign_products'])"""),
md("""Queja y Técnico reúnen 96.940 de 160.266 interacciones no resueltas (60,49 %).
Las cinco subcategorías conocidas de reclamo rondan 12.000 casos cada una: no proclamar que una concentra
el problema. Las llamadas son 84,99 % de contactos; no demuestra que voz sea mejor que texto.

**Titularidad:** 44.570/44.570 reclamos con producto apuntan a otro titular;
1.094.226/1.094.242 eventos-producto comparables también discrepan.
Transacciones-productos concuerdan en 4.425.008 filas. No usar los vínculos malos como
hechos individuales ni mostrar datos ajenos en una sesión.
Campañas describen productos promocionados, no uso ni elegibilidad.
No se infieren tasas, aprobación, rentabilidad, fraude, devoluciones o políticas."""),
md("""## Decisión incorporada
- Cuentas y tarjetas: productos propios, saldo y filtro.
- Movimientos: búsqueda, estado, detalle y revisión explícita.
- Transferencias, pagos y efectivo: consulta y solicitud con contexto.
- Préstamos, inversiones y seguros: consulta sin contratación.
- Solicitudes: confirmación, referencia, idempotencia, estado y derivación simulada.
- Agente: rutas permitidas ES/EN/PT, respuestas guiadas sin LLM.
- Admin: cola y auditoría protegidas por rol.

Los fixtures son nuevos, ficticios y coherentes. No se entrenó un modelo ni se midió impacto.
Ver docs/servicios-basados-en-datos.md para decisiones y límites.""")]
nb.metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.12'}}
nbf.write(nb,ROOT/'notebooks/SERVICIOS_NEXQORI.ipynb')
print('Notebook generated')
