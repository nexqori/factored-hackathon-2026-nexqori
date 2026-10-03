from io import BytesIO
from uuid import uuid4
import json
import pytest
from pypdf import PdfReader
from sqlalchemy import select, func
from fastapi.testclient import TestClient
from backend.tests.test_api import setup, login
from backend.tests.test_workflow_chat import models, message
from backend.db import make_sessions
from backend.models import ChatDocument, AuditEvent, Transaction, Product


def query(client, control, locale='es', intent='documents'):
    control.update(family='query',intent=intent)
    r=client.post('/api/assistant/flow',json=message(message='Quiero un PDF de mi cuenta',locale=locale))
    assert r.status_code==200,r.text
    assert r.json()['flow']['canDocument']
    return r.json()['conversation']['id']


def body(kind='statement', **kw):
    return {'kind':kind,'scope':'all','locale':'es','requestKey':str(uuid4()),**({'allHistory':True} if kind=='statement' else {}),**kw}


@pytest.mark.parametrize('locale',['es','en','pt'])
@pytest.mark.parametrize('kind',['statement','products_summary','requests_summary'])
def test_document_download_history_and_own_data_only(setup,models,locale,kind):
    app,engine=setup;client,_=login(app);calls,control=models
    before=client.get('/api/bootstrap').json();cid=query(client,control,locale)
    count=len(calls);payload=body(kind,locale=locale)
    result=client.post(f'/api/conversations/{cid}/documents',json=payload)
    assert result.status_code==200,result.text
    value=result.json();ident=value['document']['id']
    assert value['message']['document']==value['document']
    assert client.post(f'/api/conversations/{cid}/documents',json=payload).json()==value
    assert client.post(f'/api/conversations/{cid}/documents',json={**payload,'scope':'selected','productId':'account-01'}).status_code in (409,422)
    download=client.get('/api/documents/'+ident)
    assert download.status_code==200 and download.content.startswith(b'%PDF-')
    assert download.headers['cache-control']=='no-store' and 'attachment;' in download.headers['content-disposition']
    text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(download.content)).pages)
    assert 'Andrea Rivera' in text and 'Mateo Silva' not in text and 'TX-2001' not in text
    assert ('TX-1002' in text)==(kind=='statement')
    assert ('NQ-1021' in text)==(kind=='requests_summary')
    assert len(calls)==count  # Generation and downloading never send banking facts to models.
    history=client.get('/api/conversations/'+cid).json()
    assert history['messages'][-1]['document']==value['document']
    listed=client.get('/api/documents').json()
    assert listed['documents']==[value['document']] and listed['nextOffset'] is None
    assert value['document']['details']['scope']=='all'
    assert value['document']['conversationId']==cid
    after=client.get('/api/bootstrap').json()
    for key in ('products','transactions','requests'):assert after[key]==before[key]
    with make_sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(ChatDocument))==1
        assert set(db.scalars(select(AuditEvent.action).where(AuditEvent.action.like('document_%'))))=={'document_generated','document_downloaded'}


def test_document_ownership_auth_and_query_gate(setup,models):
    app,_=setup;client,_=login(app);other,_=login(app,'mateo');admin,_=login(app,'nora');_,control=models
    cid=query(client,control);path=f'/api/conversations/{cid}/documents'
    for kind,selection in [('statement',{'productId':'account-02'}),('requests_summary',{'requestId':'missing'})]:
        assert client.post(path,json=body(kind,scope='selected',**selection)).status_code==404
    assert other.post(path,json=body()).status_code==404
    assert admin.post(path,json=body()).status_code==403
    assert client.post(path,json={**body(),'userId':'mateo'}).status_code==422
    generated=client.post(path,json=body('products_summary')).json();download='/api/documents/'+generated['document']['id']
    assert other.get(download).status_code==404 and admin.get(download).status_code==403
    assert other.get('/api/documents?selected='+generated['document']['id']).json()=={'documents':[],'nextOffset':None,'selected':None}
    assert admin.get('/api/documents').status_code==403
    assert TestClient(app).get(download).status_code==401
    control.update(intent='incorrect-charge',family='problem')
    claim=client.post('/api/assistant/flow',json=message(transactionId='TX-1002')).json()
    assert client.post('/api/conversations/'+claim['conversation']['id']+'/documents',json=body()).status_code==409
    client.headers.pop('X-CSRF-Token')
    assert client.post(path,json=body()).status_code==403


@pytest.mark.parametrize('override',[{'allHistory':False},{'allHistory':False,'startDate':'2026-13-01','endDate':'2026-13-02'},
    {'allHistory':False,'startDate':'2026-10-01','endDate':'2026-09-01'},
    {'allHistory':False,'startDate':'2024-01-01','endDate':'2026-01-01'},
    {'scope':'selected'},{'scope':'all','productId':'account-01'},{'allHistory':True,'startDate':'2026-09-01','endDate':'2026-09-30'}])
def test_document_rejects_ambiguous_selection_and_period(setup,models,override):
    app,_=setup;client,_=login(app);_,control=models;cid=query(client,control)
    assert client.post('/api/conversations/'+cid+'/documents',json=body(**override)).status_code==422


def test_document_date_filter_and_no_silent_truncation(setup,models):
    app,engine=setup;client,_=login(app);_,control=models;cid=query(client,control)
    payload=body(scope='selected',productId='card-01',allHistory=False,startDate='2026-09-27',endDate='2026-09-27')
    result=client.post('/api/conversations/'+cid+'/documents',json=payload).json()
    details=result['document']['details']
    own_card=next(p for p in client.get('/api/bootstrap').json()['products'] if p['id']=='card-01')
    assert details['scope']=='selected' and details['accountLast4']==own_card['last4'] and details['startDate']=='2026-09-27'
    assert client.get('/api/documents?offset=20&selected='+result['document']['id']).json()['selected']==result['document']
    text=''.join(p.extract_text() for p in PdfReader(BytesIO(client.get('/api/documents/'+result['document']['id']).content)).pages)
    assert 'TX-1002' in text and 'TX-1003' in text and 'TX-1001' not in text
    with make_sessions(engine)() as db:
        sample=db.get(Transaction,'TX-1002')
        for i in range(251):db.add(Transaction(id=f'large-doc-{i}',user_id='andrea',product_id='card-01',merchant='<b>Not markup</b>',category='shopping',amount_minor=-100,currency='MXN',occurred_at=sample.occurred_at,status='completed'))
        db.commit()
    too_many=client.post('/api/conversations/'+cid+'/documents',json=body())
    assert too_many.status_code==422 and too_many.json()['error']=='document_too_many_rows'


def test_movement_query_answers_with_records_but_keeps_them_out_of_next_provider_input(setup,models):
    app,_=setup;client,_=login(app);calls,control=models
    cid=query(client,control,intent='account-activity')
    reply=client.get('/api/conversations/'+cid).json()['messages'][-1]['text']
    assert 'TX-1002' in reply and 'Stream Plus' in reply
    client.post('/api/assistant/flow',json=message(message='Y el resumen en PDF',conversationId=cid))
    assert 'Stream Plus' not in json.dumps(calls) and 'TX-1002' not in json.dumps(calls)
