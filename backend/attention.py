"""Persistent attention closure and optional feedback. No financial side effects."""
import logging
import time
from threading import Event, Thread
from typing import Literal
from uuid import UUID, uuid4, uuid5

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import func, select

from .models import (AttentionReview, AuditEvent, ChatFeedback, Conversation, ConversationFlow,
                     Message, Refund, RequestCase, Transaction, User, iso_utc)
from .schemas import ConfirmInput, Locale, StrictModel
from .security import admin, admin_write, customer, customer_read, db_session

DELAY_SECONDS = 15 * 60


class Resolution(ConfirmInput):
    noPending: Literal[True]
    summary: str = Field(min_length=10, max_length=1000)


class Answers(StrictModel):
    revision: int = Field(ge=0)
    locale: Locale
    nps: int | None = Field(default=None, ge=0, le=10)
    csat: int | None = Field(default=None, ge=1, le=5)
    ces: int | None = Field(default=None, ge=1, le=7)
    comment: str = Field(default='', max_length=1000)
    submit: bool = False


def event(db, row, actor, action):
    db.add(AuditEvent(id=str(uuid4()), user_id=row.user_id, actor_id=actor,
                      request_id=row.request_id, conversation_id=row.conversation_id, action=action))


def checkpoint(db, source, item):
    if source == 'requests':
        from .claim_trace import case_conversations
        refund = db.scalar(select(Refund).where(Refund.request_id == item.id, Refund.user_id == item.user_id))
        tx = db.scalar(select(Transaction).where(Transaction.id == item.transaction_id, Transaction.user_id == item.user_id))
        return {'status': item.status, 'updatedAt': iso_utc(item.updated_at),
                'refund': {'id': refund.id, 'status': refund.status} if refund else None,
                'transactionStatus': tx.status if tx else None,
                'messages': db.scalar(select(func.count(Message.id)).where(Message.user_id == item.user_id,
                                      Message.conversation_id.in_(case_conversations(item))))}
    return {'messages': db.scalar(select(func.count(Message.id)).where(Message.conversation_id == item.id,
                                                                      Message.user_id == item.user_id))}


def pending(db, source, item):
    if source == 'requests':
        value = checkpoint(db, source, item)
        return value['transactionStatus'] == 'pending' or (value['refund'] or {}).get('status') == 'pending'
    flow = db.get(ConversationFlow, item.id)
    # Only finished informational queries can be closed by the customer.
    if not flow:
        return True
    context = flow.state.get('context', {})
    triage = context.get('triage', {})
    return flow.state.get('phase') != 'completed' or triage.get('family') != 'query' or bool(flow.request_id)


def view(row):
    if row is None:
        return None
    return {'id': row.id, 'status': row.status, 'summary': row.summary,
            'confirmedAt': row.confirmed_at, 'dueAt': row.due_at, 'closedAt': row.closed_at,
            'answers': row.answers, 'revision': row.answer_revision, 'submittedAt': row.submitted_at,
            'snapshots': row.snapshots}


def find(db, source, identity):
    field = AttentionReview.request_id if source == 'requests' else AttentionReview.conversation_id
    return db.scalar(select(AttentionReview).where(field == identity))


def finalize_due(db, row, source, item, timestamp):
    if row.status != 'scheduled' or row.due_at > timestamp:
        return False
    if not item or pending(db, source, item) or checkpoint(db, source, item) != row.checkpoint:
        row.status = 'reopened'
        event(db, row, row.resolved_by, 'attention_closure_stopped')
        return False
    received = {k: v for k, v in row.answers.items() if k != 'locale' and v is not None and v != ''}
    missing = [k for k in ('nps', 'csat') if row.answers.get(k) is None]
    row.snapshots = [*row.snapshots, {'processedAt': timestamp, 'trigger': 'deadline',
        'summary': row.summary, 'confirmedBy': row.resolved_by, 'evidence': row.checkpoint,
        'received': received, 'missing': missing,
        'feedback': 'submitted' if row.submitted_at else 'partial' if received else 'unanswered'}]
    row.status, row.closed_at = 'closed', timestamp
    event(db, row, row.resolved_by, 'attention_closed_by_timer')
    return True


def lock_source(db, source, identity, user, write=False):
    model = RequestCase if source == 'requests' else Conversation
    item = db.get(model, identity)
    if not item or (user.role != 'admin' and item.user_id != user.id):
        raise HTTPException(404, 'not_found')
    if write:
        # Same order as chat: owner then conversation/case, then review.
        db.scalar(select(User).where(User.id == item.user_id).with_for_update())
        item = db.scalar(select(model).where(model.id == identity).with_for_update().execution_options(populate_existing=True))
    return item


def process_due(sessions, at=None):
    """Clock injected only by tests; HTTP clients cannot advance server time."""
    timestamp = int(time.time()) if at is None else at
    with sessions() as db:
        ids = list(db.scalars(select(AttentionReview.id).where(AttentionReview.status == 'scheduled',
                                  AttentionReview.due_at <= timestamp).order_by(AttentionReview.due_at).limit(100)))
    count = 0
    for identity in ids:
        with sessions() as db:
            row = db.get(AttentionReview, identity)
            if not row:
                continue
            source = 'requests' if row.request_id else 'conversations'
            model = RequestCase if row.request_id else Conversation
            db.scalar(select(User).where(User.id == row.user_id).with_for_update())
            item = db.scalar(select(model).where(model.id == (row.request_id or row.conversation_id)).with_for_update())
            row = db.scalar(select(AttentionReview).where(AttentionReview.id == identity).with_for_update().execution_options(populate_existing=True))
            count += int(finalize_due(db, row, source, item, timestamp))
            db.commit()
    return count


