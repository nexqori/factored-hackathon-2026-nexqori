"""Amplía el EDA con textos de casos y una muestra de transcripciones, sin APIs."""
from __future__ import annotations
import hashlib
import json
import re
import time
from datetime import datetime, timezone

import pandas as pd

from eda_problemas import ROOT, DATA, CACHE, OUT, connect, lit, qid, export, save_json

TRANSCRIPT_FIELDS = 'transcript_id interaction_id customer_id process_date customer_text agent_text detected_language detected_intents main_topics detected_keywords'.split()
CASE_FIELDS = ['complaint_id', 'description', 'resolution']


def prepare_detail(con, rebuild=False):
    base = json.loads((CACHE / 'source_selection.json').read_text(encoding='utf-8'))
    days = set(base['sampled_days'])
    manifest = json.loads((DATA / '_descarga' / 'inventario-s3.json').read_text(encoding='utf-8'))
    transcripts = []
    for obj in manifest['objects']:
        rel = obj['Key'].removeprefix('data/')
        if not rel.startswith('call_transcripts/'):
            continue
        m = re.search(r'year=(\d{4})/month=(\d{2})/day=(\d{2})/', rel)
        if m and '-'.join(m.groups()) in days:
            st = (DATA / rel).stat()
            assert st.st_size == obj['Size'], f'Tamaño no coincide: {rel}'
            transcripts.append({'path': rel, 'bytes': st.st_size, 'mtime_ns': st.st_mtime_ns, 'day': '-'.join(m.groups())})
    transcripts.sort(key=lambda x:x['path'])
    assert {r['day'] for r in transcripts} == days, 'Faltan particiones de la muestra de transcripciones'
    case_files = base['sources']['complaints']
    selected = {'case_text': case_files, 'transcript_text': transcripts}
    fp = hashlib.sha256(json.dumps({'version':1, 'base':base['fingerprint'], 'files':selected, 'fields':[CASE_FIELDS,TRANSCRIPT_FIELDS]},sort_keys=True).encode()).hexdigest()
    marker = CACHE / 'detalle_cache.json'
    if marker.exists() and not rebuild:
        previous = json.loads(marker.read_text(encoding='utf-8'))
        if previous['fingerprint'] == fp:
            return previous, True
    start = time.perf_counter()
    counts = []
    for name, fields in [('case_text',CASE_FIELDS), ('transcript_text',TRANSCRIPT_FIELDS)]:
        paths = '['+','.join(lit((DATA/r['path']).as_posix()) for r in selected[name])+']'
        projection = ','.join(f"nullif(trim({qid(c)}),'') AS {qid(c)}" for c in fields)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT {projection} FROM read_csv({paths},header=true,all_varchar=true,union_by_name=true,hive_partitioning=false,parallel=false,strict_mode=true)")
        pk = fields[0]
        n, keys, nulls = con.execute(f'SELECT count(*),count(DISTINCT {pk}),count(*) FILTER(WHERE {pk} IS NULL) FROM {name}').fetchone()
        # Avoid multiplying case counts or ambiguously selecting transcript versions.
        if n != keys or nulls:
            raise ValueError(f'IDs no únicos en {name}; revisar versiones antes de unir')
        counts.append({'table':name,'files':len(selected[name]),'rows':n,'selected_columns':len(fields),'source_MB':sum(r['bytes'] for r in selected[name])/1e6})
    meta = {'fingerprint':fp, 'base_fingerprint':base['fingerprint'], 'sampling_seed':base['seed'],
            'counts':counts, 'sampled_days':base['sampled_days'], 'selected_sources':selected,
            'new_unique_source_bytes':sum(r['bytes'] for r in transcripts),
            'extra_scan_bytes':sum(r['bytes'] for group in selected.values() for r in group),
            'first_prepare_seconds':time.perf_counter()-start}
    con.execute('CHECKPOINT')
    save_json(marker,meta)
    return meta, False


