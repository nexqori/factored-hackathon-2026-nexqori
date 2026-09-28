"""EDA de todas las filas de las 13 tablas; CPU tabular + GPU numérica real."""
from __future__ import annotations
import argparse,csv,hashlib,json,os,platform,threading,time
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd
import psutil

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'dataset'
CACHE=DATA/'_eda_integral'
OUT=ROOT/'notebooks'/'resultados_integral'
VERSION='1'
PK={
 'branches':['branch_id'],'customers':['customer_id'],'products':['product_id'],
 'service_agents':['agent_id'],'marketing_campaigns':['campaign_id'],
 'daily_exchange_rates':['date','source_currency','target_currency'],
 'call_center_interactions':['interaction_id'],'call_transcripts':['transcript_id'],
 'complaints':['complaint_id'],'satisfaction_surveys':['survey_id'],
 'transactions':['transaction_id'],'digital_events':['event_id'],'campaign_sends':['send_id']}
NUM={
 'branches':'atm_count teller_window_count latitude longitude',
 'customers':'credit_score estimated_monthly_income',
 'products':'current_balance credit_limit interest_rate days_past_due',
 'service_agents':'avg_csat total_monthly_interactions',
 'marketing_campaigns':'budget expected_conversion_rate',
 'daily_exchange_rates':'exchange_rate buy_rate sell_rate',
 'call_center_interactions':'duration_seconds wait_time_seconds sentiment_score',
 'call_transcripts':'accent_confidence duration_seconds',
 'complaints':'claimed_amount resolution_days compensation_granted resolution_satisfaction',
 'satisfaction_surveys':'main_score question_1_response question_2_response question_3_response response_time_hours campaign_response_rate',
 'transactions':'amount amount_usd fraud_score latitude longitude',
 'digital_events':'event_value duration_seconds',
 'campaign_sends':'click_count conversion_value send_cost'}


