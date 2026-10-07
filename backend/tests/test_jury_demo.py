from sqlalchemy import select
from backend.tests.test_api import setup
from backend.jury_demo import prepare, CUSTOMER_PASSWORD, ADMIN_PASSWORD
from backend.db import make_sessions
from backend.models import User, Transaction, Product, BillPayment
from backend.security import verify
from backend.payment_history import compare_payments


def test_public_demo_is_ready_and_repeat_preserves_existing_records(setup):
    app,engine=setup
    with make_sessions(engine)() as db:
        result=prepare(db);db.commit()
        customer=db.get(User,result['customerId'])
        admin=db.scalar(select(User).where(User.email==result['adminEmail']))
        assert verify(CUSTOMER_PASSWORD,customer.password_hash) and customer.role=='customer'
        assert verify(ADMIN_PASSWORD,admin.password_hash) and admin.role=='admin'
        charge=db.get(Transaction,result['phoneTransactionId'])
        assert charge.status=='completed' and charge.amount_minor==-45900
        comparison=compare_payments(db,charge)
        assert comparison['count']==5 and comparison['averageMinor']==29900
        payment=db.scalar(select(BillPayment).where(BillPayment.transaction_id==charge.id))
        assert payment.receipt['status']=='completed'
        account=db.get(Product,charge.product_id);balance=account.balance_minor
        again=prepare(db);db.commit()
        assert not again['created'] and again['otherRecordsPreserved']
        assert db.get(Product,charge.product_id).balance_minor==balance
