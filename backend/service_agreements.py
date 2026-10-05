"""Compare recorded monthly conditions with the bill, inside the bank boundary.

These first conditions are explicit constructed fixtures. A tariff publication is
not an accepted contract amendment. Text supplied in chat is not stored as terms.
"""
import calendar
import re
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from .models import BillPayment, PhoneBill, ServiceAgreement


def agreement_context(db, tx):
    if tx.amount_minor >= 0 or tx.status == 'declined': return None
    linked=db.execute(select(BillPayment,PhoneBill).join(PhoneBill,
        (PhoneBill.id==BillPayment.bill_id)&(PhoneBill.user_id==BillPayment.user_id))
        .where(BillPayment.user_id==tx.user_id,BillPayment.transaction_id==tx.id)).first()
    if not linked: return None
    payment,bill=linked;receipt=payment.receipt or {}
    if not receipt.get('providerId') or not receipt.get('planId'): return None
    base={'status':'needs-review','paymentStatus':tx.status,'billAmountMinor':bill.amount_minor,
          'currency':bill.currency,'billingPeriod':bill.period,'verifiedExtras':False}
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',bill.period): return {**base,'reason':'invalid-period'}
    try:
        year,month=map(int,bill.period.split('-'))
        first=date(year,month,1);last=date(year,month,calendar.monthrange(year,month)[1])
    except ValueError: return {**base,'reason':'invalid-period'}
    rows=db.scalars(select(ServiceAgreement).where(ServiceAgreement.user_id==tx.user_id,
        ServiceAgreement.service_id==bill.service_id,ServiceAgreement.reference==bill.reference,
        ServiceAgreement.provider_id==receipt['providerId'],ServiceAgreement.plan_id==receipt['planId'],
        ServiceAgreement.currency==bill.currency,ServiceAgreement.currency==tx.currency,
        ServiceAgreement.valid_from<=last,ServiceAgreement.valid_until>=first).limit(2)).all()
    if not rows: return {**base,'reason':'no-applicable-agreement'}
    if len(rows)!=1: return {**base,'reason':'overlapping-conditions'}
    terms=rows[0]
    if terms.valid_from>first or terms.valid_until<last: return {**base,'reason':'partial-period'}
    difference=bill.amount_minor-terms.monthly_minor
    return {**base,'status':'above-base' if difference>0 else 'within-base','reason':None,
        'agreementId':terms.id,'version':terms.version,'source':terms.source,'planName':terms.plan_name,
        'validFrom':terms.valid_from.isoformat(),'validUntil':terms.valid_until.isoformat(),
        'monthlyMinor':terms.monthly_minor,'differenceMinor':difference,
        'taxesIncluded':terms.taxes_included,'extrasRequireApproval':terms.extras_require_approval,
        'publicationChangesAgreement':False,'automaticAction':False}


def agreement_text(value,locale,compact=False):
    if not value: return ''
    i=('es','en','pt').index(locale)
    if value['status']=='needs-review':
        return ('No hay condiciones vigentes únicas para todo el período; hace falta revisar el contrato.',
                'No single set of conditions covers the entire period; the contract needs review.',
                'Não há condições vigentes únicas para todo o período; o contrato precisa de análise.')[i]
    def money(number):
        amount=f'{Decimal(number)/100:.2f}'
        return value['currency']+' '+(amount.replace('.',',') if locale=='pt' else amount)
    base=money(value['monthlyMinor']);total=money(value['billAmountMinor']);delta=money(max(0,value['differenceMinor']))
    text=(f"Condiciones v{value['version']}: base mensual {base}; recibo {total}; diferencia sobre la base {delta}.",
          f"Conditions v{value['version']}: monthly base {base}; bill {total}; difference above base {delta}.",
          f"Condições v{value['version']}: base mensal {base}; conta {total}; diferença acima da base {delta}.")[i]
    if not compact:
        text+=(' Vigencia: ', ' Validity: ', ' Vigência: ')[i]+value['validFrom']+' – '+value['validUntil']+'.'
        if value['taxesIncluded']: text+=(' La base incluye impuestos.',' The base includes taxes.',' A base inclui impostos.')[i]
    if value['status']=='above-base':
        text+=(' Revisar extras autorizados y cambios aceptados; el aviso de tarifa no modifica por sí solo estas condiciones.',
               'Review authorized extras and accepted changes; a tariff notice alone does not amend these conditions.',
               'Revisar extras autorizados e mudanças aceitas; o aviso de tarifa não altera sozinho estas condições.')[i]
    else:
        text+=(' Estar dentro de la base no confirma que el cobro sea correcto.',
               'Being within the base does not confirm the charge is correct.',
               'Estar dentro da base não confirma que a cobrança esteja correta.')[i]
    return text