def run_detail(rebuild=False):
    start = time.perf_counter()
    con = connect()
    try:
        meta, reused = prepare_detail(con,rebuild)
        # Explicit lexical flag, not a trained model or validated complaint classifier.
        con.execute("""CREATE OR REPLACE VIEW transcript_enriched AS
          SELECT t.*,c.interaction_id AS matched_interaction_id,c.customer_id AS call_customer_id,
            c.contact_reason,c.was_resolved,c.requires_followup,c.has_transcript,
            c.process_date AS call_process_date,
            (t.customer_id=c.customer_id) AS same_customer,
            (t.main_topics=c.contact_reason) AS topic_matches_reason,
            regexp_matches(lower(coalesce(t.customer_text,'')), 'saldo') AS mentions_balance,
            regexp_matches(lower(coalesce(t.customer_text,'')), 'quej|reclam|cobro|cargo|indebid|no reconoc|demora|mal servicio') AS complaint_keyword,
            regexp_matches(lower(coalesce(t.customer_text,'')), 'error|bloque|no puedo|no funciona|no abre|falla|problema|contrase|ingresar|acceder') AS technical_keyword,
            regexp_matches(coalesce(t.agent_text,''), '\\{[^}]+\\}') AS agent_has_placeholder
          FROM transcript_text t LEFT JOIN calls c ON t.interaction_id=c.interaction_id""")
        query_counts = []
        for path in sorted((ROOT/'sql'/'eda_detalle').glob('*.sql')):
            for block in path.read_text(encoding='utf-8').split('-- result: ')[1:]:
                name,query = block.split('\n',1)
                df = export(con,'detalle_'+name.strip(),query.strip())
                query_counts.append({'query':name.strip(),'aggregate_rows':len(df)})
        checks = validate_detail(con)
    finally:
        con.close()
    # Private manifest and row-level text stay in the ignored cache directory.
    public = {k:v for k,v in meta.items() if k!='selected_sources'}
    public.update({'executed_at_utc':datetime.now(timezone.utc).isoformat(),'cache_reused':reused,
                   'wall_seconds':time.perf_counter()-start,'query_counts':query_counts,
                   'passed_checks':len(checks),'lexical_method':'Regex explícitas en customer_text; pueden omitir sinónimos. No es clasificación validada ni prueba de ausencia de quejas.'})
    save_json(OUT/'detalle_ejecucion.json',public)
    return public


def validate_detail(con):
    checks=[]
    def check(name,actual,expected):
        passed=bool(actual==expected)
        checks.append({'check':name,'passed':passed,'actual':int(actual),'expected':int(expected)})
        assert passed, name
    get=lambda n:pd.read_csv(OUT/f'detalle_{n}.csv')
    ncases=con.execute('SELECT count(*) FROM cases').fetchone()[0]
    ntrans=con.execute('SELECT count(*) FROM transcript_text').fetchone()[0]
    check('Subcategorías concilian con casos',get('subcategories').cases.sum(),ncases)
    check('Prioridades concilian con casos',get('sla_priority').cases.sum(),ncases)
    check('Cruce categoría/prioridad conserva casos',get('sla_matrix').cases.sum(),ncases)
    check('JOIN de textos conserva casos',get('case_text_quality').iloc[0]['cases'],ncases)
    check('JOIN de transcripciones no multiplica filas',get('transcript_quality').iloc[0].transcripts,ntrans)
    check('Temas declarados concilian con muestra',get('transcript_topics').transcripts.sum(),ntrans)
    check('Familias textuales concilian con muestra',get('text_families').transcripts.sum(),ntrans)
    check('Grupos SLA/duración conservan Resolved/Closed',get('sla_resolution_bins').cases.sum(),con.execute("SELECT count(*) FROM cases WHERE status IN ('Resolved','Closed')").fetchone()[0])
    # Independent Python check over the small transcript sample, not all raw data.
    rows=con.execute('SELECT customer_text,agent_text,main_topics,call_customer_id,customer_id FROM transcript_enriched').fetchall()
    import re as regex
    q=get('transcript_quality').iloc[0]
    check('Mención saldo: regex Python vs SQL',sum('saldo' in (r[0] or '').lower() for r in rows),q.balance_mentions)
    check('Placeholders: regex Python vs SQL',sum(bool(regex.search(r'\{[^}]+\}',r[1] or '')) for r in rows),q.agent_placeholders)
    check('Identidad de cliente: Python vs SQL',sum(r[3] is not None and r[4] is not None and r[3]!=r[4] for r in rows),q.customer_mismatches)
    for name,num,den,p in [('subcategories','sla_breached','sla_known','sla_pct'),('sla_priority','sla_breached','sla_known','sla_pct')]:
        d=get(name)
        check(f'Porcentaje {name}',int(((d[num]/d[den]*100-d[p]).abs()<1e-8).all()),1)
    save_json(OUT/'detalle_validacion.json',checks)
    return checks


if __name__=='__main__':
    x=run_detail()
    print(json.dumps({k:v for k,v in x.items() if k not in ('sampled_days','query_counts')},ensure_ascii=True,indent=2))
