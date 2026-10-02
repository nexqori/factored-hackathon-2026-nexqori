"""Read-only case dossier. Links come from stored owner/reference IDs, never text."""
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select

from .models import AuditEvent, CardProfile, Conversation, Message, Product, Refund, RequestCase, Transaction, User, now
from .operations import iso_utc, refund_view
from .security import admin, customer_read, db_session


def trace_router(request_view, audit_view, conversation_view):
    router = APIRouter(prefix="/api")

    def dossier(db, case, reader, before, conversation_offset):
        owner = case.user_id
        customer = db.get(User, owner)
        transaction = db.scalar(select(Transaction).where(Transaction.id == case.transaction_id, Transaction.user_id == owner))
        product = db.scalar(select(Product).where(Product.id == transaction.product_id, Product.user_id == owner)) if transaction else None
        card = db.scalar(select(CardProfile).where(CardProfile.product_id == product.id, CardProfile.user_id == owner)) if product else None
        refund = db.scalar(select(Refund).where(Refund.request_id == case.id, Refund.user_id == owner))

        # A conversation with the same movement is related context, not proof that
        # the customer discussed this specific claim in every message.
        direct_conversations = select(AuditEvent.conversation_id).where(
            AuditEvent.user_id == owner, AuditEvent.request_id == case.id, AuditEvent.conversation_id.is_not(None))
        conversation_match = Conversation.id.in_(direct_conversations)
        if transaction:
            conversation_match = or_(conversation_match, Conversation.transaction_id == transaction.id)
        conversation_ids = select(Conversation.id).where(Conversation.user_id == owner, conversation_match)
        references = [AuditEvent.request_id == case.id,
                      and_(AuditEvent.request_id.is_(None), AuditEvent.conversation_id.in_(conversation_ids))]
        if transaction:
            references.append(and_(AuditEvent.transaction_id == transaction.id, AuditEvent.request_id.is_(None)))
        if product:
            references.append(and_(AuditEvent.product_id == product.id, AuditEvent.action == "card_blocked",
                                   AuditEvent.request_id.is_(None)))
        match = and_(AuditEvent.user_id == owner, or_(*references))
        query = select(AuditEvent, User.name).join(User, User.id == AuditEvent.actor_id).where(match)
        if before:
            anchor = db.scalar(select(AuditEvent).where(match, AuditEvent.id == before))
            if not anchor:
                raise HTTPException(404, "not_found")
            query = query.where(or_(AuditEvent.created_at < anchor.created_at,
                                    and_(AuditEvent.created_at == anchor.created_at, AuditEvent.id < anchor.id)))
        rows = db.execute(query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(51)).all()
        events = []
        for event, name in rows[:50]:
            relation = ("request" if event.request_id == case.id else "transaction" if transaction and event.transaction_id == transaction.id
                        else "conversation" if event.conversation_id else "product")
            events.append({**audit_view(event, name), "relation": relation, "at": iso_utc(event.created_at)})
        conv_query = select(Conversation).where(Conversation.id.in_(conversation_ids))
        conv_rows = db.scalars(conv_query.order_by(Conversation.updated_at.desc(), Conversation.id.desc())
                               .offset(conversation_offset).limit(21)).all()
        counts = dict(db.execute(select(Message.conversation_id, func.count(Message.id)).where(
            Message.user_id == owner, Message.conversation_id.in_([c.id for c in conv_rows[:20]])
        ).group_by(Message.conversation_id)).all())
        conversations = [{**conversation_view(c), "messageCount": counts.get(c.id, 0),
                          "relation": "transaction" if transaction and c.transaction_id == transaction.id else "request"}
                         for c in conv_rows[:20]]
        decision_actor = db.get(User, refund.decided_by) if refund and refund.decided_by else None
        outcome = "refund_" + refund.status if refund else case.status
        result = {
            "request": request_view(case, customer.name, refund),
            "customer": {"id": customer.id, "name": customer.name},
            "observedAt": iso_utc(now()), "outcome": outcome,
            "transaction": ({"id": transaction.id, "productId": transaction.product_id, "merchant": transaction.merchant,
                "amountMinor": transaction.amount_minor, "currency": transaction.currency, "status": transaction.status,
                "date": iso_utc(transaction.occurred_at)} if transaction else None),
            "product": ({"id": product.id, "type": product.type, "last4": product.last4,
                         "status": card.status if card else None} if product else None),
            "refund": ({**refund_view(db, refund), "decidedBy": {"id": decision_actor.id, "name": decision_actor.name}
                        if decision_actor else None} if refund else None),
            "events": events, "before": rows[49][0].id if len(rows) > 50 else None,
            "eventCount": db.scalar(select(func.count()).select_from(AuditEvent).where(match)),
            "conversations": conversations,
            "conversationCount": db.scalar(select(func.count()).select_from(Conversation).where(Conversation.id.in_(conversation_ids))),
            "nextConversationOffset": conversation_offset + 20 if len(conv_rows) > 20 else None,
            "source": "nexqori_records", "externalProcessorLogs": False,
        }
        # Viewing a dossier is itself auditable, without persisting its contents.
        db.add(AuditEvent(id=str(uuid4()), user_id=owner, actor_id=reader.id, action="claim_trace_viewed", request_id=case.id))
        db.commit()
        return result

    @router.get("/requests/{request_id}/trace")
    def own_trace(request_id: str, before: str | None = Query(None, max_length=64),
                  conversationOffset: int = Query(0, ge=0, le=100000), user=Depends(customer_read), db=Depends(db_session)):
        case = db.scalar(select(RequestCase).where(RequestCase.id == request_id, RequestCase.user_id == user.id))
        if not case:
            raise HTTPException(404, "not_found")
        return dossier(db, case, user, before, conversationOffset)

    @router.get("/admin/users/{user_id}/requests/{request_id}/trace")
    def admin_trace(user_id: str, request_id: str, before: str | None = Query(None, max_length=64),
                    conversationOffset: int = Query(0, ge=0, le=100000), user=Depends(admin), db=Depends(db_session)):
        case = db.scalar(select(RequestCase).where(RequestCase.id == request_id, RequestCase.user_id == user_id))
        if not case:
            raise HTTPException(404, "not_found")
        return dossier(db, case, user, before, conversationOffset)

    return router