def ident(s):return '"'+s.replace('"','""')+'"'
def literal(s):return "'"+str(s).replace("'","''")+"'"
def save(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def write_df(name,rows):
 OUT.mkdir(parents=True,exist_ok=True)
 df=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
 df.to_csv(OUT/f'{name}.csv',index=False,encoding='utf-8')
 return df
def connect():
 CACHE.mkdir(parents=True,exist_ok=True)
 con=duckdb.connect(str(CACHE/'integral.duckdb'))
 con.execute("SET memory_limit='1500MB'")
 con.execute('SET threads=4')
 con.execute('SET preserve_insertion_order=false')
 con.execute(f"SET temp_directory={literal((CACHE/'spill').as_posix())}")
 return con
def dtype(table,col):
 if col in NUM[table].split():return 'DOUBLE'
 if col.startswith(('has_','was_','is_')) or col in ['accepts_marketing','requires_followup','had_conversion','sla_breached']:return 'BOOLEAN'
 if col=='process_date' or col=='date':return 'DATE'
 if col.endswith('_date') or col in ['last_updated','date_of_birth']:return 'TIMESTAMP'
 if col in ['opening_time','closing_time']:return 'TIME'
 return None


def inventory():
 manifest=json.loads((DATA/'_descarga'/'inventario-s3.json').read_text(encoding='utf-8'))
 groups=defaultdict(list)
 for obj in manifest['objects']:
  rel=obj['Key'].removeprefix('data/')
  table=rel.split('/')[0].removesuffix('.csv')
  if table not in PK:raise ValueError(f'Tabla inesperada: {table}')
  st=(DATA/rel).stat()
  if st.st_size!=obj['Size']:raise ValueError(f'Tamaño no coincide: {rel}')
  groups[table].append({'path':rel,'bytes':st.st_size,'mtime_ns':st.st_mtime_ns})
 assert set(groups)==set(PK)
 for files in groups.values():files.sort(key=lambda x:x['path'])
 return dict(groups)


def gpu_init():
 import cupy as cp
 if cp.cuda.runtime.getDeviceCount()<1:raise RuntimeError('No hay dispositivo CUDA disponible')
 cp.cuda.Device(0).use()
 pool=cp.get_default_memory_pool();pool.set_limit(size=192*1024**2)
 free,total=cp.cuda.runtime.memGetInfo()
 props=cp.cuda.runtime.getDeviceProperties(0)
 name=props['name'].decode() if isinstance(props['name'],bytes) else props['name']
 check=cp.arange(10000,dtype=cp.float64).sum().item()
 assert check==49995000
 cp.cuda.Stream.null.synchronize()
 pool.free_all_blocks()
 return cp,{'name':name,'cupy':cp.__version__,'cuda_runtime':cp.cuda.runtime.runtimeGetVersion(),
   'cuda_driver':cp.cuda.runtime.driverGetVersion(),'memory_free_MiB_after_context':free/2**20,
   'memory_total_MiB':total/2**20,'pool_limit_MiB':192,'smoke_test_sum':check,
   'documentation':'https://docs.cupy.dev/en/stable/install.html'}


def numeric_gpu(con,table,cp):
 cols=NUM[table].split()
 if not cols:return [],[]
 states={c:{'n':0,'mean':0.0,'m2':0.0,'min':float('inf'),'max':-float('inf'),'negative':0,'zero':0,'nonfinite':0,'rows':0} for c in cols}
 checks=[]
 query='SELECT '+','.join(f'try_cast({ident(c)} AS DOUBLE) AS {ident(c)}' for c in cols)+f' FROM raw_{table}'
 started=time.perf_counter();batches=0;pool_peak=0
 reader=con.execute(query).to_arrow_reader(batch_size=131072)
 for batch in reader:
  batches+=1
  for j,c in enumerate(cols):
   a=batch.column(j).to_numpy(zero_copy_only=False).astype(np.float64,copy=False)
   g=cp.asarray(a);good=cp.isfinite(g);x=g[good]
   n=int(x.size);st=states[c]
   st['rows']+=len(a);st['nonfinite']+=int(cp.isinf(g).sum().item())
   if n:
    mean=float(cp.mean(x).item());m2=float(cp.sum((x-mean)**2).item())
    mi=float(cp.min(x).item());ma=float(cp.max(x).item())
    if st['n']:
     delta=mean-st['mean'];newn=st['n']+n
     st['m2']+=m2+delta**2*st['n']*n/newn;st['mean']+=delta*n/newn
    else:st['mean']=mean;st['m2']=m2
    st['n']+=n;st['min']=min(st['min'],mi);st['max']=max(st['max'],ma)
    st['negative']+=int(cp.count_nonzero(x<0).item());st['zero']+=int(cp.count_nonzero(x==0).item())
    if batches==1:
     cpu=a[np.isfinite(a)]
     passed=n==len(cpu) and np.isclose(mean,cpu.mean(),rtol=1e-9,atol=1e-7) and mi==cpu.min() and ma==cpu.max()
     checks.append({'table':table,'column':c,'batch_rows':len(a),'passed':bool(passed),'cpu_mean':float(cpu.mean()),'gpu_mean':mean})
     assert passed,f'Discrepancia CPU/GPU: {table}.{c}'
   pool_peak=max(pool_peak,cp.get_default_memory_pool().total_bytes())
   del x,good,g
 cp.cuda.Stream.null.synchronize()
 elapsed=time.perf_counter()-started
 rows=[]
 for c,s in states.items():
  rows.append({'table':table,'column':c,'rows_examined':s['rows'],'finite_values':s['n'],
    'nonfinite_inf':s['nonfinite'],'min':s['min'] if s['n'] else None,'max':s['max'] if s['n'] else None,
    'mean':s['mean'] if s['n'] else None,'std_population':(max(0,s['m2'])/s['n'])**.5 if s['n'] else None,
    'negative':s['negative'],'zero':s['zero'],'batch_size':131072,'batches':batches,
    'table_gpu_profile_wall_s':elapsed,'pool_peak_MiB':pool_peak/2**20,'engine':'CuPy/CUDA'})
 cp.get_default_memory_pool().free_all_blocks()
 return rows,checks


def prepare_table(con,table,files,cp,rebuild=False):
 fingerprint=hashlib.sha256(json.dumps({'version':VERSION,'files':files,'numeric':NUM[table]},sort_keys=True).encode()).hexdigest()
 marker=CACHE/f'{table}_profile.json'
 if marker.exists() and not rebuild:
  old=json.loads(marker.read_text(encoding='utf-8'))
  if old['fingerprint']==fingerprint:
   print(f'{table}: caché integral comprobada ({old["summary"]["raw_rows"]:,} filas)',flush=True)
   return old
 start=time.perf_counter();schemas=defaultdict(int);cols=[]
 for f in files:
  with (DATA/f['path']).open(encoding='utf-8-sig',newline='') as stream:header=next(csv.reader(stream))
  schemas[tuple(header)]+=1
  for c in header:
   if c not in cols:cols.append(c)
 paths='['+','.join(literal((DATA/f['path']).as_posix()) for f in files)+']'
 projection=','.join(f"nullif(trim({ident(c)}),'') AS {ident(c)}" for c in cols)
 print(f'{table}: leyendo {len(files)} archivos, {sum(f["bytes"] for f in files)/1e6:.1f} MB, {len(cols)} columnas',flush=True)
 con.execute(f'CREATE OR REPLACE TABLE raw_{table} AS SELECT {projection} FROM read_csv({paths},header=true,all_varchar=true,union_by_name=true,hive_partitioning=false,strict_mode=true,parallel=false)')
 n=con.execute(f'SELECT count(*) FROM raw_{table}').fetchone()[0]
 # All columns, one bounded aggregate pass. Cardinality is explicitly approximate.
 expressions=[]
 for c in cols:
  expressions += [f'count({ident(c)})',f'approx_count_distinct({ident(c)})']
  cast=dtype(table,c)
  expressions += [f'count(*) FILTER(WHERE {ident(c)} IS NOT NULL AND try_cast({ident(c)} AS {cast}) IS NULL)' if cast else '0']
 values=con.execute('SELECT '+','.join(expressions)+f' FROM raw_{table}').fetchone()
 profile=[]
 for j,c in enumerate(cols):
  known,ndv,invalid=values[j*3:j*3+3]
  profile.append({'table':table,'column':c,'rows':n,'non_null':known,'null_rows':n-known,
      'null_pct':100*(n-known)/n if n else 0,'approx_distinct':ndv,'expected_type':dtype(table,c) or 'VARCHAR','invalid_type':invalid})
 pk=PK[table];keycols=','.join(ident(k) for k in pk);nulltest=' OR '.join(f'{ident(k)} IS NULL' for k in pk)
 con.execute(f'CREATE OR REPLACE TABLE keys_{table} AS SELECT {keycols},count(*) AS _n FROM raw_{table} GROUP BY {keycols}')
 null_rows,duplicate_rows,duplicate_groups=con.execute(f'SELECT coalesce(sum(_n) FILTER(WHERE {nulltest}),0),coalesce(sum(_n) FILTER(WHERE _n>1 AND NOT({nulltest})),0),count(*) FILTER(WHERE _n>1 AND NOT({nulltest})) FROM keys_{table}').fetchone()
 unique_keys=con.execute(f'SELECT count(*) FROM keys_{table} WHERE NOT({nulltest})').fetchone()[0]
 con.execute(f'CREATE OR REPLACE TABLE bad_{table} AS SELECT {keycols} FROM keys_{table} WHERE _n>1 OR ({nulltest})')
 join=' AND '.join(f'r.{ident(k)} IS NOT DISTINCT FROM b.{ident(k)}' for k in pk)
 # Conservative: repeated key groups are withheld instead of guessing latest state.
 con.execute(f'CREATE OR REPLACE VIEW clean_{table} AS SELECT r.* FROM raw_{table} r WHERE NOT EXISTS (SELECT 1 FROM bad_{table} b WHERE {join})')
 typed=','.join(f'try_cast({ident(c)} AS {dtype(table,c)}) AS {ident(c)}' if dtype(table,c) else ident(c) for c in cols)
 con.execute(f'CREATE OR REPLACE VIEW {table} AS SELECT {typed} FROM clean_{table}')
 analysis_rows=con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
 assert n==analysis_rows+null_rows+duplicate_rows
 numeric,checks=numeric_gpu(con,table,cp)
 out={'fingerprint':fingerprint,'summary':{'table':table,'files':len(files),'source_MB':sum(f['bytes'] for f in files)/1e6,
   'columns':len(cols),'raw_rows':n,'analysis_rows':analysis_rows,'distinct_keys':unique_keys,
   'null_key_rows':null_rows,'duplicate_key_groups':duplicate_groups,'rows_in_duplicate_groups':duplicate_rows,
   'schema_variants':len(schemas),'seconds_prepare_profile':time.perf_counter()-start},
   'column_profile':profile,'numeric_gpu':numeric,'gpu_cpu_checks':checks,
   'schemas':[{'columns':list(k),'files':v} for k,v in schemas.items()]}
 con.execute('CHECKPOINT');save(marker,out)
 print(f'{table}: {n:,} filas; GPU {len(numeric)} campos; {out["summary"]["seconds_prepare_profile"]:.1f} s',flush=True)
 return out


def aliases(con):
 for alias,table in {'calls':'call_center_interactions','cases':'complaints','tx':'transactions','events':'digital_events',
                     'case_text':'complaints','transcript_text':'call_transcripts'}.items():
  con.execute(f'CREATE OR REPLACE VIEW {alias} AS SELECT * FROM {table}')
 con.execute("""CREATE OR REPLACE VIEW transcript_enriched AS
 SELECT t.*,c.interaction_id AS matched_interaction_id,c.customer_id AS call_customer_id,
 c.contact_reason,c.was_resolved,c.requires_followup,c.has_transcript,c.process_date AS call_process_date,
 (t.customer_id=c.customer_id) AS same_customer,(t.main_topics=c.contact_reason) AS topic_matches_reason,
 regexp_matches(lower(coalesce(t.customer_text,'')),'saldo') AS mentions_balance,
 regexp_matches(lower(coalesce(t.customer_text,'')),'quej|reclam|cobro|cargo|indebid|no reconoc|demora|mal servicio') AS complaint_keyword,
 regexp_matches(lower(coalesce(t.customer_text,'')),'error|bloque|no puedo|no funciona|no abre|falla|problema|contrase|ingresar|acceder') AS technical_keyword,
 regexp_matches(coalesce(t.agent_text,''),'\\{[^}]+\\}') AS agent_has_placeholder
 FROM transcript_text t LEFT JOIN calls c ON t.interaction_id=c.interaction_id""")


def sql_exports(con):
 metrics=[]
 for folder,prefix in [('eda',''),('eda_detalle','detalle_'),('eda_integral','integral_')]:
  for path in sorted((ROOT/'sql'/folder).glob('*.sql')):
   for block in path.read_text(encoding='utf-8').split('-- result: ')[1:]:
    name,sql=block.split('\n',1);name=prefix+name.strip()
    sql=sql.replace('transactions: muestra','transactions: completo').replace('digital_events: muestra','digital_events: completo')
    start=time.perf_counter();df=con.execute(sql).fetchdf();write_df(name,df)
    metrics.append({'query':name,'rows_exported':len(df),'seconds':time.perf_counter()-start})
    print(f'{name}: {len(df)} agregados',flush=True)
 return metrics


def run(rebuild=False):
 OUT.mkdir(parents=True,exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True)
 start=time.perf_counter();sources=inventory();cp,gpu=gpu_init()
 save(CACHE/'all_sources.json',sources)
 print('GPU real activa: '+gpu['name'],flush=True)
 proc=psutil.Process();rss=[proc.memory_info().rss];done=threading.Event()
 def monitor():
  while not done.wait(.2):rss[0]=max(rss[0],proc.memory_info().rss)
 thread=threading.Thread(target=monitor,daemon=True);thread.start()
 con=connect()
 try:
  results=[]
  for table in PK:results.append(prepare_table(con,table,sources[table],cp,rebuild))
  write_df('coverage',[r['summary'] for r in results])
  for name,key in [('column_profile','column_profile'),('numeric_gpu','numeric_gpu'),('gpu_cpu_checks','gpu_cpu_checks')]:
   write_df(name,[row for r in results for row in r[key]])
  aliases(con)
  from integral_relations import relations
  relation_result=relations(con)
  write_df('relations',relation_result)
  queries=sql_exports(con)
 finally:
  con.close();done.set();thread.join();cp.get_default_memory_pool().free_all_blocks()
 meta={'scope':'CENSO: todas las filas y columnas de las 13 tablas; sin muestreo',
  'executed_at_utc':datetime.now(timezone.utc).isoformat(),'engine_tabular':'DuckDB '+duckdb.__version__,
  'python':platform.python_version(),'gpu':gpu,'source_files':sum(len(f) for f in sources.values()),
  'source_bytes':sum(f['bytes'] for files in sources.values() for f in files),'raw_rows':sum(r['summary']['raw_rows'] for r in results),
  'wall_seconds':time.perf_counter()-start,'peak_process_RSS_MiB_observed':rss[0]/2**20,'rss_interval_s':.2,
  'memory_limit_DuckDB_MB':1500,'threads_DuckDB':4,'gpu_batch_rows':131072,'queries':queries,
  'gpu_scope':'Mínimo, máximo, media, desviación poblacional, negativos y ceros de todos los valores numéricos documentados, por bloques; texto y joins en CPU.',
  'cache_note':'Perfiles de tablas se reutilizan por huella de metadatos; la fecha de ejecución no significa relectura física de CSV. Consultas agregadas se recalculan.',
  'key_rule':'Se excluyen de métricas de negocio todas las filas de grupos de clave repetida o nula. No se adivina una versión vigente. Perfil de columnas y GPU usa todas las filas originales.',
  'fingerprints':{r['summary']['table']:r['fingerprint'] for r in results}}
 save(OUT/'ejecucion.json',meta)
 first=OUT/'primera_ejecucion.json'
 if not first.exists() or json.loads(first.read_text(encoding='utf-8')).get('fingerprints')!=meta['fingerprints']:
  save(first,meta)
 return meta


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--rebuild',action='store_true');args=parser.parse_args()
 print(json.dumps(run(args.rebuild),ensure_ascii=True,indent=2))
