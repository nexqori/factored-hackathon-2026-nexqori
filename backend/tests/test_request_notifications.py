import pytest
from fastapi import HTTPException
from sqlalchemy import select
from backend.db import make_sessions
from backend.models import RequestCase,AuditEvent
from backend.tests.test_api import setup,login,payload
from backend.email_templates import request_message


@pytest.mark.parametrize('failure',[False,True])
def test_registration_receipt_after_commit_and_once(setup,monkeypatch,failure):
    app,engine=setup;client,_=login(app);sent=[]
    def deliver(recipient,subject,plain,html):
        with make_sessions(engine)() as db:
            assert any(r.id in plain for r in db.scalars(select(RequestCase)))
        sent.append((recipient,plain))
        if failure:raise HTTPException(503,'mail_unavailable')
    monkeypatch.setattr('backend.notifications.send_email',deliver)
    body=payload(transactionId='TX-1001')
    response=client.post('/api/requests',json=body)
    assert response.status_code==201
    assert client.post('/api/requests',json=body).json()['id']==response.json()['id']
    assert len(sent)==1 and sent[0][0]=='andrea@nexqori.com'
    with make_sessions(engine)() as db:
        action='notification_request_failed' if failure else 'notification_request_accepted'
        assert db.scalar(select(AuditEvent).where(AuditEvent.request_id==response.json()['id'],AuditEvent.action==action))


@pytest.mark.parametrize('locale',['es','en','pt'])
def test_request_receipt_has_no_false_refund_claim(locale):
    subject,plain,html=request_message(locale,'<case>',True)
    assert '<case>' in plain and '&lt;case&gt;' in html
    assert '<case>' not in html and '#9A4B32' in html
    assert any(x in plain for x in ('pendiente de revisión','awaiting review','aguardando análise'))
