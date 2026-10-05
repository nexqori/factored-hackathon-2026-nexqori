import time
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, func

from backend.db import make_sessions
from backend.models import AuditEvent, CardProfile, EmailChallenge, NotificationPreference, Product
from backend.security import verify
from backend.tests.test_api import setup, login, PASSWORDS


@pytest.fixture
def delivery(setup, monkeypatch):
    from backend import notifications
    monkeypatch.setenv('BANK_CARD_BLOCK_EMAIL_REQUIRED', 'true')
    monkeypatch.setenv('MAIL_SMTP_HOST', 'controlled-test')
    monkeypatch.setenv('MAIL_FROM', 'sender@example.com')
    sent = []
    monkeypatch.setattr(notifications, 'send_code', lambda email, code, purpose, locale, last4: sent.append((email, code, purpose, locale, last4)))
    return sent


def lapse(engine, ident, seconds=61):
    with make_sessions(engine)() as db:
        db.get(EmailChallenge, ident).created_at -= seconds
        db.commit()


def enroll(client, sent, email='notifications@example.com'):
    r = client.post('/api/profile/notifications/code', json={'email': email, 'password': PASSWORDS[0]})
    assert r.status_code == 200, r.text
    value = r.json()
    assert sent[-1][1] not in r.text
    body = {'challengeId': value['challengeId'], 'code': sent[-1][1]}
    assert client.post('/api/profile/notifications/verify', json=body).json() == {'email': email, 'verified': True}
    return value, body


def test_email_verified_separately_from_login_and_no_secret_in_audit(setup, delivery):
    app, engine = setup
    client, _ = login(app)
    other, _ = login(app, 'mateo')
    admin, _ = login(app, 'nora')
    initial = client.get('/api/profile/notifications').json()
    assert initial['suggestedEmail'] == 'andrea@nexqori.com'
    assert initial['email'] is None and initial['verified'] is False
    assert admin.get('/api/profile/notifications').status_code == 403
    assert client.post('/api/profile/notifications/code', json={'email':'x@example.com\nBCC:y@example.com','password':PASSWORDS[0]}).status_code == 422
    assert client.post('/api/profile/notifications/code', json={'email':'x@example.com','password':'wrong'}).status_code == 403
    response = client.post('/api/profile/notifications/code', json={'email':'other@example.com','password':PASSWORDS[0]})
    value = response.json()
    body = {'challengeId':value['challengeId'], 'code':delivery[-1][1]}
    assert client.get('/api/profile/notifications').json()['email'] is None
    assert other.post('/api/profile/notifications/verify', json=body).status_code == 403
    second_session, _ = login(app)
    assert second_session.post('/api/profile/notifications/verify', json=body).status_code == 403
    assert client.post('/api/profile/notifications/verify', json=body, headers={'X-CSRF-Token':'wrong'}).status_code == 403
    assert client.post('/api/profile/notifications/verify', json=body).status_code == 200
    assert client.post('/api/profile/notifications/verify', json=body).status_code == 403
    assert client.get('/api/session').json()['user']['email'] == 'andrea@nexqori.com'
    with make_sessions(engine)() as db:
        row = db.get(EmailChallenge, value['challengeId'])
        assert row.code_hash != body['code'] and verify(body['code'], row.code_hash)
        assert row.consumed and db.get(NotificationPreference,'andrea').email == 'other@example.com'
    assert body['code'] not in admin.get('/api/admin/overview').text


def test_block_requires_own_session_card_code_and_changes_card_only_once(setup, delivery):
    app, engine = setup
    client, _ = login(app)
    block = {'confirmed':True, 'password':PASSWORDS[0], 'requestKey':str(uuid4())}
    path = '/api/cards/card-01/block'
    assert client.post(path, json=block).json()['error'] == 'notification_email_required'
    enrolled, email_body = enroll(client, delivery)
    assert client.post(path, json=block).json()['error'] == 'email_code_invalid'
    assert client.post(path, json={**block,**email_body}).status_code == 403
    assert client.post('/api/cards/card-01/block-code', json={'password':PASSWORDS[0]}).status_code == 429
    lapse(engine, enrolled['challengeId'])
    issued = client.post('/api/cards/card-01/block-code', json={'password':PASSWORDS[0]}).json()
    last4 = next(c['last4'] for c in client.get('/api/cards').json()['cards'] if c['id'] == 'card-01')
    assert delivery[-1][0] == 'notifications@example.com' and delivery[-1][2] == 'card_block' and delivery[-1][4] == last4
    body = {**block, 'challengeId':issued['challengeId'], 'code':delivery[-1][1]}
    other, _ = login(app,'mateo')
    assert other.post(path,json=body).status_code == 404
    second, _ = login(app)
    assert second.post(path,json=body).status_code == 403
    assert client.post(path,json={**body,'confirmed':False}).status_code == 422
    before = client.get('/api/bootstrap').json()
    assert client.post(path,json=body).json()['status'] == 'blocked'
    assert client.post(path,json=body).status_code == 200
    after = client.get('/api/bootstrap').json()
    assert after['transactions'] == before['transactions'] and after['requests'] == before['requests']
    with make_sessions(engine)() as db:
        assert db.get(EmailChallenge, issued['challengeId']).consumed
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action=='card_blocked')) == 1


