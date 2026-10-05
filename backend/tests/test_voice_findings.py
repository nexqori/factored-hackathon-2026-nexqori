import json
from uuid import uuid4
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.db import make_sessions
from backend.models import ServiceAgreement, Transaction
from backend.tests.test_api import setup, login, ORIGIN
from backend.tests.test_workflow_chat import models, message
from backend.tests.test_service_agreements import prepared
from backend.tests.test_voice import voice, start_body, wait_until
from backend.voice_summary import presentation


@pytest.mark.parametrize('locale',['es','en','pt'])
def test_recorded_plan_summary_chart_and_privacy(setup,locale):
    _,engine=setup;pack,person,scenario=prepared(engine);txid=scenario['transactionIds'][1]
    reply={'text':'UNTRUSTED_RESPONSE', 'conversation':{'transactionId':txid},'flow':{'canRegister':True,'missing_fields':[]}}
    with make_sessions(engine)() as db:
        result=presentation(db,person['userId'],reply,locale)
        assert result['comparison']=={'basis':'agreement','baselineMinor':29900,'currentMinor':45900,'differenceMinor':16000,'currency':'MXN','count':5,'verdict':'above-base'}
        speech=result['summary']
        for value in ('459.00','299.00','160.00','supervisor'):assert value in speech
        for value in (txid,'UNTRUSTED_RESPONSE','Empresa Telefónica',person['email']):assert value not in speech
        assert len(speech.split())<120
        with pytest.raises(HTTPException) as err:presentation(db,'mateo',reply,locale)
        assert err.value.status_code==404
        terms=db.scalar(select(ServiceAgreement).where(ServiceAgreement.user_id==person['userId']))
        terms.monthly_minor=45900;db.flush()
        assert presentation(db,person['userId'],reply,locale)['comparison']['verdict']=='within-base'


def test_insufficient_history_does_not_claim_customer_wrong(setup):
    app,engine=setup;client,_=login(app)
    with make_sessions(engine)() as db:
        result=presentation(db,'andrea',{'conversation':{'transactionId':'TX-1002'},'flow':{}},'es')
        assert result['comparison'] is None
        assert 'No tengo suficientes' in result['summary']


@pytest.mark.parametrize('fallback',['needs-clarification','out-of-scope'])
def test_subtype_clarification_still_searches_payment_clues(setup,models,fallback):
    app,_=setup;client,_=login(app);calls,control=models;control['intent']=fallback
    reply=client.post('/api/assistant/flow',json=message(message='Tengo un problema con el pago de 189 MXN')).json()
    assert reply['flow']['suggestedTransaction']['id']=='TX-1002'
    assert reply['navigation']['destination']=='movements'
    assert not reply['conversation']['transactionId']
    assert not reply['flow']['canRegister']


@pytest.mark.parametrize('locale',['es','en','pt'])
def test_voice_confirmed_plan_case_announced_once_and_pending_not_refunded(voice,models,locale):
    app,engine,provider=voice;pack,person,scenario=prepared(engine)
    client=TestClient(app)
    logged=client.post('/api/auth/login',headers={'Origin':ORIGIN},json={'identifier':person['email'],'password':pack['passwords']['cargo']}).json()
    client.headers.update({'Origin':ORIGIN,'X-CSRF-Token':logged['csrfToken']})
    txid=scenario['transactionIds'][1]
    before=client.get('/api/bootstrap').json()
    started=client.post('/api/voice/sessions',json=start_body(locale=locale,transactionId=txid)).json()
    identity=started['id'];cid=started['conversationId']
    provider.socket.events.put({'type':'session.input_transcript.delta','event_id':'input','delta':'Me cobraron de más en el teléfono','start_ms':0,'end_ms':100})
    provider.socket.events.put({'type':'session.delegation.created','delegation':{'id':'find','target':'client'},'offset_ms':100})
    result=wait_until(lambda:(v if (v:=client.post(f'/api/voice/sessions/{identity}/heartbeat',json={}).json()).get('revision')==1 else None))
    assert result['reply']['flow']['canRegister'], result['reply']
    assert result['reply']['voiceSummary']['comparison']['differenceMinor']==16000
    wait_until(lambda:any('160.00' in e.get('content','') for e in provider.socket.sent))
    preview=client.get(f'/api/conversations/{cid}/claim-preview?locale={locale}').json()
    body={'confirmed':True,'details':preview['summary'],'locale':locale,'previewToken':preview['previewToken'],'requestKey':str(uuid4())}
    claim=client.post(f'/api/conversations/{cid}/claim',json=body)
    assert claim.status_code==200,claim.text
    rid=claim.json()['id']
    assert client.post(f'/api/conversations/{cid}/claim',json=body).json()['id']==rid
    wait_until(lambda:any(rid in e.get('content','') for e in provider.socket.sent))
    assert len([e for e in provider.socket.sent if rid in e.get('content','')])==1
    assert app.state.voice.registration_notice(identity) is None
    trace=client.get(f'/api/requests/{rid}/trace').json()
    assert trace['request']['status']=='received'
    after=client.get('/api/bootstrap').json()
    for key in ('products','transactions'):assert after[key]==before[key]
    client.post(f'/api/voice/sessions/{identity}/close',json={})


def test_specific_overcharge_reclassifies_vague_payment_without_losing_selected_record(setup,models):
    app,_=setup;client,_=login(app);calls,control=models
    control['intent']='payment-status'
    first=client.post('/api/assistant/flow',json=message(message='Revisa el estado del pago',transactionId='TX-1002')).json()
    cid=first['conversation']['id'];control['intent']='incorrect-charge'
    revised=client.post('/api/assistant/flow',json=message(conversationId=cid,message='Me cobraron de más; esperaba 100 MXN')).json()
    assert revised['flow']['jev']['intent']=='incorrect-charge'
    assert revised['conversation']['transactionId']=='TX-1002' and revised['flow']['canRegister']
    assert revised['conversation']['id']==cid
    assert 'Stream Plus' not in json.dumps(calls)
