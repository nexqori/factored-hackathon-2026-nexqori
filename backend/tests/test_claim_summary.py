"""Claim review and durable confirmation use bank records without a provider call."""
import copy
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.claim_summary import claim_preview, useful_observations, TITLES
from backend.db import make_sessions
from backend.models import AuditEvent, ConversationFlow, Message, RequestCase
from backend.tests.test_api import setup, login
from backend.tests.test_workflow_chat import models, message


def ready(client, control, locale='es', cid=None):
    control.update(family='problem', intent='unrecognized-charge')
    body = message(locale=locale, message={'es':'No reconozco este cobro', 'en':'I do not recognize this charge', 'pt':'Não reconheço esta cobrança'}[locale], transactionId='TX-1002')
    if cid: body['conversationId'] = cid
    response = client.post('/api/assistant/flow', json=body)
    assert response.status_code == 200, response.text
    assert response.json()['flow']['canRegister']
    return response.json()['conversation']['id']


def preview(client, cid, locale='es'):
    response = client.get(f'/api/conversations/{cid}/claim-preview', params={'locale':locale})
    assert response.status_code == 200, response.text
    return response.json()


def payload(value, locale='es', **kwargs):
    return {'confirmed':True, 'details':value['summary'], 'previewToken':value['previewToken'],
            'locale':locale, 'requestKey':str(uuid4()), **kwargs}


def records(engine):
    with make_sessions(engine)() as db:
        return {'counts':{model.__tablename__: db.scalar(select(func.count()).select_from(model))
                          for model in (RequestCase, AuditEvent, Message)},
                'flows':{r.conversation_id: (r.request_id, copy.deepcopy(r.state)) for r in db.scalars(select(ConversationFlow))}}


@pytest.mark.parametrize('locale', ['es','en','pt'])
def test_query_then_problem_summary_excludes_chat_and_registration_persists_once(setup, models, locale):
    app, engine = setup
    client, _ = login(app)
    calls, control = models
    control.update(family='query', intent='account-activity')
    question = {'es':'¿Cuál fue mi último pago?', 'en':'What was my last payment?', 'pt':'Qual foi meu último pagamento?'}[locale]
    first = client.post('/api/assistant/flow', json=message(locale=locale, message=question)).json()
    cid = ready(client, control, locale, first['conversation']['id'])
    assent = {'es':'Sí, es este', 'en':'Yes, this one', 'pt':'Sim, é este'}[locale]
    third = client.post('/api/assistant/flow', json=message(locale=locale, conversationId=cid, message=assent))
    assert third.status_code == 200
    count = len(calls)
    before = client.get('/api/bootstrap').json()
    value = preview(client, cid, locale)
    findings = third.json()['text']
    assert findings.startswith({'es':'Esto es lo que encontré:', 'en':'Here is what I found:', 'pt':'Veja o que encontrei:'}[locale])
    assert 'TX-1002' in findings and 'Stream Plus' in findings
    assert value['summary'].split('\n\n')[1] in findings
    assert question not in findings and assent not in findings
    assert not third.json()['flow']['requestId']
    assert 'Stream Plus' not in json.dumps(calls)
    assert question not in value['summary'] and assent not in value['summary']
    assert 'TX-1002' in value['summary'] and 'Stream Plus' in value['summary']
    assert value['summary'].startswith(TITLES['unrecognized-charge'][('es','en','pt').index(locale)])
    assert value['intent']=='unrecognized-charge' and value['transactionId']=='TX-1002'
    edited = value['summary'] + '\n\n' + {'es':'Solicito que revisen este movimiento.', 'en':'Please review this transaction.', 'pt':'Peço a análise desta movimentação.'}[locale]
    body = payload(value, locale, details=edited)
    endpoint = f'/api/conversations/{cid}/claim'
    result = client.post(endpoint, json=body)
    assert result.status_code == 200, result.text
    result = result.json()
    assert result['summary']==edited and result['id'] in result['message']['text']
    assert result['nextStep'] in result['message']['text']
    assert result['message']['role']=='assistant' and result['message']['locale']==locale
    assert result['flow']['state']=='registered' and not result['flow']['canRegister']
    state = records(engine)
    assert client.post(endpoint, json=body).json()==result
    assert records(engine)==state
    assert client.post(endpoint, json={**body,'details':edited+' changed'}).status_code==409
    assert client.get(f'/api/conversations/{cid}/claim-preview').status_code==409
    history = client.get(f'/api/conversations/{cid}').json()['messages']
    assert sum(m['id']==result['message']['id'] for m in history)==1
    with make_sessions(engine)() as db:
        assert db.get(RequestCase,result['id']).details==edited
        row = db.get(ConversationFlow,cid)
        assert not any(result['id'] in m['content'] or 'Stream Plus' in m['content'] for m in row.state['messages'])
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.conversation_id==cid, AuditEvent.action=='created'))==1
    after = client.get('/api/bootstrap').json()
    assert before['products']==after['products'] and before['transactions']==after['transactions']
    assert len(calls)==count


