"""Controlled app-access incident for LAB evaluation; never queries the bank."""
import json
import uuid
from datetime import datetime, timezone
from . import storage


def now(): return datetime.now(timezone.utc).isoformat()


def path_for(id): return storage.DATA_DIR/'app-incidents'/f'{uuid.UUID(str(id))}.json'


def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)


def reproduce():
    id=str(uuid.uuid4());reference='APP-'+id[:8].upper()
    events=[{'timestamp':now(),'event':'access_check_started','level':'info','correlation_id':reference}]
    try:
        # Deliberate local failure. No network request, bank session or account is involved.
        raise TimeoutError('session_load_timeout')
    except TimeoutError:
        events.append({'timestamp':now(),'event':'session_load_timeout','level':'error','http_status':503,
                       'component':'lab_access_probe','timeout_budget_ms':1200,'correlation_id':reference})
    record={'id':id,'reference':reference,'created_at':now(),'source':'controlled_lab_probe','scenario':'app-access-timeout',
            'state':'failed','events':events,'bank_records_accessed':False,'customer_data_included':False}
    write(path_for(id),record)
    return record


def read(id):
    path=path_for(id)
    if not path.exists(): raise FileNotFoundError()
    return json.loads(path.read_text(encoding='utf-8'))


def notifications():
    path=storage.DATA_DIR/'app-notifications.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []


def notify(incident_id,workflow_id,node_id):
    incident=read(incident_id)
    key=f'{incident_id}:{workflow_id}:{node_id}'
    rows=notifications();existing=next((row for row in rows if row['key']==key),None)
    if existing: return {**existing,'reused':True}
    row={'id':str(uuid.uuid4()),'key':key,'created_at':now(),'incident_id':str(incident_id),
         'reference':incident['reference'],'workflow_id':str(workflow_id),'node_id':node_id,
         'channel':'lab_inbox','event':'app_access_incident','state':'registered','external_delivery':False}
    rows.append(row);write(storage.DATA_DIR/'app-notifications.json',rows)
    return {**row,'reused':False}
