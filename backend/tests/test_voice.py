import json
import queue
import time
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from backend.tests.test_api import setup,login
from backend.tests.test_workflow_chat import models,message
from backend.models import VoiceSession,Conversation,Message,Session
from backend.db import make_sessions
from backend.voice import TranscriptBuffer,safe_spoken_result
from backend.voice_provider import configuration


class Socket:
    def __init__(self):self.events=queue.Queue();self.sent=[]
    def send(self,raw):
        event=json.loads(raw);self.sent.append(event)
        if event['type']=='session.close':self.events.put({'type':'session.closed','usage':{'duration_seconds':2}})
    def recv(self,timeout):
        try:return json.dumps(self.events.get(timeout=timeout))
        except queue.Empty:raise TimeoutError from None
    def close(self):pass


class Provider:
    def __init__(self):self.socket=Socket();self.created=[];self.attached=[]
    def create(self,*args):self.created.append(args);return 'live_test','v=0\r\nanswer'
    def attach(self,identity):self.attached.append(identity);return self.socket


@pytest.fixture
def voice(setup,models,monkeypatch):
    app,engine=setup;provider=Provider();app.state.voice.provider=provider
    monkeypatch.setenv('BANK_VOICE_ENABLED','true');monkeypatch.setenv('LLM_API_KEY','not-a-real-key')
    yield app,engine,provider
    app.state.voice.shutdown()


def start_body(**kw):return {'requestKey':str(uuid4()),'sdp':'v=0\r\no=local','locale':'es',**kw}


def wait_until(predicate):
    end=time.monotonic()+8
    while time.monotonic()<end:
        value=predicate()
        if value:return value
        time.sleep(.05)
    raise AssertionError('voice event not completed')


def test_disabled_never_creates_provider_session(setup,monkeypatch):
    app,engine=setup;client,_=login(app);fake=Provider();app.state.voice.provider=fake
    monkeypatch.delenv('BANK_VOICE_ENABLED',raising=False)
    assert not client.get('/api/voice/capabilities').json()['enabled']
    assert client.post('/api/voice/sessions',json=start_body()).status_code==503
    assert fake.created==[]
    with make_sessions(engine)() as db:assert db.scalar(select(func.count()).select_from(VoiceSession))==0


def test_ownership_csrf_validation_and_single_active_session(voice):
    app,engine,provider=voice;client,_=login(app);other,_=login(app,'mateo');admin,_=login(app,'nora')
    assert TestClient(app).post('/api/voice/sessions',json=start_body()).status_code in (401,403)
    assert admin.post('/api/voice/sessions',json=start_body()).status_code==403
    assert client.post('/api/voice/sessions',json=start_body(transactionId='TX-2001')).status_code==404
    assert client.post('/api/voice/sessions',json=start_body(requestId='absent')).status_code==404
    assert client.post('/api/voice/sessions',json=start_body(voice='unknown')).status_code==422
    body=start_body();r=client.post('/api/voice/sessions',json=body);assert r.status_code==200,r.text
    identity=r.json()['id']
    assert client.get('/api/voice/capabilities').json()['pendingSessionId']==identity
    assert other.get('/api/voice/capabilities').json()['pendingSessionId'] is None
    assert client.post('/api/voice/sessions',json=body).status_code==409
    assert client.post('/api/voice/sessions',json=start_body()).status_code==409
    assert other.post(f'/api/voice/sessions/{identity}/close',json={}).status_code==404
    assert other.post(f'/api/voice/sessions/{identity}/heartbeat',json={}).status_code==404
    assert client.post(f'/api/voice/sessions/{identity}/close',json={},headers={'X-CSRF-Token':'bad'}).status_code==403
    assert len(provider.created)==1
    assert 'not-a-real-key' not in r.text and 'live_test' not in r.text
    assert client.post(f'/api/voice/sessions/{identity}/close',json={}).json()['remoteClosed']
    assert client.get('/api/voice/capabilities').json()['pendingSessionId'] is None


