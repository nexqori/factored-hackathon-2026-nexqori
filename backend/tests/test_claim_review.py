from uuid import uuid4
import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from backend.db import make_sessions
from backend.models import AuditEvent, ClaimReview, Product, Refund, Transaction
from backend.tests.test_api import setup, login, payload
from backend.tests.test_operations import approve_payload, approve_case


def test_stage_order_role_confirmation_and_no_money_until_final_action(setup):
    app, engine = setup
    customer, _ = login(app); other, _ = login(app, 'mateo'); admin, _ = login(app, 'nora')
    case = customer.post('/api/requests', json=payload(transactionId='TX-1001')).json()['id']
    path = f'/api/admin/requests/{case}/stage'
    before = customer.get('/api/bootstrap').json()
    for actor in (customer, other):
        assert actor.post(path, json={'confirmed':True,'stage':'delivered'}).status_code == 403
    assert admin.post(path, json={'confirmed':False,'stage':'delivered'}).status_code == 422
    assert admin.post(path, json={'confirmed':True,'stage':'approved','note':'Evidence has been reviewed.'}).status_code == 409
    assert admin.post(path, json={'confirmed':True,'stage':'in_review'}).status_code == 409
    assert admin.post(f'/api/admin/requests/{case}/review',json={'confirmed':True}).status_code == 409
    for stage in ('delivered','in_review','approved'):
        body={'confirmed':True,'stage':stage,'note':'Reviewed the original charge and account.' if stage=='approved' else ''}
        assert admin.post(path,json=body).status_code == 200
        assert admin.post(path,json=body).status_code == 200
        trace=customer.get(f'/api/requests/{case}/trace').json()
        assert trace['request']['handling']['stage']==stage
        assert trace['outcome']=='claim_'+stage
        after=customer.get('/api/bootstrap').json()
        assert after['products']==before['products'] and after['transactions']==before['transactions']
    refund=admin.get(f'/api/admin/requests/{case}/refund').json()
    assert refund['claimApproved'] and refund['refund']['status']=='pending'
    assert refund['refund']['creditTransactionId'] is None
    url='/api/admin/refunds/'+refund['refund']['id']+'/decision'
    body=approve_payload()
    assert admin.post(url,json=body).status_code==200
    assert admin.post(url,json=body).status_code==200
    with make_sessions(engine)() as db:
        assert db.get(Product,'account-01').balance_minor==1845000+28650
        assert db.scalar(select(func.count()).select_from(Transaction).where(Transaction.category=='refund'))==1
        actions=db.scalars(select(AuditEvent.action).where(AuditEvent.request_id==case)).all()
        for action in ('claim_delivered','reviewed','claim_approved','refund_approved'):
            assert actions.count(action)==1
    assert other.get(f'/api/requests/{case}/trace').status_code==404


def test_direct_refund_cannot_bypass_case_approval(setup):
    from backend.tests.test_operations import make_refund
    app,engine=setup;customer,_=login(app);admin,_=login(app,'nora')
    case,_,refund=make_refund(customer)
    response=admin.post('/api/admin/refunds/'+refund['id']+'/decision',json=approve_payload())
    assert response.status_code==409 and response.json()['error']=='claim_approval_required'
    with make_sessions(engine)() as db:
        assert db.get(Product,'account-01').balance_minor==1845000
        assert db.get(Refund,refund['id']).status=='pending'


@pytest.mark.parametrize('transaction',['TX-1005','TX-1006'])
def test_pending_or_declined_complaint_approval_does_not_prepare_refund(setup,transaction):
    app,engine=setup;customer,_=login(app);admin,_=login(app,'nora')
    case=customer.post('/api/requests',json=payload(transactionId=transaction,reason='payment')).json()['id']
    approve_case(admin,case)
    state=admin.get(f'/api/admin/requests/{case}/refund').json()
    assert state['claimApproved'] and state['refund'] is None and not state['eligible']
    with make_sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(Transaction).where(Transaction.category=='refund'))==0


def test_application_cannot_enter_claim_stages_and_owner_fk_is_enforced(setup):
    from backend.models import RequestCase
    app,engine=setup;customer,_=login(app);admin,_=login(app,'nora')
    case=customer.post('/api/requests',json=payload(transactionId='TX-1001')).json()['id']
    with make_sessions(engine)() as db:
        db.get(RequestCase,case).catalog_service_id='account-balance';db.commit()
    assert admin.post(f'/api/admin/requests/{case}/stage',json={'confirmed':True,'stage':'delivered'}).status_code==409
    with make_sessions(engine)() as db:
        db.add(ClaimReview(request_id=case,user_id='mateo',stage='delivered',actor_id='nora'))
        with pytest.raises(IntegrityError):db.commit()


def test_handoff_remains_visible_after_delivery_until_review_starts(setup):
    app,_=setup;customer,_=login(app);admin,_=login(app,'nora')
    case=customer.post('/api/requests',json=payload(transactionId='TX-1001')).json()['id']
    path=f'/api/admin/requests/{case}/stage'
    assert admin.post(path,json={'confirmed':True,'stage':'delivered'}).status_code==200
    assert customer.post(f'/api/requests/{case}/handoff',json={'confirmed':True}).status_code==200
    trace=customer.get(f'/api/requests/{case}/trace').json()
    assert trace['outcome']=='handed_off' and trace['request']['status']=='handed_off'
    assert admin.post(path,json={'confirmed':True,'stage':'in_review'}).status_code==200
    assert customer.get(f'/api/requests/{case}/trace').json()['outcome']=='claim_in_review'
