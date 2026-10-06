"""Email confirmation is a server policy, never an LLM tool or a client choice."""
import os
import re
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, field_validator
from sqlalchemy import func, select

from .email_templates import code_message, refund_message
from .models import AuditEvent, CardProfile, EmailChallenge, NotificationPreference, Product, User, now
from .schemas import StrictModel
from .security import customer, customer_read, current_session, db_session, hasher, LoginLimiter, verify


def email_required():
    return os.getenv('BANK_CARD_BLOCK_EMAIL_REQUIRED', 'true').lower() == 'true'


def mail_ready():
    return bool(os.getenv('MAIL_SMTP_HOST') and (os.getenv('MAIL_FROM') or os.getenv('MAIL_SMTP_USER')))


def masked(email):
    local, domain = email.rsplit('@', 1)
    return local[:1] + '•••@' + domain


class PasswordInput(StrictModel):
    password: str = Field(min_length=1, max_length=256)


class EmailInput(PasswordInput):
    email: str = Field(min_length=5, max_length=254)

    @field_validator('email')
    @classmethod
    def address(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}", value):
            raise ValueError('Invalid email')
        return value


class CodeInput(StrictModel):
    challengeId: str = Field(min_length=1, max_length=64)
    code: str = Field(pattern=r'^\d{6}$')


def send_code(recipient, code, purpose, locale, last4=None):
    send_email(recipient, *code_message(code, purpose, locale, last4))


def send_email(recipient, subject, plain, html):
    if not mail_ready():
        raise HTTPException(503, 'mail_unavailable')
    message = EmailMessage()
    sender = os.getenv('MAIL_FROM') or os.environ['MAIL_SMTP_USER']
    message['From'] = formataddr(('Nexqori', parseaddr(sender)[1]))
    message['To'] = recipient
    message['Subject'] = subject
    message.set_content(plain)
    message.add_alternative(html, subtype='html')
    try:
        mode = os.getenv('MAIL_SMTP_SECURITY', 'starttls')
        if mode not in ('ssl', 'starttls'):
            raise ValueError('TLS required')
        host = os.environ['MAIL_SMTP_HOST']
        port = int(os.getenv('MAIL_SMTP_PORT', '465' if mode == 'ssl' else '587'))
        context = ssl.create_default_context()
        connection = smtplib.SMTP_SSL(host, port, context=context, timeout=10) if mode == 'ssl' else smtplib.SMTP(host, port, timeout=10)
        with connection as smtp:
            if mode == 'starttls':
                smtp.starttls(context=context)
            if os.getenv('MAIL_SMTP_USER'):
                smtp.login(os.environ['MAIL_SMTP_USER'], os.environ.get('MAIL_SMTP_PASSWORD', ''))
            refused = smtp.send_message(message)
            if refused:
                raise ValueError('Recipient refused')
    except Exception:
        # SMTP diagnostics may contain addresses or credentials. Never expose them.
        raise HTTPException(503, 'mail_unavailable') from None


def log(db, user, action, product=None):
    db.add(AuditEvent(id=str(uuid4()), user_id=user.id, actor_id=user.id, action=action, product_id=product))


def consume_code(db, user, session, ident, code, purpose, product=None):
    row = db.scalar(select(EmailChallenge).where(EmailChallenge.id == ident, EmailChallenge.user_id == user.id).with_for_update())
    if (not row or row.purpose != purpose or row.product_id != product or row.session_hash != session.token_hash
            or row.consumed or row.expires_at <= int(time.time()) or row.attempts >= 5):
        raise HTTPException(403, 'email_code_invalid')
    row.attempts += 1
    if not verify(code or '', row.code_hash):
        log(db, user, 'email_code_rejected', product)
        db.commit()  # Failed attempts must persist even though the request fails.
        raise HTTPException(403, 'email_code_invalid')
    row.consumed = True
    return row


