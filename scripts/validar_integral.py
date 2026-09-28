"""Valida denominadores completos y contrasta cada perfil GPU contra SQL CPU."""
import json
import csv
import numpy as np
import pandas as pd
from eda_integral import OUT,DATA,connect,PK,NUM,save,ident,write_df


def validate():
 checks=[]
 def check(name,ok,detail=''):
  checks.append({'check':name,'passed':bool(ok),'detail':str(detail)})
  if not ok:raise AssertionError(name+' '+str(detail))
 get=lambda n:pd.read_csv(OUT/f'{n}.csv')
 cov=get('coverage').set_index('table');numeric=get('numeric_gpu')
 check('13 tablas examinadas',set(cov.index)==set(PK))
 check('7671 archivos examinados',cov.files.sum()==7671)
 for table,r in cov.iterrows():check('Conciliación filas '+table,r.raw_rows==r.analysis_rows+r.null_key_rows+r.rows_in_duplicate_groups)
 for file,col,table in [('calls_by_reason','interactions','call_center_interactions'),('calls_monthly','interactions','call_center_interactions'),
    ('complaints_by_category','cases','complaints'),('detalle_subcategories','cases','complaints'),('transactions_status','transactions','transactions'),
    ('digital_channels','events','digital_events'),('detalle_transcript_topics','transcripts','call_transcripts'),
    ('integral_survey_scores','surveys','satisfaction_surveys'),('integral_campaigns_channel','sends','campaign_sends'),
    ('integral_product_health','products','products'),('integral_customer_country','customers','customers'),('integral_branch_country','branches','branches')]:
  check('Conciliación '+file,get(file)[col].sum()==cov.loc[table,'analysis_rows'])
 check('SLA por subcategoría',get('detalle_subcategories').sla_breached.sum()==get('complaints_overall').iloc[0].sla_breached)
 check('Sin multiplicación JOIN de casos',get('detalle_case_text_quality').iloc[0]['cases']==cov.loc['complaints','analysis_rows'])
 check('Sin multiplicación JOIN de transcripciones',get('detalle_transcript_quality').iloc[0].transcripts==cov.loc['call_transcripts','analysis_rows'])
 rel=get('relations')
 check('24 relaciones con denominadores reconciliados',len(rel)==24 and (rel.rows==rel.null_reference+rel.absent_parent+rel.ambiguous_parent+rel.valid_reference).all())
 check('GPU/NumPy primer bloque',get('gpu_cpu_checks').passed.all())
 con=connect()
 cpu_checks=[];date_profile=[]
 try:
  for table,columns in NUM.items():
   cols=columns.split();expr=[]
   for col in cols:
    x=f'try_cast({ident(col)} AS DOUBLE)'
    expr.extend([f'count(*) FILTER(WHERE isfinite({x}))',f'min({x}) FILTER(WHERE isfinite({x}))',
      f'max({x}) FILTER(WHERE isfinite({x}))',f'avg({x}) FILTER(WHERE isfinite({x}))',
      f'stddev_pop({x}) FILTER(WHERE isfinite({x}))',f'count(*) FILTER(WHERE isfinite({x}) AND {x}<0)',
      f'count(*) FILTER(WHERE isfinite({x}) AND {x}=0)'])
   values=con.execute('SELECT '+','.join(expr)+f' FROM raw_{table}').fetchone()
   for i,col in enumerate(cols):
    cpu=values[i*7:(i+1)*7]
    row=numeric[(numeric.table==table)&(numeric.column==col)].iloc[0]
    passed=cpu[0]==row.finite_values and cpu[5]==row.negative and cpu[6]==row.zero
    if cpu[0]:passed=passed and all(np.isclose(cpu[j],row[field],rtol=1e-7,atol=1e-7) for j,field in [(1,'min'),(2,'max'),(3,'mean'),(4,'std_population')])
    check(f'GPU vs CPU completo {table}.{col}',passed)
    cpu_checks.append({'table':table,'column':col,'finite_values_CPU':cpu[0],'mean_CPU':cpu[3],'mean_GPU':row['mean'],'passed':bool(passed)})
   # Date coverage for every explicitly typed date/timestamp, not only partitions.
   datecols=con.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}' AND data_type IN ('DATE','TIMESTAMP') ORDER BY ordinal_position").fetchall()
   if datecols:
    query='SELECT '+','.join(f'count({ident(c)}),min({ident(c)}),max({ident(c)})' for (c,) in datecols)+f' FROM {table}'
    values=con.execute(query).fetchone()
    for j,(c,) in enumerate(datecols):date_profile.append({'table':table,'column':c,'non_null':values[j*3],'minimum':values[j*3+1],'maximum':values[j*3+2]})
  # A different parser checks the three small dimension sources completely.
  for table in ['branches','service_agents','marketing_campaigns']:
   with (DATA/(table+'.csv')).open(encoding='utf-8-sig',newline='') as f:
    reader=csv.reader(f);next(reader);n=sum(1 for _ in reader)
   check('CSV independiente '+table,n==cov.loc[table,'raw_rows'])
  # Verify surprising ownership/reference findings without the SQL join engine.
  with (DATA/'products.csv').open(encoding='utf-8-sig',newline='') as f:
   product_owners={r['product_id'].strip():r['customer_id'].strip() for r in csv.DictReader(f)}
  with (DATA/'branches.csv').open(encoding='utf-8-sig',newline='') as f:
   branch_rows=list(csv.DictReader(f));branch_ids={r['branch_id'].strip() for r in branch_rows};branch_codes={r['branch_code'].strip() for r in branch_rows}
  total=linked=missing=mismatch=0
  for path in sorted((DATA/'complaints').rglob('*.csv')):
   with path.open(encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f):
     total+=1;ref=r['affected_product_id'].strip()
     if ref:
      linked+=1
      if ref not in product_owners:missing+=1
      elif product_owners[ref]!=r['customer_id'].strip():mismatch+=1
  match_id=match_code=customer_n=0
  with (DATA/'customers.csv').open(encoding='utf-8-sig',newline='') as f:
   for r in csv.DictReader(f):
    customer_n+=1;ref=r['registration_branch_id'].strip();match_id+=ref in branch_ids;match_code+=ref in branch_codes
  owners=get('integral_owner_consistency').set_index('relation')
  check('Producto de caso vs cliente: CSV completo independiente',mismatch==owners.loc['complaints.product.customer','mismatches'])
  branch_ref=rel[(rel.child=='customers')&(rel.foreign_key=='registration_branch_id')].iloc[0]
  check('Sucursal de registro: CSV completo independiente',match_id==branch_ref.valid_reference)
  save(OUT/'source_crosscheck.json',{'method':'csv.DictReader: todos los productos, clientes y casos',
       'cases':total,'case_product_refs':linked,'absent_product':missing,'case_owner_mismatches':mismatch,
       'customers':customer_n,'branch_id_matches':match_id,'branch_code_matches':match_code})
 finally:con.close()
 write_df('gpu_vs_cpu_full',cpu_checks);write_df('date_profile',date_profile)
 save(OUT/'validacion.json',checks)
 return pd.DataFrame(checks)


if __name__=='__main__':
 x=validate();print(f'{len(x)} comprobaciones satisfactorias, incluido GPU vs CPU sobre todos los valores numéricos.')
