"""Natural read-only replies from audited facts, composed inside the bank."""
from decimal import Decimal
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def query_answer(intent, evidence, locale):
    i=('es','en','pt').index(locale)
    if intent=='documents':
        return ('Puedo preparar un estado de cuenta informativo, un resumen de productos o el seguimiento de tus solicitudes en PDF. Abre Preparar PDF y elige el documento, la cuenta y el periodo que necesitas.',
                'I can prepare an informational account statement, a product summary or request tracking as a PDF. Open Prepare PDF and choose the document, account and period you need.',
                'Posso preparar um extrato informativo, um resumo de produtos ou o acompanhamento de suas solicitações em PDF. Abra Preparar PDF e escolha o documento, a conta e o período que precisa.')[i]
    reads=evidence.get('reads',[])
    if intent=='account-activity':
        data=next((r['data'] for r in reads if r['tool']=='read-transactions'),{})
        rows=data.get('transactions',[])
        if not rows:return ('No hay movimientos registrados en tu cuenta.','There are no transactions in your account.','Não há movimentações registradas na sua conta.')[i]
        lines=[('Estos son tus últimos movimientos:','These are your latest transactions:','Estas são suas últimas movimentações:')[i]]
        states={'completed':('Realizado','Completed','Concluído'),'pending':('Pendiente','Pending','Pendente'),'declined':('Rechazado','Declined','Recusado')}
        for r in rows[:5]:
            dt=datetime.fromisoformat(r['date']);dt=dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            day=dt.astimezone(ZoneInfo('America/Mexico_City')).strftime('%d/%m/%Y')
            lines.append(f"{day} · {r['merchant']} · {r['currency']} {Decimal(r['amountMinor'])/100:,.2f} · {states[r['status']][i]} · {r['id']}")
        lines.append(('Puedes ver el detalle en Movimientos o preparar un PDF por cuenta y periodo.','View the details in Transactions or prepare a PDF for an account and period.','Veja os detalhes em Movimentações ou prepare um PDF por conta e período.')[i])
        return '\n\n'.join(lines)
    if intent=='my-cards':
        rows=next((r['data']['cards'] for r in reads if r['tool']=='read-cards'),[])
        if not rows:return ('No hay tarjetas asociadas a tu cuenta.','There are no cards linked to your account.','Não há cartões vinculados à sua conta.')[i]
        labels={'active':('Activa','Active','Ativo'),'blocked':('Bloqueada','Blocked','Bloqueado')}
        return '\n'.join(f"•••• {r['last4']} · {labels[r['status']][i]}" for r in rows)
    return None
