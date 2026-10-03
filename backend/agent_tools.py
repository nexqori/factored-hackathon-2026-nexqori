"""Authenticated read gateway. Financial commands deliberately have no dispatcher."""
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from .agent_routing import TOOLS, tools_for
from .catalog import SERVICES, service_view
from .models import AuditEvent, CardProfile, Conversation, Product, Refund, RequestCase, Transaction
from .schemas import Locale
from .security import customer, db_session
from .transaction_context import transaction_evidence
from .workflows import workflow_view


class ReadToolInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    intent: str = Field(min_length=1, max_length=64)
    tool: str = Field(min_length=1, max_length=64)
    referenceId: str | None = Field(default=None, min_length=1, max_length=64)
    conversationId: str | None = Field(default=None, min_length=1, max_length=64)
    locale: Locale = 'es'


def read_tool(db, owner_id, payload, *, commit=True):
    """Caller supplies a session-derived owner, never a model-derived identity."""
    definition = TOOLS.get(payload.tool)
    if not definition or definition['kind'] != 'read' or payload.tool not in tools_for(payload.intent):
        raise HTTPException(403, 'tool_not_allowed')
    if bool(definition['reference']) != bool(payload.referenceId):
        raise HTTPException(422, 'tool_reference_required' if definition['reference'] else 'tool_reference_not_allowed')
    if payload.conversationId:
        conversation = db.scalar(select(Conversation).where(Conversation.id == payload.conversationId, Conversation.user_id == owner_id))
        if not conversation:
            raise HTTPException(404, 'not_found')
        if payload.tool == 'read-transaction-evidence' and conversation.transaction_id and conversation.transaction_id != payload.referenceId:
            raise HTTPException(409, 'conversation_context_conflict')
    result, references = _read(db, owner_id, payload)
    audit_id = str(uuid4())
    db.add(AuditEvent(id=audit_id, user_id=owner_id, actor_id=owner_id,
                      action=payload.tool.replace('read-', 'tool_').replace('-', '_'),
                      conversation_id=payload.conversationId, **references))
    # No response leaves the gateway without its audit record committed.
    if commit: db.commit()
    else: db.flush()  # Embedded chat commits the audited reads with its complete turn.
    return {'tool': payload.tool, 'intent': payload.intent, 'status': 'executed',
            'source': result.get('source', 'nexqori_records'), 'data': result, 'auditEventId': audit_id,
            'executed_operations': []}


def _read(db, owner, p):
    if p.tool == 'read-balances':
        rows = db.scalars(select(Product).where(Product.user_id == owner, Product.type.in_(('account', 'savings'))).order_by(Product.id).limit(21)).all()
        return {'products': [{'id': r.id, 'type': r.type, 'last4': r.last4, 'balanceMinor': r.balance_minor, 'currency': r.currency} for r in rows[:20]], 'hasMore': len(rows) > 20, 'limit': 20}, {}
    if p.tool == 'read-transactions':
        rows = db.scalars(select(Transaction).where(Transaction.user_id == owner).order_by(Transaction.occurred_at.desc(), Transaction.id.desc()).limit(21)).all()
        return {'transactions': [{'id': r.id, 'merchant': r.merchant, 'category': r.category, 'amountMinor': r.amount_minor, 'currency': r.currency, 'status': r.status, 'date': r.occurred_at.isoformat()} for r in rows[:20]], 'hasMore': len(rows) > 20, 'limit': 20}, {}
    if p.tool == 'read-cards':
        rows = db.execute(select(Product, CardProfile).join(CardProfile, (CardProfile.product_id == Product.id) & (CardProfile.user_id == Product.user_id)).where(Product.user_id == owner, Product.type == 'card').order_by(Product.id).limit(21)).all()
        return {'cards': [{'id': card.id, 'last4': card.last4, 'status': profile.status} for card, profile in rows[:20]], 'hasMore': len(rows) > 20, 'limit': 20}, {}
    if p.tool == 'read-transaction-evidence':
        evidence = transaction_evidence(db, owner, p.referenceId)
        return evidence, {'transaction_id': p.referenceId, 'product_id': evidence['transaction']['productId'], 'request_id': evidence['request']['id'] if evidence['request'] else None}
    if p.tool == 'read-request-status':
        case = db.scalar(select(RequestCase).where(RequestCase.id == p.referenceId, RequestCase.user_id == owner))
        if not case:
            raise HTTPException(404, 'not_found')
        refund = db.scalar(select(Refund).where(Refund.request_id == case.id, Refund.user_id == owner))
        return {'request': {'id': case.id, 'status': case.status, 'updatedAt': case.updated_at.isoformat()},
                'refund': {'id': refund.id, 'status': refund.status, 'creditTransactionId': refund.credit_transaction_id} if refund else None}, {'request_id': case.id, 'transaction_id': case.transaction_id}
    if p.tool == 'read-service-info':
        return {'source': 'nexqori_catalog', 'service': service_view(SERVICES[p.intent], p.locale)}, {}
    if p.tool == 'read-problem-contract':
        return {'source': 'nexqori_catalog', 'contract': workflow_view(p.intent, p.locale)}, {}
    raise HTTPException(403, 'tool_not_allowed')


def agent_tools_router():
    router = APIRouter()

    @router.post('/api/assistant/tools/read')
    def run_tool(payload: ReadToolInput, user=Depends(customer), db=Depends(db_session)):
        # The intent narrows the allowlist; it grants neither identity nor role.
        return read_tool(db, user.id, payload)

    return router