def test_preview_and_registration_require_owner_session_role_and_ready_flow(setup,models):
    app, _ = setup
    client, _ = login(app)
    other, _ = login(app,'mateo')
    admin, _ = login(app,'nora')
    _, control = models
    waiting = client.post('/api/assistant/flow',json=message(transactionId='TX-1002')).json()['conversation']['id']
    assert client.get(f'/api/conversations/{waiting}/claim-preview').status_code==409
    assert client.post(f'/api/conversations/{waiting}/claim',json={'confirmed':True,'details':'Revisar el cobro','requestKey':str(uuid4())}).status_code==409
    cid = ready(client,control)
    value = preview(client,cid)
    for who, status in [(other,404),(admin,403),(TestClient(app),401)]:
        assert who.get(f'/api/conversations/{cid}/claim-preview').status_code==status
    assert other.post(f'/api/conversations/{cid}/claim',json=payload(value)).status_code==404
    assert admin.post(f'/api/conversations/{cid}/claim',json=payload(value)).status_code==403
    assert client.post(f'/api/conversations/{cid}/claim',json={**payload(value),'confirmed':False}).status_code==422
    assert client.get(f'/api/conversations/{cid}/claim-preview?locale=xx').status_code==422


def test_preview_token_rejects_edited_conversation_and_reused_key(setup,models):
    app, _ = setup
    client, _ = login(app)
    _, control = models
    cid = ready(client,control)
    old = preview(client,cid)
    client.post('/api/assistant/flow',json=message(conversationId=cid,message='También necesito que revisen este detalle'))
    assert client.post(f'/api/conversations/{cid}/claim',json=payload(old)).status_code==409
    fresh = preview(client,cid)
    assert fresh['previewToken'] != old['previewToken']
    result = client.post(f'/api/conversations/{cid}/claim',json=payload(fresh))
    assert result.status_code==200


@pytest.mark.parametrize('failure_at',['flush','commit'])
def test_claim_failure_rolls_back_case_message_audit_and_cache(setup,models,monkeypatch,failure_at):
    app, engine = setup
    client, _ = login(app)
    _, control = models
    cid = ready(client,control)
    body = payload(preview(client,cid))
    before = records(engine)
    original = getattr(Session, failure_at)
    def fail(self,*args,**kwargs):
        if failure_at=='commit' or any(isinstance(row,Message) and row.conversation_id==cid for row in self.new):
            raise RuntimeError('controlled claim failure')
        return original(self,*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Session,failure_at,fail)
        with pytest.raises(RuntimeError,match='controlled claim failure'):
            client.post(f'/api/conversations/{cid}/claim',json=body)
    assert records(engine)==before
    result = client.post(f'/api/conversations/{cid}/claim',json=body)
    assert result.status_code==200,result.text
    assert client.post(f'/api/conversations/{cid}/claim',json=body).json()==result.json()


def test_existing_transaction_claim_links_without_overwriting_original_summary(setup,models):
    app, engine = setup
    client, _ = login(app)
    _, control = models
    first = ready(client,control)
    result = client.post(f'/api/conversations/{first}/claim',json=payload(preview(client,first))).json()
    second = ready(client,control)
    linked = client.post(f'/api/conversations/{second}/claim',json=payload(preview(client,second),details='Otro relato para el mismo movimiento')).json()
    assert linked['id']==result['id'] and linked['summary']=='Otro relato para el mismo movimiento'
    assert 'vinculada' in linked['message']['text']
    with make_sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(RequestCase).where(RequestCase.transaction_id=='TX-1002'))==1
        assert db.get(RequestCase,result['id']).details==result['summary']


def test_observations_use_current_case_grounded_quotes_not_prior_query_assent_or_model_value():
    state = {'messages':[{'role':'user','content':'¿Cuál fue mi último pago?'},
                         {'role':'assistant','content':'Saldo bancario privado'},
                         {'role':'user','content':'La app se cierra al abrir. Reinicié el teléfono.'},
                         {'role':'user','content':'Sí, es este'},
                         {'role':'user','content':'Después reinstalé y sigue igual.'}],
             'record':{'graph':{'nodes':[{'id':'intake','kind':'intake'}]}},
             'node_inputs':{'intake':{'messages':[{'role':'user','content':'old'},{'role':'assistant','content':'old'},{'role':'user','content':'current'}]}},
             'context':{'observations':[
                 {'field':'location','quote':'¿Cuál fue mi último pago?','message_index':0},
                 {'field':'symptom','quote':'Saldo bancario privado','message_index':1},
                 {'field':'symptom','quote':'La app se cierra al abrir.','value':'Fraude confirmado','message_index':2},
                 {'field':'attempts','quote':'Reinicié el teléfono.','message_index':2},
                 {'field':'location','quote':'Sí, es este','message_index':3},
                 {'field':'attempts','quote':'Después reinstalé y sigue igual.','message_index':4},
                 {'field':'symptom','quote':'dato inventado','message_index':4}]}}
    assert useful_observations(state)=={'symptom':'La app se cierra al abrir.','attempts':'Después reinstalé y sigue igual.'}


@pytest.mark.parametrize('locale',['es','en','pt'])
@pytest.mark.parametrize('intent',list(TITLES))
def test_contract_summary_copy_has_equal_language_coverage(locale,intent):
    conv=SimpleNamespace(id='conversation',user_id='owner',transaction_id=None)
    state={'context':{'intent':intent},'bank_binding':{},'version':1,'run_id':'run'}
    value=claim_preview(None,conv,state,locale)
    assert value['summary']==TITLES[intent][('es','en','pt').index(locale)]
    assert len(value['previewToken'])==64 and value['nextStep']
