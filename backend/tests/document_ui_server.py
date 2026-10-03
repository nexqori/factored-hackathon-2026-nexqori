"""Isolated PDF/filter UI harness. Never loaded by the deployed application."""
import copy
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import workflow_chat as chat
from backend.db import make_engine, make_sessions
from backend.main import create_app
from backend.models import Base, Product, Transaction, User
from backend.security import hasher

if os.getenv('NEXQORI_DOCUMENT_UI_CHECK') != '1':
    raise RuntimeError('Explicit isolated document UI test required')
folder = Path(os.environ['NEXQORI_DOCUMENT_UI_DATA']).resolve()
if not folder.is_relative_to(Path('.local/verification').resolve()):
    raise RuntimeError('Private verification directory required')
folder.mkdir(parents=True, exist_ok=True)
database = folder/'bank.sqlite'
if database.exists(): raise RuntimeError('Use a fresh verification directory')
os.environ['BANK_ASSISTANT_FLOW'] = 'true'
os.environ['BANK_FLOW_CONFIG'] = str(folder)
os.environ['NEXQORI_LAB_DATA'] = str(folder)
engine = make_engine('sqlite:///'+str(database))
Base.metadata.create_all(engine)
people = []
with make_sessions(engine)() as db:
    for locale in ('es', 'en', 'pt'):
        uid = uuid4().hex; password = secrets.token_urlsafe(24)
        email = uid+'@nexqori.com'; account = 'doc-account-'+uid
        september, october = 'doc-sept-'+uid, 'doc-oct-'+uid
        db.add(User(id=uid, email=email, name='Verificación documentos '+locale,
                    password_hash=hasher.hash(password), role='customer', locale=locale))
        db.flush()
        db.add(Product(id=account, user_id=uid, type='account', last4='9101', balance_minor=150000))
        db.flush()
        db.add_all([
            Transaction(id=september, user_id=uid, product_id=account, merchant='Registro septiembre privado',
                        category='utilities', amount_minor=-25743, currency='MXN', status='completed',
                        occurred_at=datetime(2026, 9, 12, 18, tzinfo=timezone.utc)),
            Transaction(id=october, user_id=uid, product_id=account, merchant='Registro octubre privado',
                        category='utilities', amount_minor=-13819, currency='MXN', status='completed',
                        occurred_at=datetime(2026, 10, 2, 18, tzinfo=timezone.utc)),
        ])
        people.append({'email': email, 'password': password, 'locale': locale, 'accountId': account,
                       'transactionId': september, 'octoberTransactionId': october, 'septemberAmountMinor': 25743})
    db.commit()
(folder/'credentials.private.json').write_text(json.dumps(people), encoding='utf-8')
calls = []


def triage(messages, language, *args, **kwargs):
    calls.append({'model': 'triage', 'messages': copy.deepcopy(messages)})
    return {'status': 'ok', 'family': 'query'}, {}


def classify(messages, language, *args, **kwargs):
    calls.append({'model': 'jev', 'messages': copy.deepcopy(messages)})
    latest = next(m['content'] for m in reversed(messages) if m['role'] == 'user')
    return {'status': 'ok', 'intent': 'documents' if 'pdf' in latest.lower() else 'account-activity'}, {}


def extract(messages, language, *args, **kwargs):
    calls.append({'model': 'llm', 'messages': copy.deepcopy(messages)})
    return {'status': 'ok', 'observations': [], 'assessment': 'consistent', 'latency_ms': 1}


chat.editor.classify_triage = triage
chat.editor.classify_jev = classify
chat.editor.extract = extract
chat.provider_status = lambda: {'jev': 'configured', 'llm': 'configured'}
app = create_app(engine, ['http://127.0.0.1:5193'], False)


@app.get('/api/verification/summary')
def summary():
    private = ('Registro septiembre privado', 'Registro octubre privado', '257.43', '138.19',
               *[p['transactionId'] for p in people], *[p['octoberTransactionId'] for p in people],
               *[p['accountId'] for p in people])
    return {'counts': {name: sum(c['model'] == name for c in calls) for name in ('triage', 'jev', 'llm')},
            'bankRecordsSentToModels': any(value in json.dumps(calls, ensure_ascii=False) for value in private)}


app.mount('/assets', StaticFiles(directory='dist/assets'))


@app.get('/{path:path}')
def frontend(path: str):
    root = Path('dist').resolve(); candidate = (root/path).resolve()
    return FileResponse(candidate if candidate.is_relative_to(root) and candidate.is_file() else root/'index.html')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=5193, access_log=False)