def test_attempt_limit_expiry_resend_and_old_code_invalidation(setup, delivery):
    app, engine = setup
    client, _ = login(app)
    start = lambda: client.post('/api/profile/notifications/code',json={'email':'x@example.com','password':PASSWORDS[0]})
    first = start().json()
    wrong = str((int(delivery[-1][1])+1)%1000000).zfill(6)
    for _ in range(5):
        assert client.post('/api/profile/notifications/verify',json={'challengeId':first['challengeId'],'code':wrong}).status_code == 403
    assert client.post('/api/profile/notifications/verify',json={'challengeId':first['challengeId'],'code':delivery[-1][1]}).status_code == 403
    assert start().status_code == 429
    lapse(engine, first['challengeId'])
    second = start().json()
    with make_sessions(engine)() as db:
        assert db.get(EmailChallenge, first['challengeId']).consumed
        row = db.get(EmailChallenge, second['challengeId']); row.expires_at=int(time.time())-1; db.commit()
    assert client.post('/api/profile/notifications/verify',json={'challengeId':second['challengeId'],'code':delivery[-1][1]}).status_code == 403
    assert client.get('/api/profile/notifications').json()['email'] is None


def test_failed_delivery_never_activates_an_email_or_code(setup, delivery, monkeypatch):
    from backend import notifications
    app, engine = setup
    client, _ = login(app)
    def fail(*args): raise HTTPException(503,'mail_unavailable')
    monkeypatch.setattr(notifications,'send_code',fail)
    assert client.post('/api/profile/notifications/code',json={'email':'x@example.com','password':PASSWORDS[0]}).status_code == 503
    with make_sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(EmailChallenge)) == 0
        assert db.get(NotificationPreference,'andrea') is None
        assert db.get(CardProfile,'card-01').status == 'active'


def test_code_cannot_block_another_card_and_email_change_revokes_pending_code(setup, delivery):
    app, engine = setup
    client, _ = login(app)
    enrolled, _ = enroll(client, delivery)
    lapse(engine, enrolled['challengeId'])
    with make_sessions(engine)() as db:
        db.add(Product(id='second-card', user_id='andrea', type='card', last4='5511'))
        db.flush()
        db.add(CardProfile(product_id='second-card', user_id='andrea', provider_ref='second-private-card',
                           expiry_month=12, expiry_year=2030, settlement_product_id='account-01'))
        db.commit()
    issued = client.post('/api/cards/card-01/block-code', json={'password':PASSWORDS[0]}).json()
    block = {'confirmed':True,'requestKey':str(uuid4()),'password':PASSWORDS[0],
             'challengeId':issued['challengeId'],'code':delivery[-1][1]}
    assert client.post('/api/cards/second-card/block',json=block).status_code == 403
    lapse(engine, issued['challengeId'])
    enroll(client, delivery, 'changed@example.com')
    assert client.post('/api/cards/card-01/block',json=block).status_code == 403
    with make_sessions(engine)() as db:
        assert db.get(CardProfile,'card-01').status == db.get(CardProfile,'second-card').status == 'active'


def test_smtp_uses_tls_auth_and_correct_recipient_without_exposing_failure(monkeypatch):
    from backend import notifications
    monkeypatch.setenv('MAIL_SMTP_HOST','smtp.gmail.com')
    monkeypatch.setenv('MAIL_SMTP_USER','sender@example.com')
    monkeypatch.setenv('MAIL_SMTP_PASSWORD','private-test-password')
    monkeypatch.delenv('MAIL_FROM',raising=False)
    monkeypatch.setenv('MAIL_SMTP_SECURITY','starttls')
    steps = []
    class SMTP:
        def __init__(self,host,port,timeout): assert (host,port,timeout)==('smtp.gmail.com',587,10)
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def starttls(self,context): steps.append('tls'); assert context.check_hostname
        def login(self,user,password): steps.append('login'); assert user=='sender@example.com' and password=='private-test-password'
        def send_message(self,message):
            steps.append('send')
            assert message['To']=='recipient@example.net' and str(message['From'])=='Nexqori <sender@example.com>'
            assert '123456' in message.get_body(preferencelist=('plain',)).get_content() and '5511' in message.get_body(preferencelist=('plain',)).get_content()
            return {}
    monkeypatch.setattr(notifications.smtplib,'SMTP',SMTP)
    notifications.send_code('recipient@example.net','123456','card_block','es','5511')
    assert steps==['tls','login','send']
    monkeypatch.setenv('MAIL_SMTP_SECURITY','plain')
    with pytest.raises(HTTPException) as error:
        notifications.send_code('recipient@example.net','123456','card_block','es','5511')
    assert error.value.detail == 'mail_unavailable'


@pytest.mark.parametrize('locale', ['es','en','pt'])
def test_branded_email_has_plain_alternative_and_escaped_html(monkeypatch,locale):
    from backend import notifications
    monkeypatch.setenv('MAIL_SMTP_HOST','smtp.gmail.com')
    monkeypatch.setenv('MAIL_SMTP_USER','sender@example.com')
    monkeypatch.setenv('MAIL_SMTP_PASSWORD','private-test-password')
    monkeypatch.delenv('MAIL_FROM',raising=False)
    monkeypatch.setenv('MAIL_SMTP_SECURITY','starttls')
    sent=[]
    class SMTP:
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def starttls(self,**kwargs):pass
        def login(self,*args):pass
        def send_message(self,message):sent.append(message);return {}
    monkeypatch.setattr(notifications.smtplib,'SMTP',SMTP)
    notifications.send_code('recipient@example.net','123456','card_block',locale,'<img src=x>')
    message=sent[0];plain=message.get_body(preferencelist=('plain',)).get_content()
    html=message.get_body(preferencelist=('html',)).get_content()
    assert message.get_content_type()=='multipart/alternative'
    assert '123456' in plain and '123456' in html
    assert 'nexqori.' in html and '#9A4B32' in html and '#F2D8C8' in html
    assert '<img src=x>' not in html and '&lt;img src=x&gt;' in html
    assert 'private-test-password' not in str(message)