class AttentionClock:
    def __init__(self, sessions):
        self.sessions, self.stop = sessions, Event()
        self.thread = None

    def start(self):
        def run():
            while not self.stop.is_set():
                try:
                    process_due(self.sessions)
                except Exception:
                    logging.getLogger(__name__).exception('Attention closure scan failed')
                self.stop.wait(30)
        self.thread = Thread(target=run, name='attention-closure', daemon=True)
        self.thread.start()

    def shutdown(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=10)


def attention_router():
    router = APIRouter(prefix='/api')
    Source = Literal['requests', 'conversations']

    def read(source, identity, user, db):
        item = lock_source(db, source, identity, user)
        row = find(db, source, identity)
        return {'review': view(row), 'canResolve': (user.role == 'admin' if source == 'requests' else user.role == 'customer')
                and not pending(db, source, item), 'pending': bool(pending(db, source, item)), 'serverTime': int(time.time())}

    @router.get('/attention/{source}/{identity}')
    def own_read(source: Source, identity: str, user=Depends(customer_read), db=Depends(db_session)):
        return read(source, identity, user, db)

    @router.get('/admin/attention/{source}/{identity}')
    def admin_read(source: Source, identity: str, user=Depends(admin), db=Depends(db_session)):
        return read(source, identity, user, db)

    def resolve(source, identity, payload, user, db):
        item = lock_source(db, source, identity, user, True)
        if source == 'requests' and user.role != 'admin':
            raise HTTPException(403, 'role')
        if source == 'conversations' and user.role != 'customer':
            raise HTTPException(403, 'role')
        if pending(db, source, item):
            raise HTTPException(409, 'attention_pending')
        summary = payload.summary.strip()
        if len(summary) < 10:
            raise HTTPException(422, 'details')
        row = find(db, source, identity)
        if row and row.status in ('scheduled', 'closed'):
            if row.summary != summary:
                raise HTTPException(409, 'conflict')
            return read(source, identity, user, db)
        timestamp = int(time.time())
        if row is None:
            row = AttentionReview(id=str(uuid4()), user_id=item.user_id,
                request_id=identity if source == 'requests' else None,
                conversation_id=identity if source == 'conversations' else None,
                answers={}, snapshots=[], answer_revision=0)
            db.add(row)
        row.summary, row.resolved_by = summary, user.id
        row.status, row.confirmed_at, row.due_at, row.closed_at = 'scheduled', timestamp, timestamp + DELAY_SECONDS, None
        row.checkpoint = checkpoint(db, source, item)
        event(db, row, user.id, 'attention_resolved')
        db.commit()
        return read(source, identity, user, db)

    @router.post('/attention/{source}/{identity}/resolve')
    def own_resolve(source: Source, identity: str, payload: Resolution, user=Depends(customer), db=Depends(db_session)):
        return resolve(source, identity, payload, user, db)

    @router.post('/admin/attention/{source}/{identity}/resolve')
    def admin_resolve(source: Source, identity: str, payload: Resolution, user=Depends(admin_write), db=Depends(db_session)):
        return resolve(source, identity, payload, user, db)

    @router.post('/attention/{source}/{identity}/reopen')
    def reopen(source: Source, identity: str, payload: ConfirmInput, user=Depends(customer), db=Depends(db_session)):
        lock_source(db, source, identity, user, True)
        row = find(db, source, identity)
        if not row:
            raise HTTPException(404, 'not_found')
        if row.status != 'reopened':
            row.status = 'reopened'
            event(db, row, user.id, 'attention_reopened')
            db.commit()
        return read(source, identity, user, db)

    @router.put('/attention/{source}/{identity}/feedback')
    def feedback(source: Source, identity: str, payload: Answers, user=Depends(customer), db=Depends(db_session)):
        item = lock_source(db, source, identity, user, True)
        row = find(db, source, identity)
        if not row:
            raise HTTPException(409, 'attention_pending')
        # A late response cannot rewrite the information present at closure,
        # even when it arrives between deadline and the worker's next scan.
        finalize_due(db, row, source, item, int(time.time()))
        values = payload.model_dump(exclude={'revision', 'submit'})
        values['comment'] = values['comment'].strip()
        if row.answers == values and bool(row.submitted_at) == payload.submit:
            db.commit()
            return read(source, identity, user, db)
        if row.answer_revision != payload.revision or row.submitted_at:
            raise HTTPException(409, 'conflict')
        if payload.submit and (payload.nps is None or payload.csat is None):
            raise HTTPException(422, 'attention_scores')
        row.answers = values
        row.answer_revision += 1
        timestamp = int(time.time())
        if payload.submit:
            row.submitted_at = timestamp
            for metric in ('nps', 'csat', 'ces'):
                if values[metric] is not None:
                    key = str(uuid5(UUID(row.id), metric))
                    db.add(ChatFeedback(id=str(uuid4()), user_id=user.id, submission_id=key, metric=metric,
                        score=values[metric], locale=payload.locale,
                        form_duration_ms=None, conversation_duration_ms=None))
        event(db, row, user.id, 'feedback_submitted' if payload.submit else 'feedback_draft_saved')
        db.commit()
        return read(source, identity, user, db)

    return router
