from datetime import datetime, timedelta, timezone
from uuid import uuid4
import json
import pytest
from sqlalchemy import select
from backend.tests.test_api import setup, login
from backend.tests.test_workflow_chat import models, message
from backend.models import Transaction, PhoneBill, BillPayment, ConversationFlow, AuditEvent
from backend.db import make_sessions
from backend.payment_history import compare_payments, comparison_text


def prepare(db, amounts=(29900,29900,29900)):
    current = db.get(Transaction, 'TX-1002')
    current.merchant = 'Historial de teléfono'
    current.amount_minor = -45900
    current.occurred_at = datetime(2026,10,3,12,tzinfo=timezone.utc)
    current.status = 'completed'
    rows=[]
    for i, amount in enumerate(amounts):
        row=Transaction(id='history-'+str(i), user_id=current.user_id, product_id=current.product_id,
            merchant=current.merchant, category=current.category, amount_minor=-amount, currency='MXN',
            occurred_at=current.occurred_at-timedelta(days=20*(i+1)), status='completed')
        db.add(row);rows.append(row)
    db.flush()
    return current, rows


@pytest.mark.parametrize('count',[0,1,2,3,6,7])
def test_window_sample_size_and_increase_are_explicit(setup,count):
    _,engine=setup
    with make_sessions(engine)() as db:
        current,rows=prepare(db,[29900]*count)
        value=compare_payments(db,current)
        assert value['count']==min(count,6)
        assert value['unusualIncrease']==(count>=3)
        if count:
            assert (value['averageMinor'],value['differenceMinor'],value['differencePercent'])==(29900,16000,'53.5')
            assert value['minMinor']==value['maxMinor']==29900
        for locale in ('es','en','pt'):assert comparison_text(value,locale)


def test_only_prior_completed_same_owner_product_merchant_debits_count(setup):
    _,engine=setup
    with make_sessions(engine)() as db:
        current,rows=prepare(db,[29900]*8)
        rows[1].status='pending';rows[2].status='declined';rows[3].amount_minor=29900
        rows[4].occurred_at=current.occurred_at+timedelta(days=1)
        rows[5].occurred_at=current.occurred_at-timedelta(days=181)
        rows[6].merchant='Otro comercio'
        other=db.get(Transaction,'TX-2001');rows[7].user_id=other.user_id;rows[7].product_id=other.product_id
        db.flush();value=compare_payments(db,current)
        assert [s['transactionId'] for s in value['samples']]==[rows[0].id]
        assert value['status']=='limited' and not value['unusualIncrease']


def attach_bill(db, tx, period, reference='5598765432', amount=None, service='phone-bill'):
    bill=PhoneBill(id='bill-'+tx.id,user_id=tx.user_id,service_id=service,reference=reference,
        period=period,due_date=period+'-28',amount_minor=amount or abs(tx.amount_minor),currency='MXN')
    db.add(bill);db.flush()
    db.add(BillPayment(id='pay-'+tx.id,user_id=tx.user_id,bill_id=bill.id,account_id=tx.product_id,
        transaction_id=tx.id,request_key=str(uuid4()),receipt={},created_at=tx.occurred_at));db.flush()
    return bill


def test_exact_service_reference_excludes_other_lines_services_and_partial_bills(setup):
    _,engine=setup
    with make_sessions(engine)() as db:
        current,rows=prepare(db,[29900]*5)
        attach_bill(db,current,'2026-10')
        attach_bill(db,rows[0],'2026-09')
        attach_bill(db,rows[1],'2026-08',reference='5500000002')
        attach_bill(db,rows[2],'2026-07',service='internet-bill')
        attach_bill(db,rows[3],'2026-06',amount=60000)
        # Unlinked same-merchant card activity must not join a known phone line.
        value=compare_payments(db,current)
        assert value['basis']=='bill-reference' and value['count']==1
        assert value['samples'][0]['transactionId']==rows[0].id
        current.amount_minor=-50000;db.flush()
        mismatch=compare_payments(db,current)
        assert mismatch['reason']=='bill_amount_mismatch'
        assert 'supera' in comparison_text(mismatch,'es')
        current.amount_minor=-20000;db.flush()
        assert compare_payments(db,current)['reason']=='partial_payment'


def test_rounding_stability_and_high_variable_range(setup):
    _,engine=setup
    with make_sessions(engine)() as db:
        current,_=prepare(db,[29900,30000,100000]);current.amount_minor=-45900
        value=compare_payments(db,current)
        assert value['averageMinor']==53300 and value['differenceMinor']==-7400
        assert not value['unusualIncrease']
        current.status='declined';db.flush()
        assert compare_payments(db,current)['status']=='not-comparable'


def test_average_rounds_half_cent_up(setup):
    _,engine=setup
    with make_sessions(engine)() as db:
        current,_=prepare(db,[10000,10001])
        assert compare_payments(db,current)['averageMinor']==10001


def test_approved_refund_removes_charge_from_history(setup):
    from backend.tests.test_operations import make_refund, approve_payload, approve_case
    app,engine=setup
    with make_sessions(engine)() as db:
        current,rows=prepare(db);reference=rows[0].id;db.commit()
    client,_=login(app);admin,_=login(app,'nora')
    case,_,refund=make_refund(client,reference)
    approve_case(admin,case)
    with make_sessions(engine)() as db:
        assert compare_payments(db,db.get(Transaction,'TX-1002'))['count']==3
    response=admin.post(f"/api/admin/refunds/{refund['id']}/decision",json=approve_payload())
    assert response.status_code==200,response.text
    with make_sessions(engine)() as db:
        result=compare_payments(db,db.get(Transaction,'TX-1002'))
        assert result['count']==2 and not result['unusualIncrease']
        assert reference not in [s['transactionId'] for s in result['samples']]


@pytest.mark.parametrize('locale',['es','en','pt'])
def test_audited_chat_comparison_is_read_only_and_not_sent_to_models(setup,models,locale):
    app,engine=setup
    with make_sessions(engine)() as db:prepare(db);db.commit()
    client,_=login(app);calls,_=models
    before=client.get('/api/bootstrap').json()
    first=client.post('/api/assistant/flow',json=message(locale=locale,transactionId='TX-1002')).json()
    assert '299' in first['text'] and first['flow']['missing_fields']==['difference']
    cid=first['conversation']['id']
    second=client.post('/api/assistant/flow',json=message(locale=locale,conversationId=cid,message='Esperaba 100 MXN')).json()
    assert second['flow']['canRegister']
    preview=client.get('/api/conversations/'+cid+'/claim-preview?locale='+locale).json()
    assert '53.5' in preview['summary']
    assert '299' in second['text'] and '160' in second['text']
    assert 'history-' not in json.dumps(calls) and 'Historial de teléfono' not in json.dumps(calls)
    assert '299' not in json.dumps(calls)
    with make_sessions(engine)() as db:
        state=db.get(ConversationFlow,cid).state
        assert 'history-' not in json.dumps(state['messages'])
        assert db.scalar(select(AuditEvent).where(AuditEvent.conversation_id==cid,AuditEvent.action=='tool_transaction_evidence'))
    after=client.get('/api/bootstrap').json()
    for key in ('products','transactions','requests'):assert after[key]==before[key]
