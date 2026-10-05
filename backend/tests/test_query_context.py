"""Local period parsing, own-data summaries and later PDF defaults."""
import copy
import json
from datetime import date, datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import select

from backend import query_context as query
from backend.db import make_sessions
from backend.models import AuditEvent, Conversation, ConversationFlow, Product, Transaction
from backend.tests.test_api import setup, login
from backend.tests.test_workflow_chat import models, message


TODAY=date(2026,10,3)
PRODUCTS=[SimpleNamespace(id='account-01',last4='4821',type='account'),
          SimpleNamespace(id='savings-01',last4='7206',type='savings'),
          SimpleNamespace(id='card-01',last4='5556',type='card')]


@pytest.fixture
def frozen_clock(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):
            return datetime(2026,10,3,17,tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(query,'datetime',Clock)


@pytest.mark.parametrize('text,start,end',[
    ('último mes','2026-09-01','2026-09-30'),('last month','2026-09-01','2026-09-30'),('mês passado','2026-09-01','2026-09-30'),
    ('este mes','2026-10-01','2026-10-03'),('this month','2026-10-01','2026-10-03'),('mês atual','2026-10-01','2026-10-03'),
    ('últimos 30 días','2026-09-04','2026-10-03'),('last 30 days','2026-09-04','2026-10-03'),('últimos 30 dias','2026-09-04','2026-10-03'),
    ('septiembre de 2026','2026-09-01','2026-09-30'),('September 2026','2026-09-01','2026-09-30'),('setembro de 2026','2026-09-01','2026-09-30'),
    ('del 2026-09-05 al 2026-09-18','2026-09-05','2026-09-18'),('05/09/2026 - 18/09/2026','2026-09-05','2026-09-18'),
    ('del 5 al 18 de septiembre de 2026','2026-09-05','2026-09-18'),('September 5 to 18 2026','2026-09-05','2026-09-18'),
    ('de 5 a 18 de setembro de 2026','2026-09-05','2026-09-18'),
])
def test_exact_calendar_and_explicit_periods(text,start,end):
    assert query.period(text,TODAY)=={'startDate':start,'endDate':end,'allHistory':False}


@pytest.mark.parametrize('text',[
    'el mes de septiembre','last few months','últimos tres meses','nas últimas semanas',
    '2026-09-05','2026-09-31 a 2026-10-02','2026-10-03 a 2026-09-01',
    '2024-01-01 a 2026-10-03','desde ayer','2026-9-1','03/10/26',
    'último mes y este mes','September 2026 and October 2026','del 5 de septiembre de 2026',
    'no quiero todo mi historial','not all my history','não quero todo o histórico',
])
def test_ambiguous_periods_require_clarification(text):
    assert query.period(text,TODAY)=={}


def resolve(*texts,previous=None,products=PRODUCTS):
    return query.resolve_defaults([{'role':'user','content':text} for text in texts],products,today=TODAY,previous=previous)


def test_calendar_year_boundary_leap_year_and_document_kind_not_request_verb():
    assert query.period('last month',date(2026,1,3))['startDate']=='2025-12-01'
    assert query.period('February 2024',TODAY)['endDate']=='2024-02-29'
    assert resolve('I request a statement for last month')['draft']['kind']=='statement'
    assert resolve('Quiero el último mes','Quiero un estado de cuenta')['draft']=={
        'kind':'statement','scope':'all','startDate':'2026-09-01','endDate':'2026-09-30','allHistory':False}


@pytest.mark.parametrize('selection,expected',[
    ('cuenta terminada en 4821','account-01'),('account ending 4821','account-01'),('conta final 4821','account-01'),
    ('account-01','account-01'),('card-01','card-01'),('mi cuenta',None),
    ('account-02',None),('cuenta 1103',None),('account-01 y card-01',None),
    ('cuenta 4821 y cuenta 7206',None),('cuenta 4821 y cuenta 1103',None),
    ('cuenta 4821 y 7206',None),('otra cuenta',None),('my other account',None),('cuenta 123456789012',None),
])
def test_selection_is_unique_and_own_or_remains_missing(selection,expected):
    value=resolve('Movimientos de '+selection+' del último mes')
    assert value['draft']['scope']=='selected'
    assert value['draft'].get('productId')==expected
    assert ('selection' in value['missing'])==(expected is None)


def test_duplicate_last_four_invalid_saved_selection_and_explicit_all():
    duplicate=SimpleNamespace(id='extra-account',type='account',last4='4821')
    assert 'selection' in resolve('Movimientos cuenta 4821',products=PRODUCTS+[duplicate])['missing']
    invalid={'kind':'statement','scope':'selected','productId':'account-02','allHistory':True}
    assert 'selection' in resolve(previous=invalid)['missing']
    chosen=resolve('Movimientos cuenta 4821 del último mes')['draft']
    follow=resolve('El PDF de mi cuenta',previous=chosen)
    assert follow['draft']==chosen
    all_accounts=resolve('De todas mis cuentas',previous=chosen)['draft']
    assert all_accounts['scope']=='all' and 'productId' not in all_accounts
    assert all_accounts['startDate']=='2026-09-01'


def test_request_refs_are_unique_own_and_separate_from_product_refs():
    cases=[SimpleNamespace(id='NQ-1001',catalog_service_id='personal-loan'),SimpleNamespace(id='NQ-1002',catalog_service_id='personal-loan')]
    def result(text):return query.resolve_defaults([{'role':'user','content':text}],PRODUCTS,cases,today=TODAY)
    value=result('Seguimiento NQ-1001')
    assert value['draft']=={'kind':'requests_summary','scope':'selected','requestId':'NQ-1001'}
    assert 'selection' in result('NQ-1001 y NQ-1002')['missing']
    assert 'selection' in result('NQ-9999')['missing']
    assert 'selection' in result('NQ-')['missing']


def test_explicit_document_type_does_not_switch_for_opposite_case_reference():
    cases=[SimpleNamespace(id='NQ-1001',catalog_service_id='personal-loan'),SimpleNamespace(id='NQ-1002',catalog_service_id='incorrect-charge')]
    for text,kind in [('PDF solicitudes NQ-1002','requests_summary'),('PDF reclamos NQ-1001','claims_summary')]:
        value=query.resolve_defaults([{'role':'user','content':text}],PRODUCTS,cases,today=TODAY)
        assert value['draft']['kind']==kind and 'requestId' not in value['draft']
        assert value['missing']==['selection']


@pytest.mark.parametrize('locale,text,pdf',[
    ('es','Quiero un resumen de mis movimientos del último mes de la cuenta terminada en 4821','Quiero el PDF de ese resumen'),
    ('en','I want a summary of transactions last month for account ending 4821','Can I have that as a PDF?'),
    ('pt','Quero um resumo das movimentações do mês passado da conta final 4821','Quero o PDF desse resumo'),
])
def test_activity_filters_and_later_pdf_inherit_exact_scope_without_bank_data_to_models(setup,models,frozen_clock,locale,text,pdf):
    app,engine=setup;client,_=login(app);calls,control=models
    control.update(family='query',intent='account-activity')
    first=client.post('/api/assistant/flow',json=message(locale=locale,message=text))
    assert first.status_code==200,first.text
    first=first.json();cid=first['conversation']['id']
    assert first['navigation']['filters']=={'start':'2026-09-01','end':'2026-09-30','product':'account-01'}
    assert '2026-09-01' in first['text'] and '2026-09-30' in first['text']
    control['intent']='documents'
    second=client.post('/api/assistant/flow',json=message(locale=locale,message=pdf,conversationId=cid))
    assert second.status_code==200,second.text
    count=len(calls)
    defaults=client.get(f'/api/conversations/{cid}/document-context').json()
    assert defaults['missing']==[]
    assert defaults['draft']=={'kind':'statement','scope':'selected','productId':'account-01',
                               'startDate':'2026-09-01','endDate':'2026-09-30','allHistory':False}
    generated=client.post(f'/api/conversations/{cid}/documents',json={**defaults['draft'],'locale':locale,'requestKey':str(uuid4())})
    assert generated.status_code==200,generated.text
    doc=generated.json()['document'];content=client.get('/api/documents/'+doc['id']).content
    text=''.join(page.extract_text() for page in PdfReader(BytesIO(content)).pages)
    assert 'TX-1004' in text and 'TX-1002' not in text and 'TX-2001' not in text
    assert len(calls)==count and first['text'] not in json.dumps(calls)
    with make_sessions(engine)() as db:
        state=db.get(ConversationFlow,cid).state
        assert 'Stream Plus' not in json.dumps(state['messages'])
        assert state['queryDefaults']==defaults['draft']


@pytest.mark.parametrize('text',['Movimientos del último trimestre','Movimientos de account-02','Movimientos de mi cuenta',
                               'Movimientos de cuenta 4821 y cuenta 7206'])
def test_ambiguous_scope_or_period_does_not_fall_back_to_all_on_followup(setup,models,frozen_clock,text):
    app,_=setup;client,_=login(app);_,control=models
    control.update(family='query',intent='account-activity')
    first=client.post('/api/assistant/flow',json=message(message=text)).json()
    assert first['navigation'] is None and 'TX-' not in first['text']
    second=client.post('/api/assistant/flow',json=message(message='Quiero revisarlo',conversationId=first['conversation']['id'])).json()
    assert second['navigation'] is None and 'TX-' not in second['text']


def test_changed_period_overrides_previous_and_relative_period_is_not_reinterpreted_for_pdf(setup,models,frozen_clock,monkeypatch):
    app,_=setup;client,_=login(app);_,control=models
    control.update(family='query',intent='account-activity')
    first=client.post('/api/assistant/flow',json=message(message='Movimientos del último mes')).json()
    cid=first['conversation']['id']
    class November(datetime):
        @classmethod
        def now(cls,tz=None):return datetime(2026,11,3,17,tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(query,'datetime',November)
    control['intent']='documents'
    client.post('/api/assistant/flow',json=message(message='Dame ese PDF',conversationId=cid))
    frozen=client.get(f'/api/conversations/{cid}/document-context').json()['draft']
    assert frozen['startDate']=='2026-09-01' and frozen['endDate']=='2026-09-30'
    client.post('/api/assistant/flow',json=message(message='Mejor del 2026-10-01 al 2026-10-15',conversationId=cid))
    changed=client.get(f'/api/conversations/{cid}/document-context').json()['draft']
    assert changed['startDate']=='2026-10-01' and changed['endDate']=='2026-10-15'


def test_document_defaults_endpoint_requires_own_valid_query(setup,models,frozen_clock):
    app,_=setup;client,_=login(app);other,_=login(app,'mateo');admin,_=login(app,'nora');_,control=models
    control.update(family='query',intent='account-activity')
    cid=client.post('/api/assistant/flow',json=message(message='Movimientos del último mes')).json()['conversation']['id']
    endpoint=f'/api/conversations/{cid}/document-context'
    assert other.get(endpoint).status_code==404
    assert admin.get(endpoint).status_code==403
    assert TestClient(app).get(endpoint).status_code==401
    control.update(family='problem',intent='unrecognized-charge')
    problem=client.post('/api/assistant/flow',json=message(transactionId='TX-1002')).json()['conversation']['id']
    assert client.get(f'/api/conversations/{problem}/document-context').status_code==409


def test_summary_sql_counts_full_period_and_only_settled_amounts_with_local_day_boundaries(setup,frozen_clock):
    _,engine=setup
    with make_sessions(engine)() as db:
        conv=Conversation(id=str(uuid4()),user_id='andrea',locale='es')
        db.add(conv);db.flush()
        rows=[('before',-10000,'completed','2026-09-01T05:59:59+00:00'),
              ('start',-100,'completed','2026-09-01T06:00:00+00:00'),
              ('income',300,'completed','2026-09-15T12:00:00+00:00'),
              ('pending',-500,'pending','2026-09-16T12:00:00+00:00'),
              ('declined',-900,'declined','2026-09-17T12:00:00+00:00'),
              ('last',-200,'completed','2026-10-01T05:59:59+00:00'),
              ('after',-20000,'completed','2026-10-01T06:00:00+00:00')]
        # Use a dedicated own account so the summary cannot rely on the last-20 tool preview.
        db.add(Product(id='query-account',user_id='andrea',type='account',last4='4321',balance_minor=10000));db.flush()
        for name,amount,status,stamp in rows:
            db.add(Transaction(id='query-'+name,user_id='andrea',product_id='query-account',merchant='QUERY_PRIVATE',category='services',amount_minor=amount,status=status,occurred_at=datetime.fromisoformat(stamp)))
        for n in range(22):db.add(Transaction(id=f'query-extra-{n}',user_id='andrea',product_id='query-account',merchant='QUERY_PRIVATE',category='services',amount_minor=-100,status='completed',occurred_at=datetime(2026,9,20,tzinfo=timezone.utc)))
        db.flush()
        state={'context':{'triage':{'family':'query'},'intent':'account-activity'},
               'messages':[{'role':'user','content':'Movimientos cuenta 4321 del último mes'}]}
        original=copy.deepcopy(state['messages'])
        query.apply_query_context(db,'andrea',conv.id,state,'es')
        assert '27 movimientos' in state['context']['reply']
        assert 'Pagos y salidas: MXN 25.00' in state['context']['reply']
        assert 'Entradas: MXN 3.00' in state['context']['reply']
        assert '1 pendientes' in state['context']['reply']
        assert state['messages']==original and 'QUERY_PRIVATE' not in json.dumps(state)
        assert state['context']['navigation']['filters']['product']=='query-account'
        assert db.scalar(select(AuditEvent).where(AuditEvent.conversation_id==conv.id,AuditEvent.action=='tool_filtered_transactions'))