def notifications_router():
    router = APIRouter(prefix='/api')
    limiter = LoginLimiter(10)

    def authenticate(request, user, password):
        limiter.consume(request.client.host if request.client else 'local', user.id)
        if not verify(password, user.password_hash):
            raise HTTPException(403, 'card_password')

    def issue(db, user, session, email, purpose, product=None):
        stamp = int(time.time())
        # The caller holds the owner row lock, serializing sends across sessions.
        recent = db.scalar(select(EmailChallenge).where(EmailChallenge.user_id == user.id).order_by(EmailChallenge.created_at.desc()).limit(1))
        if recent and stamp - recent.created_at < 60:
            raise HTTPException(429, 'email_code_wait')
        count = db.scalar(select(func.count()).select_from(EmailChallenge).where(EmailChallenge.user_id == user.id, EmailChallenge.created_at > stamp - 3600))
        if count >= 10:
            raise HTTPException(429, 'rate_limited')
        code = str(secrets.randbelow(1_000_000)).zfill(6)
        row = EmailChallenge(id=str(uuid4()), user_id=user.id, session_hash=session.token_hash,
                             purpose=purpose, product_id=product.id if product else None, email=email,
                             code_hash=hasher.hash(code), created_at=stamp, expires_at=stamp + 300)
        send_code(email, code, purpose, user.locale, product.last4 if product else None)
        for previous in db.scalars(select(EmailChallenge).where(EmailChallenge.user_id == user.id,
                EmailChallenge.purpose == purpose, EmailChallenge.product_id == row.product_id, EmailChallenge.consumed.is_(False))):
            previous.consumed = True
        db.add(row)
        log(db, user, 'email_code_sent', row.product_id)
        db.commit()
        return {'challengeId': row.id, 'destination': masked(email), 'expiresAt': row.expires_at, 'resendAt': stamp + 60}

    @router.get('/profile/notifications')
    def settings(user=Depends(customer_read), db=Depends(db_session)):
        setting = db.get(NotificationPreference, user.id)
        return {'email': setting.email if setting else None, 'suggestedEmail': user.email,
                'verified': bool(setting), 'mailAvailable': mail_ready(),
                'blockRequiresEmail': email_required()}

    @router.post('/profile/notifications/code')
    def start(body: EmailInput, request: Request, user=Depends(customer), auth=Depends(current_session), db=Depends(db_session)):
        authenticate(request, user, body.password)
        db.scalar(select(User).where(User.id == user.id).with_for_update())
        return issue(db, user, auth[0], body.email, 'notification_email')

    @router.post('/profile/notifications/verify')
    def finish(body: CodeInput, user=Depends(customer), auth=Depends(current_session), db=Depends(db_session)):
        db.scalar(select(User).where(User.id == user.id).with_for_update())
        row = consume_code(db, user, auth[0], body.challengeId, body.code, 'notification_email')
        setting = db.get(NotificationPreference, user.id)
        if setting:
            setting.email, setting.verified_at = row.email, now()
        else:
            db.add(NotificationPreference(user_id=user.id, email=row.email))
        for pending in db.scalars(select(EmailChallenge).where(EmailChallenge.user_id == user.id, EmailChallenge.purpose == 'card_block')):
            pending.consumed = True
        log(db, user, 'notification_email_verified')
        db.commit()
        return {'email': row.email, 'verified': True}

    @router.post('/cards/{product_id}/block-code')
    def block_code(product_id: str, body: PasswordInput, request: Request, user=Depends(customer), auth=Depends(current_session), db=Depends(db_session)):
        authenticate(request, user, body.password)
        db.scalar(select(User).where(User.id == user.id).with_for_update())
        card = db.scalar(select(CardProfile).where(CardProfile.product_id == product_id, CardProfile.user_id == user.id))
        if not card:
            raise HTTPException(404, 'not_found')
        if card.status != 'active':
            raise HTTPException(409, 'card_blocked')
        setting = db.get(NotificationPreference, user.id)
        if not setting:
            raise HTTPException(409, 'notification_email_required')
        product = db.scalar(select(Product).where(Product.id == card.product_id, Product.user_id == user.id))
        return issue(db, user, auth[0], setting.email, 'card_block', product)

    return router


def notify_refund_completed(db, refund):
    """Called only after the credit commit, never by a model or an approval preview."""
    owner = db.get(User, refund.user_id)
    setting = db.get(NotificationPreference, refund.user_id)
    account = db.get(Product, refund.destination_product_id)
    recipient = setting.email if setting else owner.email
    action = 'notification_refund_accepted'
    try:
        send_email(recipient, *refund_message(owner.locale, refund.amount_minor, refund.currency,
            refund.request_id, refund.credit_transaction_id, account.last4))
    except HTTPException:
        # Delivery failure must not undo a settled credit or invite a second debit/credit.
        action = 'notification_refund_failed'
    db.add(AuditEvent(id=str(uuid4()), user_id=owner.id, actor_id=refund.decided_by,
        action=action, request_id=refund.request_id, product_id=account.id))
    db.commit()
