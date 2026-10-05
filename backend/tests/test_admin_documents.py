from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.db import make_sessions
from backend.models import AuditEvent
from backend.tests.test_api import setup, login, payload
from backend.tests.test_query_documents import query, body
from backend.tests.test_workflow_chat import models


def test_admin_document_access_requires_case_owner_relation_and_is_read_only(setup, models):
    app, engine = setup
    customer, _ = login(app)
    other, _ = login(app, 'mateo')
    admin, _ = login(app, 'nora')
    _, control = models
    case = customer.post('/api/requests', json=payload()).json()['id']
    cid = query(customer, control)
    doc = customer.post(f'/api/conversations/{cid}/documents', json=body(
        'claims_summary', scope='selected', requestId=case)).json()['document']
    unrelated_cid = query(customer, control)
    unrelated = customer.post(f'/api/conversations/{unrelated_cid}/documents', json=body('products_summary')).json()['document']
    base = f'/api/admin/users/andrea/requests/{case}/documents'
    assert TestClient(app).get(base).status_code == 401
    assert customer.get(base).status_code == other.get(base).status_code == 403
    assert admin.get(base.replace('/andrea/', '/mateo/')).status_code == 404
    assert admin.get(base + '?offset=-1').status_code == 422
    before = customer.get('/api/bootstrap').json()
    listed = admin.get(base).json()
    assert [d['id'] for d in listed['documents']] == [doc['id']]
    assert listed['documents'][0]['relation'] == 'request'
    assert listed['nextOffset'] is None
    assert admin.get(base + '/' + unrelated['id']).status_code == 404
    assert customer.get(base + '/' + doc['id']).status_code == 403
    assert admin.get(base.replace('/andrea/', '/mateo/') + '/' + doc['id']).status_code == 404
    expected = customer.get('/api/documents/' + doc['id']).content
    for download in (False, True):
        result = admin.get(base + '/' + doc['id'] + '?download=' + str(download).lower())
        assert result.status_code == 200 and result.content == expected
        assert result.headers['cache-control'] == 'no-store'
        assert result.headers['x-content-type-options'] == 'nosniff'
        assert result.headers['content-disposition'].startswith('attachment' if download else 'inline')
    after = customer.get('/api/bootstrap').json()
    for key in ('products', 'transactions', 'requests'):
        assert after[key] == before[key]
    with make_sessions(engine)() as db:
        logs = db.scalars(select(AuditEvent).where(AuditEvent.action.like('case_document%'))).all()
        assert len(logs) == 3
        assert all((r.actor_id, r.user_id, r.request_id) == ('nora', 'andrea', case) for r in logs)
    assert admin.get(base.removesuffix('/documents') + '/trace').json()['documentCount'] == 1


def test_documents_from_related_conversation_are_labeled_and_paginate(setup, models):
    app, engine = setup
    customer, _ = login(app)
    other, _ = login(app, 'mateo')
    admin, _ = login(app, 'nora')
    _, control = models
    case = customer.post('/api/requests', json=payload()).json()['id']
    ids = []
    for _ in range(22):
        cid = query(customer, control)
        ids.append(customer.post(f'/api/conversations/{cid}/documents', json=body('products_summary')).json()['document']['id'])
        with make_sessions(engine)() as db:
            db.add(AuditEvent(id=str(uuid4()), user_id='andrea', actor_id='andrea', request_id=case,
                              conversation_id=cid, action='conversation_linked'))
            db.commit()
    other_cid = query(other, control)
    foreign = other.post(f'/api/conversations/{other_cid}/documents', json=body('products_summary')).json()['document']
    # An inconsistent historical audit link cannot grant access to another owner's PDF.
    with make_sessions(engine)() as db:
        db.add(AuditEvent(id=str(uuid4()), user_id='andrea', actor_id='andrea', request_id=case,
                          conversation_id=other_cid, action='conversation_linked'))
        db.commit()
    base = f'/api/admin/users/andrea/requests/{case}/documents'
    first = admin.get(base).json()
    second = admin.get(base + '?offset=20').json()
    assert len(first['documents']) == 20 and first['nextOffset'] == 20
    assert len(second['documents']) == 2 and second['nextOffset'] is None
    assert {d['id'] for d in first['documents'] + second['documents']} == set(ids)
    assert all(d['relation'] == 'conversation' for d in first['documents'])
    assert admin.get(base + '/' + foreign['id']).status_code == 404
    assert admin.get(base.removesuffix('/documents') + '/trace').json()['documentCount'] == 22
