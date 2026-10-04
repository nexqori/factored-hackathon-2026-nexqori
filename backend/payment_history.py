"""Bounded, same-owner payment comparisons. Descriptive evidence, not fraud scoring."""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select, func, exists
from .models import Transaction, BillPayment, PhoneBill, Refund
from .provider_updates import price_context, provider_context_text

DAYS = 180
LIMIT = 6
MINIMUM = 3
INCREASE_PERCENT = 20


def compare_payments(db, tx):
    result = _compare_payments(db, tx)
    notice = price_context(db, tx)
    if notice: result['providerNotice'] = notice
    return result


def _compare_payments(db, tx):
    result = {'windowDays': DAYS, 'limit': LIMIT, 'minimumSamples': MINIMUM,
              'thresholdPercent': INCREASE_PERCENT, 'transactionId': tx.id,
              'currency': tx.currency, 'samples': [], 'unusualIncrease': False}
    if tx.amount_minor >= 0 or tx.status == 'declined':
        return {**result, 'status': 'not-comparable', 'reason': 'not_a_charge'}
    linked = db.execute(select(BillPayment, PhoneBill).join(PhoneBill,
        (PhoneBill.id == BillPayment.bill_id) & (PhoneBill.user_id == BillPayment.user_id))
        .where(BillPayment.user_id == tx.user_id, BillPayment.transaction_id == tx.id)).first()
    refunded = exists(select(Refund.id).where(Refund.user_id == tx.user_id,
        Refund.transaction_id == Transaction.id, Refund.status == 'approved'))
    query = select(Transaction).where(Transaction.user_id == tx.user_id,
        Transaction.currency == tx.currency, Transaction.amount_minor < 0,
        Transaction.status == 'completed', Transaction.occurred_at < tx.occurred_at,
        Transaction.occurred_at >= tx.occurred_at - timedelta(days=DAYS), ~refunded)
    if linked:
        payment, bill = linked
        count = db.scalar(select(func.count()).select_from(BillPayment).where(
            BillPayment.user_id == tx.user_id, BillPayment.bill_id == bill.id))
        result['basis'] = 'bill-reference'
        if abs(tx.amount_minor) != bill.amount_minor or count != 1:
            reason = 'bill_amount_mismatch' if abs(tx.amount_minor) > bill.amount_minor and count == 1 else 'partial_payment'
            return {**result, 'status': 'not-comparable', 'reason': reason}
        single_payment = select(func.count(BillPayment.id)).where(
            BillPayment.user_id == tx.user_id, BillPayment.bill_id == PhoneBill.id).correlate(PhoneBill).scalar_subquery()
        query = query.join(BillPayment, (BillPayment.transaction_id == Transaction.id)
            & (BillPayment.user_id == tx.user_id)).join(PhoneBill,
            (PhoneBill.id == BillPayment.bill_id) & (PhoneBill.user_id == tx.user_id))
        query = query.where(PhoneBill.service_id == bill.service_id, PhoneBill.reference == bill.reference,
            PhoneBill.currency == tx.currency, PhoneBill.period < bill.period,
            -Transaction.amount_minor == PhoneBill.amount_minor, single_payment == 1)
    else:
        result['basis'] = 'merchant-product'
        # A card merchant alone cannot identify a phone line or subscription.
        has_receipt = exists(select(BillPayment.id).where(BillPayment.user_id == tx.user_id,
            BillPayment.transaction_id == Transaction.id))
        query = query.where(Transaction.product_id == tx.product_id,
            func.lower(func.trim(Transaction.merchant)) == tx.merchant.strip().lower(),
            Transaction.category == tx.category, ~has_receipt)
    rows = db.scalars(query.order_by(Transaction.occurred_at.desc(), Transaction.id.desc()).limit(LIMIT)).all()
    result['samples'] = [{'transactionId': r.id, 'amountMinor': abs(r.amount_minor),
                          'date': r.occurred_at.isoformat()} for r in rows]
    result['count'] = len(rows)
    if not rows: return {**result, 'status': 'none'}
    amounts = [abs(r.amount_minor) for r in rows]
    mean = Decimal(sum(amounts)) / len(amounts)
    rounded = int(mean.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    percent = (Decimal(abs(tx.amount_minor)) / mean - 1) * 100
    return {**result, 'status': 'sufficient' if len(rows) >= MINIMUM else 'limited',
            'averageMinor': rounded, 'minMinor': min(amounts), 'maxMinor': max(amounts),
            'differenceMinor': abs(tx.amount_minor) - rounded,
            'differencePercent': str(percent.quantize(Decimal('.1'), rounding=ROUND_HALF_UP)),
            'unusualIncrease': len(rows) >= MINIMUM and abs(tx.amount_minor) > max(amounts)
                              and percent >= INCREASE_PERCENT}


def context_comparison(state, reference):
    if not reference: return None
    for read in state.get('context', {}).get('bank_evidence', {}).get('reads', []):
        data = read.get('data', {})
        if read.get('tool') == 'read-transaction-evidence' and data.get('transaction', {}).get('id') == reference:
            return data.get('historyComparison')
    return None


def comparison_text(value, locale):
    history = _comparison_text(value, locale)
    notice = provider_context_text(value.get('providerNotice') if value else None, locale)
    return '\n\n'.join(part for part in (history,notice) if part)


def _comparison_text(value, locale):
    if not value or value.get('reason') == 'not_a_charge': return ''
    i = ('es', 'en', 'pt').index(locale)
    if value.get('reason') == 'bill_amount_mismatch':
        return ('El cargo supera el total del recibo vinculado. Hay que revisar esa diferencia antes de compararlo con otros recibos.',
                'The charge exceeds the linked bill total. That difference needs review before comparing it with other bills.',
                'A cobrança supera o total da conta vinculada. É preciso analisar essa diferença antes de compará-la com outras contas.')[i]
    if value['status'] == 'not-comparable':
        return ('Este pago incluye abonos; no lo comparé con recibos completos.',
                'This payment involves installments; I did not compare it with full bills.',
                'Este pagamento envolve pagamentos parciais; não o comparei com contas integrais.')[i]
    if not value['count']:
        return ('No encontré pagos anteriores comparables en los últimos 180 días.',
                'I found no comparable earlier payments in the last 180 days.',
                'Não encontrei pagamentos anteriores comparáveis nos últimos 180 dias.')[i]
    def money(number):
        text = f'{Decimal(number)/100:,.2f}'
        return value['currency'] + ' ' + (text.translate(str.maketrans({',':'.','.':','})) if locale == 'pt' else text)
    basis = (('la misma referencia de servicio', 'the same service reference', 'a mesma referência de serviço')
             if value['basis'] == 'bill-reference' else ('el mismo comercio y producto', 'the same merchant and product', 'o mesmo estabelecimento e produto'))[i]
    text = ('Historial de {basis}: últimos {count} pagos comparables en 180 días. Promedio {avg}; rango {low}–{high}. Diferencia de este cobro: {delta} ({pct} %).',
            'History for {basis}: last {count} comparable payments within 180 days. Average {avg}; range {low}–{high}. Difference for this charge: {delta} ({pct}%).',
            'Histórico de {basis}: últimos {count} pagamentos comparáveis em 180 dias. Média {avg}; faixa {low}–{high}. Diferença desta cobrança: {delta} ({pct}%).')[i]
    sign = '+' if value['differenceMinor'] > 0 else ''
    text = text.format(basis=basis, count=value['count'], avg=money(value['averageMinor']),
        low=money(value['minMinor']), high=money(value['maxMinor']),
        delta=sign+money(value['differenceMinor']), pct=('+' if Decimal(value['differencePercent'])>0 else '')+value['differencePercent'])
    if value['count'] < MINIMUM:
        text += (' Hay pocos antecedentes para establecer un importe habitual.', ' There is too little history to establish a usual amount.', ' Há poucos registros para estabelecer um valor habitual.')[i]
    elif value['unusualIncrease']:
        text += (' Supera el rango observado y merece revisión; no confirma un cobro incorrecto.', ' It exceeds the observed range and warrants review; this does not confirm an incorrect charge.', ' Supera a faixa observada e merece análise; isso não confirma uma cobrança incorreta.')[i]
    if value['basis'] == 'merchant-product':
        text += (' El comercio no permite confirmar que sean los mismos artículos o el mismo plan.', ' The merchant name does not establish identical purchases or the same plan.', ' O estabelecimento não confirma compras ou planos idênticos.')[i]
    return text
