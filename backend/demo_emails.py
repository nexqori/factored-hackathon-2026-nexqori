"""Explicit demo login aliases. Never change a customer's notification address."""
from uuid import uuid4

from sqlalchemy import select

from .models import AuditEvent, User

UX_EMAILS = {
    'cargo': 'camila.torres@nexqori.com',
    'importe': 'diego.medina@nexqori.com',
    'pendiente': 'valeria.rojas@nexqori.com',
    'aplicacion': 'lucas.costa@nexqori.com',
    'documentos': 'sofia.vega@nexqori.com',
}
BASE_EMAILS = {
    'andrea': ('Andrea Rivera', 'andrea@nexqori.com', 'andrea.rivera@nexqori.com'),
    'mateo': ('Mateo Silva', 'mateo@nexqori.com', 'mateo.silva@nexqori.com'),
    'nora': ('Nora', 'admin@nexqori.com', 'nora.admin@nexqori.com'),
}


def update_demo_email(db, user, previous, desired):
    # A customized login (including Bryan's Gmail) is never replaced.
    if user.email != previous:
        return False
    if db.scalar(select(User.id).where(User.email == desired, User.id != user.id)):
        raise ValueError('Demo email already belongs to another user')
    user.email = desired
    db.add(AuditEvent(id=str(uuid4()), user_id=user.id, actor_id=user.id,
                      action='demo_login_email_updated'))
    db.flush()
    return True


def update_base_demo_emails(db):
    for uid, (name, previous, desired) in BASE_EMAILS.items():
        user = db.get(User, uid)
        if user and user.name == name:
            update_demo_email(db, user, previous, desired)
