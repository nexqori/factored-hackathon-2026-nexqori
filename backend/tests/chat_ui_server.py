"""Isolated UI harness, never loaded by the production app. No provider calls."""
import json
import os
import secrets
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from backend.db import make_engine, make_sessions
from backend.models import Base, User, Product, Transaction, now
from backend.security import hasher
from backend.main import create_app
from backend import workflow_chat as chat
chat.inspect_prompt=lambda *a,**k: {'status':'allowed'}

if os.getenv('NEXQORI_CHAT_UI_CHECK') != '1': raise RuntimeError('Explicit isolated UI test required')
folder=Path(os.environ['NEXQORI_CHAT_UI_DATA']).resolve()
if not folder.is_relative_to(Path('.local/verification').resolve()): raise RuntimeError('Private verification directory required')
folder.mkdir(parents=True,exist_ok=True)
database=folder/'bank.sqlite'
if database.exists(): raise RuntimeError('Use a fresh verification directory')
os.environ['BANK_ASSISTANT_FLOW']='true';os.environ['BANK_FLOW_CONFIG']=str(folder);os.environ['NEXQORI_LAB_DATA']=str(folder)
engine=make_engine('sqlite:///'+str(database));Base.metadata.create_all(engine)
people=[]
with make_sessions(engine)() as db:
    for locale in ('es','en','pt'):
        for intent in ('unrecognized-charge','incorrect-charge','payment-status'):
            uid=uuid4().hex;password=secrets.token_urlsafe(24);email=uid+'@nexqori.com';account='account-'+uid;tx='tx-'+uid
            db.add(User(id=uid,email=email,name='Verificación '+locale,password_hash=hasher.hash(password),role='customer',locale=locale));db.flush()
            db.add(Product(id=account,user_id=uid,type='account',last4='9001',balance_minor=150000));db.flush()
            db.add(Transaction(id=tx,user_id=uid,product_id=account,merchant='Empresa Telefónica' if intent=='unrecognized-charge' else 'Registro privado del banco',category='utilities',amount_minor=-18500,currency='MXN',occurred_at=now(),status='pending' if intent=='payment-status' else 'completed'))
            alternate='alternate-'+uid
            if intent == 'incorrect-charge':
                for month in range(1,4):
                    db.add(Transaction(id=f'history-{month}-{uid}',user_id=uid,product_id=account,
                        merchant='Registro privado del banco',category='utilities',amount_minor=-10000,
                        currency='MXN',occurred_at=now()-timedelta(days=30*month),status='completed'))
            db.add(Transaction(id=alternate,user_id=uid,product_id=account,merchant='Comercio alternativo privado',category='shopping',amount_minor=-9900,currency='MXN',occurred_at=now()-timedelta(days=1),status='pending' if intent=='payment-status' else 'completed'))
            people.append({'email':email,'password':password,'locale':locale,'intent':intent,'transactionId':tx,'alternateTransactionId':alternate})
    db.commit()
(folder/'credentials.private.json').write_text(json.dumps(people),encoding='utf-8')
calls=[]
def triage(messages,language,*args,**kw):
    calls.append({'model':'triage','messages':messages.copy()});return {'status':'ok','family':'problem'},{}
def classify(messages,language,*args,**kw):
    calls.append({'model':'jev','messages':messages.copy()})
    intent=next(intent for intent in ('unrecognized-charge','incorrect-charge','payment-status') if intent in messages[0]['content'])
    return {'status':'ok','intent':intent},{}
def extract(messages,language,fields,*args,**kw):
    calls.append({'model':'llm','messages':messages.copy()})
    observations=[{'field':'difference','value':'100 MXN','quote':'100 MXN','message_index':len(messages)-1}] if '100 MXN' in messages[-1]['content'] else []
    return {'status':'ok','observations':observations,'assessment':'consistent','latency_ms':1}
chat.editor.classify_triage=triage;chat.editor.classify_jev=classify;chat.editor.extract=extract
chat.provider_status=lambda:{'jev':'configured','llm':'configured'}
app=create_app(engine,['http://127.0.0.1:5192'],False)
@app.get('/api/verification/summary')
def summary():
    return {'counts':{name:sum(c['model']==name for c in calls) for name in ('triage','jev','llm')},
            'bankRecordsSentToModels':any(value in json.dumps(calls,ensure_ascii=False) for value in ('Registro privado del banco','Empresa Telefónica','Comercio alternativo privado',*[p['transactionId'] for p in people],*[p['alternateTransactionId'] for p in people]))}
app.mount('/assets',StaticFiles(directory='dist/assets'))
@app.get('/{path:path}')
def frontend(path: str):
    root=Path('dist').resolve();candidate=(root/path).resolve()
    return FileResponse(candidate if candidate.is_relative_to(root) and candidate.is_file() else root/'index.html')
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=5192,access_log=False)
