import os
from datetime import datetime, timezone
from sqlalchemy import select
from .db import make_engine, make_sessions
from .models import User, Product, Transaction, RequestCase, AuditEvent
from .security import hasher

def seed(session, passwords):
    if session.scalar(select(User.id).limit(1)):
        return
    if any(not isinstance(p, str) or len(p) < 14 for p in passwords):
        raise RuntimeError("Run npm run setup: initial passwords require at least 14 characters.")
    users = [
        User(id="andrea",identity_number="00000001",email="andrea@nexqori.com",name="Andrea Rivera",password_hash=hasher.hash(passwords[0]),role="customer",locale="es"),
        User(id="nora",identity_number="00000002",email="admin@nexqori.com",name="Nora",password_hash=hasher.hash(passwords[1]),role="admin",locale="es"),
        User(id="mateo",identity_number="00000003",email="mateo@nexqori.com",name="Mateo Silva",password_hash=hasher.hash(passwords[2]),role="customer",locale="pt")
    ]
    session.add_all(users); session.flush()
    session.add_all([
        Product(id="account-01",user_id="andrea",type="account",last4="4821",balance_minor=1845000),
        Product(id="savings-01",user_id="andrea",type="savings",last4="7206",balance_minor=640000),
        Product(id="card-01",user_id="andrea",type="card",last4="8942",balance_minor=None),
        Product(id="account-02",user_id="mateo",type="account",last4="1103",balance_minor=520000)
    ]); session.flush()
    rows = [
        ("TX-1001","andrea","card-01","Mercado Central","shopping",-28650,"2026-09-28T16:30:00+00:00","completed"),
        ("TX-1002","andrea","card-01","Stream Plus","subscription",-18900,"2026-09-27T23:40:00+00:00","completed"),
        ("TX-1003","andrea","card-01","Café Aurora","food",-8500,"2026-09-27T15:15:00+00:00","completed"),
        ("TX-1004","andrea","account-01","María López","transfer",280000,"2026-09-26T22:00:00+00:00","completed"),
        ("TX-1005","andrea","account-01","Luz Hogar","utilities",-52000,"2026-09-26T17:00:00+00:00","pending"),
        ("TX-1006","andrea","card-01","Libro Abierto","shopping",-34500,"2026-09-25T21:10:00+00:00","declined"),
        ("TX-2001","mateo","account-02","Mercado del Sol","shopping",-14000,"2026-09-27T18:00:00+00:00","completed")
    ]
    for id,uid,pid,merchant,category,amount,date,status in rows:
        session.add(Transaction(id=id,user_id=uid,product_id=pid,merchant=merchant,category=category,amount_minor=amount,occurred_at=datetime.fromisoformat(date),status=status))
    session.flush()
    at=datetime(2026,9,26,17,5,tzinfo=timezone.utc)
    session.add(RequestCase(id="NQ-1021",user_id="andrea",transaction_id="TX-1005",request_key="seed-request-0001",service="payments",reason="payment",details="Pago pendiente / Pending payment / Pagamento pendente.",status="in_review",created_at=at,updated_at=at))
    session.flush()
    session.add_all([
        AuditEvent(id="seed-01",user_id="andrea",request_id="NQ-1021",action="created",actor_id="andrea",created_at=at),
        AuditEvent(id="seed-02",user_id="andrea",request_id="NQ-1021",action="reviewed",actor_id="nora",created_at=at)
    ])
    session.commit()

if __name__ == "__main__":
    engine=make_engine()
    with make_sessions(engine)() as session:
        seed(session, [os.getenv("CUSTOMER_PASSWORD"),os.getenv("ADMIN_PASSWORD"),os.getenv("SECOND_CUSTOMER_PASSWORD")])
    print("Nexqori demo seed ready.")