@pytest.mark.parametrize('locale',['es','en','pt'])
def test_voice_continues_text_case_once_with_safe_results_and_no_financial_effect(voice,models,locale):
    app,engine,provider=voice;client,_=login(app);calls,control=models
    before=client.get('/api/bootstrap').json()
    written=client.post('/api/assistant/flow',json=message(locale=locale,transactionId='TX-1002')).json()
    cid=written['conversation']['id'];assert written['flow']['missing_fields']==['difference']
    started=client.post('/api/voice/sessions',json=start_body(locale=locale,conversationId=cid,transactionId='TX-1002'))
    assert started.status_code==200,started.text
    identity=started.json()['id'];sock=provider.socket
    for event in [
        {'type':'session.input_transcript.delta','event_id':'a','delta':'Esperaba ','start_ms':0,'end_ms':100},
        {'type':'session.input_transcript.delta','event_id':'b','delta':'100 MXN','start_ms':100,'end_ms':200},
        {'type':'session.delegation.created','delegation':{'id':'d1','target':'client'},'offset_ms':200},
        {'type':'session.delegation.created','delegation':{'id':'d1','target':'client'},'offset_ms':200}]:sock.events.put(event)
    result=wait_until(lambda:(v if (v:=client.post(f'/api/voice/sessions/{identity}/heartbeat',json={}).json()).get('revision')==1 else None))
    assert result['reply']['conversation']['id']==cid and result['reply']['flow']['canRegister']
    assert [c[0] for c in calls]==['triage','jev','llm','llm']
    wait_until(lambda:any(e['type']=='session.commentary.append' for e in sock.sent))
    sent=json.dumps(sock.sent);assert 'TX-1002' not in sent and 'Stream Plus' not in sent and '100 MXN' not in sent
    with make_sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(Message).where(Message.conversation_id==cid))==4
    after=client.get('/api/bootstrap').json()
    for key in ('products','transactions','requests'):assert after[key]==before[key]
    assert client.post(f'/api/voice/sessions/{identity}/close',json={}).status_code==200
    wait_until(lambda:client.post(f'/api/voice/sessions/{identity}/heartbeat',json={}).json()['remoteClosed'])
    # Written continuation shares the same contract and remains available.
    resumed=client.post('/api/assistant/flow',json=message(conversationId=cid,message='Sigo con el mismo caso')).json()
    assert resumed['conversation']['id']==cid and resumed['flow']['contract']==written['flow']['contract']


def test_logout_and_lease_expiry_close_remote_audio(voice):
    app,engine,provider=voice;client,_=login(app)
    started=client.post('/api/voice/sessions',json=start_body()).json();identity=started['id']
    client.post('/api/auth/logout',json={})
    wait_until(lambda:any(e['type']=='session.close' for e in provider.socket.sent))
    with make_sessions(engine)() as db:assert db.get(VoiceSession,identity).state.get('reply') is None


def test_heartbeat_deadline_and_server_restart_do_not_create_second_call(voice):
    app,engine,provider=voice;client,_=login(app)
    identity=client.post('/api/voice/sessions',json=start_body()).json()['id']
    with make_sessions(engine)() as db:db.get(VoiceSession,identity).expires_at=0;db.commit()
    wait_until(lambda:any(e['type']=='session.close' for e in provider.socket.sent))
    app.state.voice.shutdown()
    with make_sessions(engine)() as db:db.get(VoiceSession,identity).status='active';db.commit()
    app.state.voice.recover()
    assert len(provider.created)==1 and len(provider.attached)==2


def test_fragment_order_deduplication_and_prompt_permissions():
    buffer=TranscriptBuffer()
    events=[{'event_id':'b','delta':'100 pesos','start_ms':20,'end_ms':30},{'event_id':'a','delta':'Esperaba ','start_ms':0,'end_ms':20}]
    for event in events+events:buffer.add(event)
    assert buffer.take(30)=='Esperaba 100 pesos' and buffer.take(30)==''
    config=configuration('es','marin')
    assert config['store'] is False and config['delegation']=={'type':'client'}
    assert config['client']['data_channel']['allowed_client_events']==['session.close']
    assert 'input' not in config
    for locale in ('es','en','pt'):
        assert 'SECRET' not in safe_spoken_result({'text':'SECRET','flow':{'reply':'SECRET','questions':['SECRET']}},locale)
        question=safe_spoken_result({'text':'SECRET','flow':{'missing_fields':['difference'],'questions':['SECRET']}},locale)
        assert 'SECRET' not in question and question!=safe_spoken_result({},locale)


def test_provider_failure_is_not_retried_automatically_and_known_session_is_closed(voice):
    app,engine,provider=voice;client,_=login(app)
    original=provider.attach;attempts=[]
    def fail_once(identity):
        attempts.append(identity)
        if len(attempts)==1:raise TimeoutError
        return original(identity)
    provider.attach=fail_once
    body=start_body();assert client.post('/api/voice/sessions',json=body).status_code==503
    assert len(provider.created)==1 and len(attempts)==2
    assert client.post('/api/voice/sessions',json=body).status_code==409
    with make_sessions(engine)() as db:
        row=db.scalar(select(VoiceSession));assert row.state['remote_closed'] and row.status=='closed'


def test_disabled_real_provider_has_no_network(monkeypatch):
    from backend.voice_provider import LiveProvider
    monkeypatch.delenv('BANK_VOICE_ENABLED',raising=False)
    with pytest.raises(RuntimeError):LiveProvider().create('v=0','es','marin')
    with pytest.raises(RuntimeError):LiveProvider().attach('live_test')


def test_transport_cleanup_failure_still_persists_remote_closure(voice):
    app,engine,provider=voice;client,_=login(app)
    identity=client.post('/api/voice/sessions',json=start_body()).json()['id']
    def broken_close():raise OSError('transport already gone')
    provider.socket.close=broken_close
    result=client.post(f'/api/voice/sessions/{identity}/close',json={})
    assert result.status_code==200 and result.json()['remoteClosed']
    assert result.json()['status']=='closed'
    assert client.get('/api/voice/capabilities').json()['pendingSessionId'] is None
