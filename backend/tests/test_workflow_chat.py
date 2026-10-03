import copy
import json
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from backend.tests.test_api import setup, login
from backend.db import make_sessions
from backend.models import AssistantTurn, AuditEvent, ConversationFlow, Message
from backend import workflow_chat as chat


@pytest.fixture
def models(monkeypatch,tmp_path):
    monkeypatch.setenv('BANK_ASSISTANT_FLOW','true')
    monkeypatch.setenv('BANK_FLOW_CONFIG',str(tmp_path))
    calls=[]; control={'intent':'incorrect-charge','family':'problem','fail':False}
    def triage(messages,language,*args,**kw):
        calls.append(('triage',copy.deepcopy(messages)))
        return {'status':'ok','family':control['family']},{}
    def classify(messages,language,*args,**kw):
        calls.append(('jev',copy.deepcopy(messages)))
        return ({'status':'error','error':'timeout'} if control['fail'] else {'status':'ok','intent':control['intent']}),{}
    def extract(messages,language,fields,*args,**kw):
        calls.append(('llm',copy.deepcopy(messages)))
        found = [{'field':'difference','value':'100 MXN','quote':'100 MXN','message_index':len(messages)-1}] if '100 MXN' in messages[-1]['content'] else []
        return {'status':'ok','observations':found,'assessment':'consistent','latency_ms':1}
    monkeypatch.setattr(chat.editor,'classify_triage',triage)
    monkeypatch.setattr(chat.editor,'classify_jev',classify)
    monkeypatch.setattr(chat.editor,'extract',extract)
    # Embedded execution must never write conversation/bank evidence into LAB files.
    monkeypatch.setattr(chat.execution,'write',lambda _:pytest.fail('bank state written to LAB file'))
    monkeypatch.setattr(chat.execution,'save_run',lambda _:pytest.fail('bank evidence copied into LAB run'))
    return calls,control


def message(**kw):
    return {'message':'Quiero revisar un cobro incorrecto','locale':'es','requestKey':str(uuid4()),**kw}


@pytest.mark.parametrize('locale',['es','en','pt'])
def test_chat_asks_then_continues_same_contract_registers_trace_without_financial_effect(setup,models,locale):
    app,engine=setup; client,_=login(app); calls,control=models
    before=client.get('/api/bootstrap').json()
    body=message(locale=locale,transactionId='TX-1002')
    r=client.post('/api/assistant/flow',json=body)
    assert r.status_code==200,r.text
    value=r.json(); cid=value['conversation']['id']
    assert value['flow']['missing_fields']==['difference'] and value['flow']['execution']['phase']=='waiting_reply'
    assert client.post('/api/assistant/flow',json=body).json()==value
    assert len(calls)==3
    assert client.get('/api/conversations/'+cid+'/flow').json()['flow']==value['flow']
    assert client.post('/api/conversations/'+cid+'/claim',json={'confirmed':True,'details':'Revisar importe diferente','requestKey':str(uuid4())}).status_code==409
    result=client.post('/api/assistant/flow',json=message(locale=locale,conversationId=cid,message='Esperaba 100 MXN'))
    assert result.status_code==200,result.text
    assert result.json()['flow']['canRegister']
    assert [c[0] for c in calls]==['triage','jev','llm','llm']
    assert 'Stream Plus' not in json.dumps(calls) and '2026-09-27' not in json.dumps(calls)
    assert not client.get('/api/conversations/'+cid+'/flow').json()['flow']['requestId']
    after=client.get('/api/bootstrap').json()
    assert before['products']==after['products'] and before['transactions']==after['transactions'] and before['requests']==after['requests']
    claim={'confirmed':True,'details':'El importe es incorrecto, esperaba 100 MXN.','requestKey':str(uuid4())}
    registered=client.post('/api/conversations/'+cid+'/claim',json=claim)
    assert registered.status_code==200,registered.text
    rid=registered.json()['id']
    assert client.post('/api/conversations/'+cid+'/claim',json=claim).json()==registered.json()
    trace=client.get('/api/requests/'+rid+'/trace').json()
    assert any(c['id']==cid for c in trace['conversations'])
    assert any(e['action']=='tool_transaction_evidence' for e in trace['events'])
    assert trace['request']['kind']=='claim' and trace['request']['status']=='received'
    calls_before=len(calls)
    followed=client.post('/api/assistant/flow',json=message(locale=locale,conversationId=cid,message='Quiero seguir el reclamo')).json()
    assert followed['flow']['state']=='registered' and followed['flow']['requestId']==rid and len(calls)==calls_before
    assert followed['flow']['jev']==result.json()['flow']['jev']
    with make_sessions(engine)() as db:
        assert db.get(ConversationFlow,cid).request_id==rid
        assert db.scalar(select(func.count()).select_from(AssistantTurn))==3
        assert db.scalar(select(func.count()).select_from(Message).where(Message.conversation_id==cid))==7


