"""Isolated UI test transport. Never imported by the deployed application."""
import json
import os
import secrets
from pathlib import Path
from uuid import uuid4

from fastapi import Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from backend import notifications
from backend.db import make_engine, make_sessions
from backend.main import create_app
from backend.models import Base, User, Product, CardProfile, EmailChallenge
from backend.security import customer_read, db_session, hasher

if os.getenv('NEXQORI_NOTIFICATION_UI_CHECK') != '1':
    raise RuntimeError('Explicit isolated notification test required')
folder = Path(os.environ['NEXQORI_NOTIFICATION_UI_DATA']).resolve()
if not folder.is_relative_to(Path('.local/verification').resolve()):
    raise RuntimeError('Private test directory required')
database = folder / 'bank.sqlite'
if database.exists():
    raise RuntimeError('Fresh database required')
os.environ['BANK_CARD_BLOCK_EMAIL_REQUIRED'] = 'true'
os.environ['MAIL_SMTP_HOST'] = 'controlled-ui-test'
os.environ['MAIL_FROM'] = 'sender@example.com'
engine = make_engine('sqlite:///' + str(database))
Base.metadata.create_all(engine)
people = []
with make_sessions(engine)() as db:
    for locale in ('es', 'en', 'pt'):
        uid = uuid4().hex
        password = secrets.token_urlsafe(24)
        email = uid + '@example.com'
        db.add(User(id=uid, email=email, name='Verificación correo '+locale,
                    password_hash=hasher.hash(password), role='customer', locale=locale))
        db.flush()
        db.add_all([Product(id='account-'+uid, user_id=uid, type='account', last4='9050', balance_minor=150000),
                    Product(id='card-'+uid, user_id=uid, type='card', last4='9101')])
        db.flush()
        db.add(CardProfile(product_id='card-'+uid, user_id=uid, provider_ref=uid, expiry_month=12,
                           expiry_year=2030, settlement_product_id='account-'+uid))
        people.append({'userId':uid, 'email':email, 'password':password, 'locale':locale, 'cardId':'card-'+uid})
    db.commit()
(folder/'credentials.private.json').write_text(json.dumps(people), encoding='utf-8')
mailbox = {}


def deliver(email, code, purpose, locale, last4):
    mailbox[email] = {'code':code, 'purpose':purpose, 'last4':last4}


notifications.send_code = deliver
app = create_app(engine, ['http://127.0.0.1:5194'], False)


@app.get('/api/verification/mailbox')
def read_mail(user=Depends(customer_read), db=Depends(db_session)):
    row = db.scalar(select(EmailChallenge).where(EmailChallenge.user_id==user.id).order_by(EmailChallenge.created_at.desc()).limit(1))
    # Advance only the resend clock to avoid a minute of idle test time.
    row.created_at -= 61
    db.commit()
    return mailbox[row.email]


app.mount('/assets', StaticFiles(directory='dist/assets'))


@app.get('/{path:path}')
def frontend(path: str):
    root = Path('dist').resolve()
    candidate = (root/path).resolve()
    return FileResponse(candidate if candidate.is_relative_to(root) and candidate.is_file() else root/'index.html')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=5194, access_log=False)
