"""Deterministic call findings. No model text, merchant names, raw logs or secrets in speech.

The customer requested spoken findings: only the selected record's amount/date/status,
aggregate comparison and owned case number can reach the voice provider. Raw evidence
and history remain on the authenticated screen, outside text/classification models.
"""
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from .transaction_context import transaction_evidence


def pick(locale, es, en, pt): return (es,en,pt)[('es','en','pt').index(locale)]


def money(value, currency, locale):
    if type(value) is not int or abs(value)>10**12 or currency not in ('MXN','USD','COP','BRL'):
        return None
    amount=f'{value/100:.2f}'
    return amount + ' ' + ('pesos mexicanos' if currency=='MXN' and locale in ('es','pt') else currency)


def registered_summary(db, owner, identity, locale):
    if not isinstance(identity, str) or not re.fullmatch(r'NQ-[A-Za-z0-9-]{1,61}', identity): return None
    from .case_followup import read_case_status, case_status_reply
    from fastapi import HTTPException
    try:
        data = read_case_status(db, owner, identity)
    except HTTPException as error:
        if error.status_code == 404: return None
        raise
    return case_status_reply(data, locale, speech=True)


def presentation(db, owner, reply, locale):
    if 'appCommand' in reply:
        # Local commands preserve the case, but must not repeat its old findings.
        command=reply.get('appCommand') or {}; kind=command.get('type')
        choices={
            'logout':('Voy a cerrar tu sesión y la llamada.', 'I will sign you out and end the call.', 'Vou encerrar sua sessão e a chamada.'),
            'set_locale':('He solicitado cambiar el idioma de la pantalla. La llamada conserva su idioma inicial.', 'I requested the screen language change. This call keeps its starting language.', 'Solicitei a alteração do idioma da tela. Esta chamada mantém o idioma inicial.'),
            'prepare_card':('Abro Tarjetas para que revises la selección y confirmes tu identidad. No compartas contraseñas ni códigos por voz.', 'I am opening Cards so you can review the selection and confirm your identity. Do not share passwords or codes by voice.', 'Abro Cartões para você revisar a seleção e confirmar sua identidade. Não compartilhe senhas nem códigos por voz.'),
        }
        if kind in choices:summary=pick(locale,*choices[kind])
        elif reply.get('navigation'):
            from .assistant import NAV_LABELS
            screen=NAV_LABELS[locale].get(reply['navigation'].get('destination'))
            if not screen:screen=pick(locale,'Mis documentos','My documents','Meus documentos')
            summary=pick(locale,f'Te muestro {screen}. Tu caso sigue guardado.',f'I am showing {screen}. Your case is preserved.',f'Mostro {screen}. Seu caso continua salvo.')
        else:
            from .chat_language import language_reply
            summary=language_reply(locale)['text']
        return {'summary':summary,'comparison':None}
    flow=reply.get('flow') or {}
    if reply.get('guard',{}).get('status') in ('blocked','uncertain','unavailable'):
        from .prompt_guard import guard_message
        return {'summary':guard_message(reply['guard']['status'],locale),'comparison':None}
    registered=registered_summary(db,owner,flow.get('requestId') or flow.get('selectedRequestId'),locale)
    if flow.get('state')=='provider_unavailable':return None
    proposed=flow.get('suggestedTransaction') or {}
    reference=proposed.get('id') or reply.get('conversation',{}).get('transactionId')
    if not reference or (flow.get('transactionSearch') or {}).get('kind')=='browse':
        return {'summary':registered,'comparison':None} if registered else None
    evidence=transaction_evidence(db,owner,reference)
    tx=evidence['transaction']; c=evidence.get('historyComparison') or {}
    amount=money(abs(tx['amountMinor']),tx['currency'],locale)
    if amount is None:return None
    at=datetime.fromisoformat(tx['date'])
    if at.tzinfo is None:at=at.replace(tzinfo=ZoneInfo('UTC'))
    date=at.astimezone(ZoneInfo('America/Mexico_City')).strftime('%d/%m/%Y')
    status=pick(locale,{'pending':'pendiente','completed':'completado','declined':'rechazado'},
                {'pending':'pending','completed':'completed','declined':'declined'},
                {'pending':'pendente','completed':'concluído','declined':'recusado'})[tx['status']]
    text=pick(locale,f'Encontré el pago de {amount}, del {date}; está {status}.',
              f'I found the payment of {amount}, dated {date}; it is {status}.',
              f'Encontrei o pagamento de {amount}, de {date}; está {status}.')
    result={'summary':text,'transactionId':reference,'comparison':None}
    if proposed:
        result['summary']+=pick(locale,' ¿Es el que quieres revisar?',' Is that the payment you want to review?',' É esse que deseja analisar?')
        return result
    agreement=c.get('serviceAgreement') or {}; comparison=None
    if agreement.get('status') in ('above-base','within-base'):
        base=agreement['monthlyMinor'];current=agreement['billAmountMinor'];delta=current-base
        comparison={'basis':'agreement','baselineMinor':base,'currentMinor':current,'differenceMinor':delta,
                    'currency':tx['currency'],'count':c.get('count',0),'verdict':'above-base' if delta>0 else 'within-base'}
        text+=pick(locale,f" La base del plan es {money(base,tx['currency'],locale)}; el recibo {'la supera en '+money(delta,tx['currency'],locale) if delta>0 else 'no la supera'}.",
                   f" The plan base is {money(base,tx['currency'],locale)}; the bill {'exceeds it by '+money(delta,tx['currency'],locale) if delta>0 else 'does not exceed it'}.",
                   f" A base do plano é {money(base,tx['currency'],locale)}; a conta {'supera essa base em '+money(delta,tx['currency'],locale) if delta>0 else 'não supera essa base'}.")
        text+=pick(locale,' Falta verificar extras o cambios aceptados.',' Accepted extras or plan changes still need verification.',' Ainda é preciso verificar extras ou alterações aceitas.')
    elif c.get('status')=='sufficient':
        base=c['averageMinor'];delta=abs(tx['amountMinor'])-base
        comparison={'basis':'history','baselineMinor':base,'currentMinor':abs(tx['amountMinor']),'differenceMinor':delta,
                    'currency':tx['currency'],'count':c['count'],'verdict':'unusual' if c['unusualIncrease'] else 'comparable'}
        text+=pick(locale,f" Tus {c['count']} pagos anteriores promedian {money(base,tx['currency'],locale)}.",
                   f" Your {c['count']} previous payments average {money(base,tx['currency'],locale)}.",
                   f" Seus {c['count']} pagamentos anteriores têm média de {money(base,tx['currency'],locale)}.")
        text+=pick(locale,' El aumento merece revisión; no confirma un error.' if c['unusualIncrease'] else ' El historial no muestra un aumento inusual; podemos revisar lo ocurrido.',
                   ' The increase warrants review; it does not prove an error.' if c['unusualIncrease'] else ' The history shows no unusual increase; we can still review what happened.',
                   ' O aumento merece análise; não confirma um erro.' if c['unusualIncrease'] else ' O histórico não indica aumento incomum; podemos analisar o ocorrido.')
    else:
        text+=pick(locale,' No tengo suficientes antecedentes comparables para confirmar un cobro excesivo.',
                   ' There is not enough comparable history to establish an overcharge.',
                   ' Não há histórico comparável suficiente para confirmar cobrança excessiva.')
    if registered:
        text=registered
    elif flow.get('canRegister'):
        text+=pick(locale,' Te propongo enviarlo a un supervisor. Revisa el resumen y confirma el registro aquí; tendrás un número de expediente en Mis reclamos.',
                   ' I suggest sending it for supervisor review. Review the summary and confirm here to receive a case number in My complaints.',
                   ' Proponho encaminhar para análise de um supervisor. Revise o resumo e confirme aqui para receber um protocolo em Minhas reclamações.')
        if tx['status']=='pending':text+=pick(locale,' El pago sigue pendiente; no he devuelto ni cancelado dinero.',
                ' The payment is still pending; I have not refunded or cancelled it.',' O pagamento segue pendente; não efetuei devolução ou cancelamento.')
    elif 'difference' in flow.get('missing_fields',[]):
        text+=pick(locale,' ¿Reconoces algún extra o cambio de plan que pueda explicarlo?' if comparison and comparison['basis']=='agreement' else '¿Qué importe esperabas pagar?',
                   ' Do you recognize an extra or plan change that could explain it?' if comparison and comparison['basis']=='agreement' else ' What amount did you expect to pay?',
                   ' Reconhece algum extra ou alteração do plano que explique isso?' if comparison and comparison['basis']=='agreement' else ' Qual valor esperava pagar?')
    else:
        text+=pick(locale,' ¿El problema es el importe, que no lo reconoces o que no se completó?',
                   ' Is the issue the amount, a payment you do not recognize, or one that did not complete?',
                   ' O problema é o valor, um pagamento que não reconhece ou que não foi concluído?')
    return {**result,'summary':text,'comparison':comparison}