def test_flow_ownership_idempotency_and_provider_failure(setup,models):
    app,_=setup; client,_=login(app); other,_=login(app,'mateo'); admin,_=login(app,'nora'); calls,control=models
    assert client.post('/api/assistant/flow',json=message(transactionId='TX-2001')).status_code==404
    assert calls==[]
    body=message(transactionId='TX-1002'); value=client.post('/api/assistant/flow',json=body).json(); cid=value['conversation']['id']
    assert client.post('/api/assistant/flow',json={**body,'message':'changed'}).status_code==409
    assert other.post('/api/assistant/flow',json=message(conversationId=cid)).status_code==404
    assert other.get('/api/conversations/'+cid+'/flow').status_code==404
    assert admin.post('/api/assistant/flow',json=message()).status_code==403
    assert other.post('/api/conversations/'+cid+'/claim',json={'confirmed':True,'details':'reclamo de prueba','requestKey':str(uuid4())}).status_code==404
    control['fail']=True
    failure=client.post('/api/assistant/flow',json=message()).json()
    assert failure['flow']['state']=='provider_unavailable' and not failure['flow']['canRegister']


def test_phone_query_opens_payment_without_creating_request_or_debit(setup,models):
    app,_=setup;client,_=login(app);calls,control=models
    control.update(intent='phone-bill',family='query')
    before=client.get('/api/bootstrap').json()
    value=client.post('/api/assistant/flow',json=message(message='Quiero pagar mi teléfono')).json()
    assert value['navigation']['route']=='/services/catalog/phone-bill'
    assert not value['flow']['canRegister']
    after=client.get('/api/bootstrap').json()
    for key in ('products','transactions','requests'): assert before[key]==after[key]


def test_query_about_selected_movement_reads_its_status_without_a_problem_contract(setup,models):
    app,_=setup;client,_=login(app);calls,control=models
    control.update(intent='request-status',family='query')
    value=client.post('/api/assistant/flow',json=message(message='Ayúdame a entender este movimiento y su seguimiento',transactionId='TX-1005')).json()
    assert 'TX-1005' in value['text'] and 'NQ-1021' in value['text']
    assert value['flow']['contract'] is None and not value['flow']['canRegister']
    assert [c[0] for c in calls]==['triage','jev']


def test_missing_reference_can_be_selected_on_next_turn(setup,models):
    app,_=setup;client,_=login(app);calls,control=models
    control['intent']='unrecognized-charge'
    value=client.post('/api/assistant/flow',json=message()).json()
    assert 'transaction_id' in value['flow']['missing_fields']
    result=client.post('/api/assistant/flow',json=message(message='Revisa este movimiento',conversationId=value['conversation']['id'],transactionId='TX-1002'))
    assert result.status_code==200,result.text
    assert result.json()['flow']['canRegister']
    assert [c[0] for c in calls]==['triage','jev','llm','llm']


@pytest.mark.parametrize('locale,first,follow,topic',[
    ('es','tengo un problema con una transferencia','No llegó y sigue pendiente','transferencia'),
    ('en','I have a problem with a transfer','It did not arrive and is still pending','transfer'),
    ('pt','Tenho um problema com uma transferência','Não chegou e está pendente','transferência'),
])
def test_clarifying_a_problem_preserves_the_original_story(setup,models,locale,first,follow,topic):
    app,_=setup;client,_=login(app);calls,control=models
    control['intent']='needs-clarification'
    value=client.post('/api/assistant/flow',json=message(locale=locale,message=first)).json()
    assert value['flow']['triage']['family']=='problem'
    assert topic in value['text'] and not value['flow']['canRegister']
    cid=value['conversation']['id']
    assert client.get('/api/conversations/'+cid+'/flow').json()['flow']==value['flow']
    control['intent']='payment-status'
    result=client.post('/api/assistant/flow',json=message(locale=locale,message=follow,conversationId=cid)).json()
    assert result['flow']['jev']['intent']=='payment-status'
    assert calls[2][1]==[{'role':'user','content':first},{'role':'assistant','content':value['text']},{'role':'user','content':follow}]
    assert result['flow']['state']=='ask_customer' and not result['flow']['canRegister']


def test_new_query_keeps_context_but_never_sends_bank_enriched_reply_to_models(setup,models):
    app,_=setup;client,_=login(app);calls,control=models
    control.update(family='query',intent='account-balance')
    value=client.post('/api/assistant/flow',json=message(message='Quiero saber mi saldo')).json()
    control['intent']='phone-bill'
    result=client.post('/api/assistant/flow',json=message(message='Ahora quiero pagar mi teléfono',conversationId=value['conversation']['id'])).json()
    assert result['navigation']['route']=='/services/catalog/phone-bill'
    assert calls[2][1][0]['content']=='Quiero saber mi saldo'
    assert value['text'] not in [m['content'] for m in calls[2][1]]


@pytest.mark.parametrize('locale,question',[('es','¿Cuánto dinero tengo en mi cuenta?'),('en','How much money do I have?'),('pt','Quanto dinheiro tenho na minha conta?')])
def test_balance_query_answers_the_classified_intent_and_persists_bank_enriched_result(setup,models,locale,question):
    app,_=setup;client,_=login(app);calls,control=models
    control.update(family='query',intent='account-balance')
    value=client.post('/api/assistant/flow',json=message(locale=locale,message=question)).json()
    assert 'MXN' in value['text']
    assert value['flow']['bank_evidence']['reads'][0]['tool']=='read-balances'
    assert client.get('/api/conversations/'+value['conversation']['id']+'/flow').json()['flow']==value['flow']
    assert len(calls)==2
