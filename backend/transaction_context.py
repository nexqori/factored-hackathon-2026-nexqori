"""Read-only transaction evidence. No model, processor, credentials or command execution."""
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from .models import Transaction, RequestCase, Refund, AuditEvent
from .payment_history import compare_payments, comparison_text

COPY = {
    "es": {
        "record": "Según el registro de Nexqori, {merchant} ({id}) tiene un importe de {amount} {currency} y está {status}.",
        "completed": "completado", "pending": "pendiente", "declined": "rechazado",
        "case": "El reclamo vinculado es {id}. Puedes consultarlo en Mis solicitudes.",
        "no_case": "No hay una solicitud vinculada a este movimiento.",
        "refund": "La devolución {id} está {status}.",
        "refund_pending": "pendiente de aprobación administrativa", "refund_approved": "aprobada", "refund_rejected": "rechazada",
        "credit": "El abono registrado tiene la referencia {id}.",
        "events": "El último evento de gestión del reclamo se registró el {date}.",
    },
    "en": {
        "record": "Nexqori's record shows {merchant} ({id}) for {amount} {currency}, with status {status}.",
        "completed": "completed", "pending": "pending", "declined": "declined",
        "case": "The linked request is {id}. You can open it in My requests.",
        "no_case": "No request is linked to this transaction.",
        "refund": "Refund {id} is {status}.",
        "refund_pending": "awaiting administrator approval", "refund_approved": "approved", "refund_rejected": "rejected",
        "credit": "The recorded credit reference is {id}.",
        "events": "The latest request-handling event was recorded on {date}.",
    },
    "pt": {
        "record": "Segundo o registro da Nexqori, {merchant} ({id}) tem valor de {amount} {currency} e está {status}.",
        "completed": "concluído", "pending": "pendente", "declined": "recusado",
        "case": "A solicitação vinculada é {id}. Você pode abri-la em Minhas solicitações.",
        "no_case": "Nenhuma solicitação está vinculada a esta movimentação.",
        "refund": "A devolução {id} está {status}.",
        "refund_pending": "aguardando aprovação administrativa", "refund_approved": "aprovada", "refund_rejected": "rejeitada",
        "credit": "O crédito registrado tem a referência {id}.",
        "events": "O último evento de tratamento da solicitação foi registrado em {date}.",
    },
}


def transaction_evidence(db, owner_id, transaction_id):
    tx = db.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == owner_id))
    if not tx:
        raise HTTPException(404, "not_found")
    case = db.scalar(select(RequestCase).where(RequestCase.transaction_id == tx.id, RequestCase.user_id == owner_id))
    refund = db.scalar(select(Refund).where(Refund.transaction_id == tx.id, Refund.user_id == owner_id))
    actions = ('created', 'service_request_created', 'reviewed', 'handed_off', 'refund_requested', 'refund_approved', 'refund_rejected')
    events = db.scalars(select(AuditEvent).where(AuditEvent.user_id == owner_id, AuditEvent.request_id == case.id, AuditEvent.action.in_(actions)).order_by(AuditEvent.created_at.desc()).limit(20)).all() if case else []
    return {
        "source": "nexqori_records", "externalProcessorLogs": False,
        "historyComparison": compare_payments(db, tx),
        "transaction": {"id":tx.id,"productId":tx.product_id,"merchant":tx.merchant,"amountMinor":tx.amount_minor,"currency":tx.currency,"status":tx.status,"date":tx.occurred_at.isoformat()},
        "request": {"id":case.id,"status":case.status} if case else None,
        "refund": {"id":refund.id,"status":refund.status,"creditTransactionId":refund.credit_transaction_id} if refund else None,
        "events": [{"action":e.action,"at":e.created_at.isoformat()} for e in events],
        "eventsLimit": 20,
    }


def transaction_reply(evidence, locale):
    copy = COPY[locale]
    tx, case, refund = (evidence[k] for k in ("transaction", "request", "refund"))
    amount = f"{Decimal(tx['amountMinor']) / 100:,.2f}"
    if locale == 'pt':
        amount = amount.translate(str.maketrans({',':'.','.':','}))
    lines = [copy['record'].format(**(tx | {'amount':amount,'status':copy[tx['status']]}))]
    history = comparison_text(evidence.get('historyComparison'), locale)
    if history: lines.append(history)
    lines.append(copy['case'].format(id=case['id']) if case else copy['no_case'])
    if refund:
        lines.append(copy['refund'].format(id=refund['id'],status=copy['refund_'+refund['status']]))
        if refund['creditTransactionId']:
            lines.append(copy['credit'].format(id=refund['creditTransactionId']))
    # The bounded event preview is not presented as the total lifetime audit count.
    if evidence['events']:
        lines.append(copy['events'].format(count=len(evidence['events']),date=evidence['events'][0]['at'][:10]))
    return {'text':'\n\n'.join(lines),'intent':'transaction-evidence','destination':None,'navigation':None,'evidence':evidence}
