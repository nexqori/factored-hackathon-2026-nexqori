"""Current, owned case outcome; deterministic text without model access to records."""
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from .models import RequestCase, Refund, Transaction
from .claim_review import handling_view
from .catalog import request_kind


def unique_owned_claim(db, owner):
    """Use an unambiguous owned claim; never guess between multiple cases."""
    rows = db.scalars(select(RequestCase).where(RequestCase.user_id == owner)).all()
    claims = [row.id for row in rows if request_kind(row) == 'claim']
    return claims[0] if len(claims) == 1 else None


def read_case_status(db, owner, identity):
    case = db.scalar(select(RequestCase).where(RequestCase.id == identity, RequestCase.user_id == owner))
    if not case:
        raise HTTPException(404, 'not_found')
    refund = db.scalar(select(Refund).where(Refund.request_id == case.id, Refund.user_id == owner))
    credit = None
    if refund and refund.status == 'approved' and refund.credit_transaction_id:
        credit = db.scalar(select(Transaction).where(
            Transaction.id == refund.credit_transaction_id, Transaction.user_id == owner,
            Transaction.product_id == refund.destination_product_id,
            Transaction.category == 'refund', Transaction.status == 'completed',
            Transaction.amount_minor == refund.amount_minor, Transaction.currency == refund.currency))
    return {'request': {'id': case.id, 'kind': request_kind(case), 'status': case.status,
                       'updatedAt': case.updated_at.isoformat(), 'handling': handling_view(case)},
            'refund': {'id': refund.id, 'status': refund.status, 'creditTransactionId': credit.id if credit else None,
                       'amountMinor': refund.amount_minor, 'currency': refund.currency} if refund else None,
            'transactionId': case.transaction_id}


def case_status_navigation(data):
    """Navigate to the verified credit, or to the owned case awaiting it."""
    from .navigation import navigate_in_app
    credit = (data.get('refund') or {}).get('creditTransactionId')
    if credit:
        return navigate_in_app('movements', 'customer', filters={'transaction': credit})
    if data['request']['kind'] != 'claim':
        return navigate_in_app('requests', 'customer')
    return navigate_in_app('complaints', 'customer', case_id=data['request']['id'])


def case_status_reply(data, locale, *, speech=False):
    i = ('es', 'en', 'pt').index(locale)
    case = data['request']; refund = data.get('refund'); handling = case.get('handling') or {}
    stage = handling.get('stage', case['status']); identity = case['id']
    if refund and refund.get('creditTransactionId'):
        amount = f"{Decimal(refund['amountMinor']) / 100:,.2f} {refund['currency']}"
        result = (f"Tu reclamo {identity} ya tiene el reembolso realizado: {amount}. El abono está registrado en tu cuenta.",
                  f"Your complaint {identity} has been refunded: {amount}. The credit is recorded in your account.",
                  f"Sua reclamação {identity} já foi reembolsada: {amount}. O crédito está registrado em sua conta.")[i]
        if not speech:
            result += (' Referencia del abono: ', ' Credit reference: ', ' Referência do crédito: ')[i] + refund['creditTransactionId'] + '.'
        return result + (' Puedes ver el resultado en Mis reclamos y el abono en Movimientos.',
                         ' View the result in My complaints and the credit in Transactions.',
                         ' Veja o resultado em Minhas reclamações e o crédito em Movimentações.')[i]
    if refund and refund['status'] == 'rejected':
        return (f"La devolución de tu reclamo {identity} fue rechazada. No se registró un abono. Puedes revisar el motivo en Mis reclamos.",
                f"The refund for complaint {identity} was declined. No credit was recorded. Review the reason in My complaints.",
                f"A devolução da reclamação {identity} foi rejeitada. Nenhum crédito foi registrado. Consulte o motivo em Minhas reclamações.")[i]
    if stage == 'approved' or (refund and refund['status'] == 'approved'):
        return (f"Tu reclamo {identity} está aprobado, pero todavía no consta un reembolso realizado. Puedes seguir el siguiente paso en Mis reclamos.",
                f"Your complaint {identity} is approved, but no completed refund is recorded yet. Track the next step in My complaints.",
                f"Sua reclamação {identity} está aprovada, mas ainda não consta um reembolso realizado. Acompanhe o próximo passo em Minhas reclamações.")[i]
    if case['status'] == 'handed_off' and stage == 'received': stage = 'handed_off'
    labels = {'received': ('registrado', 'registered', 'registrada'), 'delivered': ('entregado a atención', 'delivered to support', 'entregue ao atendimento'),
              'in_review': ('en revisión', 'under review', 'em análise'), 'handed_off': ('derivado a atención', 'referred to support', 'encaminhada ao atendimento')}
    label = labels.get(stage, labels['received'])[i]
    if case.get('kind') != 'claim':
        return (f"Tu solicitud {identity} está {label}. Consulta el detalle en Mis solicitudes.", f"Your request {identity} is {label}. View the details in My requests.", f"Sua solicitação {identity} está {label}. Veja os detalhes em Minhas solicitações.")[i]
    return (f"Tu reclamo {identity} está {label}. Todavía no se ha registrado un reembolso. Puedes seguir su avance en Mis reclamos.",
            f"Your complaint {identity} is {label}. No refund has been recorded yet. Track its progress in My complaints.",
            f"Sua reclamação {identity} está {label}. Ainda não foi registrado um reembolso. Acompanhe o andamento em Minhas reclamações.")[i]
