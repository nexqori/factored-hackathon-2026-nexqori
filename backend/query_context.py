"""Conversation defaults and period summaries, resolved locally for the session owner.

No bank record or generated summary is placed in provider messages. Defaults are
suggestions for the document review form, never authority to generate a document.
"""
import calendar
import re
import unicodedata
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select, func
from .models import Product, RequestCase, Transaction, AuditEvent
from .navigation import navigate_in_app
from .conversation_context import changes_topic

ZONE = ZoneInfo('America/Mexico_City')
MONTHS = {
    'enero':1,'january':1,'janeiro':1,'febrero':2,'february':2,'fevereiro':2,
    'marzo':3,'march':3,'marco':3,'abril':4,'april':4,'mayo':5,'may':5,'maio':5,
    'junio':6,'june':6,'junho':6,'julio':7,'july':7,'julho':7,'agosto':8,'august':8,
    'septiembre':9,'setiembre':9,'september':9,'setembro':9,'octubre':10,'october':10,
    'outubro':10,'noviembre':11,'november':11,'novembro':11,'diciembre':12,'december':12,'dezembro':12,
}


def plain(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.lower()) if not unicodedata.combining(c))


def period(text, today):
    """Return None when unspecified; {} when a stated period needs clarification."""
    text = plain(text)
    dates = re.findall(r'\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{4}\b', text)
    if dates:
        try:
            parsed = [date.fromisoformat(d) if '-' in d else datetime.strptime(d,'%d/%m/%Y').date() for d in dates]
            if len(parsed) != 2 or parsed[0] > parsed[1] or (parsed[1]-parsed[0]).days > 366:return {}
            return {'startDate':parsed[0].isoformat(),'endDate':parsed[1].isoformat(),'allHistory':False}
        except ValueError:return {}
    signals = [bool(re.search(pattern, text)) for pattern in (
        r'\b(?:todo (?:el|mi) historial|all (?:my )?history|todo o historico)\b',
        r'\b(?:ultimos? 30 dias|last 30 days)\b',
        r'\b(?:ultimo mes|mes (?:pasado|anterior|passado)|last month|previous month)\b',
        r'\b(?:este mes|mes (?:actual|atual)|this month|current month)\b')]
    if sum(signals) > 1:return {}
    if signals[0]:
        if re.search(r'\b(?:no|not|nao|without|sin)\b(?:\s+\w+){0,3}\s+(?:todo|all)\b',text):return {}
        return {'allHistory':True}
    if signals[1]:start,end=today-timedelta(days=29),today
    elif signals[2]:
        end=today.replace(day=1)-timedelta(days=1);start=end.replace(day=1)
    elif signals[3]:start,end=today.replace(day=1),today
    else:
        months = '|'.join(MONTHS)
        named_range = re.search(r'\b(\d{1,2})\s*(?:al|a|to|ate|-)\s*(\d{1,2})\s+(?:de\s+)?('+months+r')\s+(?:de\s+)?(20\d{2})\b', text)
        english_range = re.search(r'\b('+months+r')\s+(\d{1,2})\s*(?:to|-)\s*(\d{1,2})(?:,)?\s+(20\d{2})\b', text)
        match=re.search(r'\b('+months+r')\s+(?:de\s+)?(20\d{2})\b',text)
        if named_range or english_range:
            day1, day2, month, year = named_range.groups() if named_range else (english_range[2],english_range[3],english_range[1],english_range[4])
            try:start,end=date(int(year),MONTHS[month],int(day1)),date(int(year),MONTHS[month],int(day2))
            except ValueError:return {}
            if start>end:return {}
        elif match:
            if len(re.findall(r'\b(?:'+months+r')\b', text)) != 1:return {}
            # A partly understood day range must not silently widen to a month.
            if re.search(r'(?<![\w-])\d{1,2}(?![\w-])', text):return {}
            month,year=MONTHS[match[1]],int(match[2]);start=date(year,month,1);end=date(year,month,calendar.monthrange(year,month)[1])
        elif re.search(r'\b(?:periodos?|periods?|semanas?|weeks?|mes(?:es)?|months?|trimestres?|quarters?|anos?|years?|dias?|days?|hoy|ayer|today|yesterday|hoje|ontem|'+months+r')\b|\b\d{2,4}[-/]\d{1,2}',text):return {}
        else:return None
    return {'startDate':start.isoformat(),'endDate':end.isoformat(),'allHistory':False}


def resolve_defaults(messages, products, requests=(), *, today=None, previous=None):
    today=today or datetime.now(ZONE).date(); draft=dict(previous or {})
    for message in messages:
        if message.get('role') != 'user':continue
        if changes_topic(message.get('content','')):draft={}
        text=plain(message.get('content',''))
        kind = ('statement' if re.search(r'\b(?:movimientos|movements|transactions|movimentacoes|estado de cuenta|statements?|extratos?)\b',text)
                else 'requests_summary' if re.search(r'\b(?:solicitudes|requests|solicitacoes|reclamos|complaints|reclamacoes|pedidos)\b',text)
                else 'products_summary' if re.search(r'\b(?:productos|products|produtos|tarjetas|cards|cartoes)\b',text) else None)
        if kind and kind != draft.get('kind'):
            # Account and period survive a clarification of the document type;
            # request references and product references are separate domains.
            if kind=='requests_summary' or draft.get('kind')=='requests_summary':
                draft={key:value for key,value in draft.items() if key not in ('scope','productId','requestId')}
            draft.update(kind=kind);draft.setdefault('scope','all')
        found=period(text,today)
        if found is not None:
            for key in ('startDate','endDate','allHistory'):draft.pop(key,None)
            draft.update(found)
            if not draft.get('kind'):draft.update(kind='statement',scope='all')
        if re.search(r'todas? (?:mis |las )?(?:cuentas|productos|solicitudes)|all (?:my )?(?:accounts|products|requests)|todos? (?:os |meus )?(?:produtos|pedidos)|todas? (?:as |minhas )?contas',text):
            draft['scope']='all';draft.pop('productId',None);draft.pop('requestId',None)
        # Only an explicitly stated, unique last-four or exact own reference selects data.
        matches4=re.findall(r'(?:termina(?:da|cion)?|ending|final)[^\d\n]{0,20}(\d{4})\b',text)
        matches4+=re.findall(r'\b(?:cuenta|account|conta|tarjeta|card|cartao)\s*(?:(?:numero|number|nro)\s*)?[#*· ]*(\d{4})\b(?!-\d)',text)
        if matches4:matches4+=re.findall(r'\b(?:y|and|e|o|or|ou)\s+(?:la |a |the )?(\d{4})\b',text)
        exact_refs=re.findall(r'\b(?:account|savings|card)-[a-z0-9_-]+\b',text)
        exact_refs += [p.id for p in products if re.search(r'(?<![\w-])'+re.escape(p.id.lower())+r'(?![\w-])',text)]
        other_account=re.search(r'\b(?:otra|other|another|outra)\s+(?:cuenta|account|conta|tarjeta|card|cartao)\b',text)
        explicit_account = re.search(r'\b(?:mi|my|minha|esta|esa|this|essa)\s+(?:cuenta|account|conta|tarjeta|card|cartao)\b',text)
        numeric_reference=re.search(r'\b(?:cuenta|account|conta|tarjeta|card|cartao)\s*(?:(?:numero|number|nro)\s*)?#?\s*(\d[\d -]{4,})',text)
        if matches4 or exact_refs or explicit_account or other_account or numeric_reference:
            selected_before=draft.get('productId') if draft.get('scope')=='selected' else None
            draft['scope']='selected';draft.pop('productId',None)
            ids=set(); ambiguous=False
            for last4 in set(matches4):
                owned=[p for p in products if p.last4==last4]
                if len(owned)!=1:ambiguous=True
                else:ids.add(owned[0].id)
            for ref in set(exact_refs):
                owned=next((p for p in products if p.id.lower()==ref.lower()),None)
                if not owned:ambiguous=True
                else:ids.add(owned.id)
            if not matches4 and not exact_refs:
                # "My account" does not identify one account among several.
                owned=[p for p in products if p.type in ('account','savings')]
                if re.search(r'\b(?:tarjeta|card|cartao)\b',text):owned=[p for p in products if p.type=='card']
                if not other_account and not numeric_reference:
                    if selected_before in {p.id for p in owned}:ids.add(selected_before)
                    elif len(owned)==1:ids.add(owned[0].id)
            if len(ids)==1 and not ambiguous:draft['productId']=next(iter(ids))
        refs=re.findall(r'\bnq-[a-z0-9]+\b',text)
        if refs or re.search(r'\bnq-',text):
            draft.update(kind='requests_summary',scope='selected');draft.pop('requestId',None)
            matches=[r for r in requests if r.id.lower() in set(refs)]
            if len(set(refs))==1 and len(matches)==1:draft['requestId']=matches[0].id
    if draft.get('kind') != 'statement':
        for key in ('startDate','endDate','allHistory'):draft.pop(key,None)
    if draft.get('kind')=='requests_summary':draft.pop('productId',None)
    else:draft.pop('requestId',None)
    # Saved references are revalidated as well as new messages; never trust a
    # stale snapshot to turn an unavailable selection into an unfiltered query.
    if draft.get('productId') and draft['productId'] not in {p.id for p in products}:
        draft.pop('productId');draft['scope']='selected'
    if draft.get('requestId') and draft['requestId'] not in {r.id for r in requests}:
        draft.pop('requestId');draft['scope']='selected'
    missing=[]
    if not draft.get('kind'):missing.append('kind')
    if draft.get('kind')=='statement' and not (draft.get('allHistory') or draft.get('startDate') and draft.get('endDate')):missing.append('period')
    if draft.get('scope')=='selected' and not draft.get('requestId' if draft.get('kind')=='requests_summary' else 'productId'):missing.append('selection')
    return {'draft':draft,'missing':missing}


def conversation_defaults(db, owner, state, *, refresh=False):
    products=db.scalars(select(Product).where(Product.user_id==owner)).all()
    requests=db.scalars(select(RequestCase).where(RequestCase.user_id==owner)).all()
    saved=state.get('queryDefaults')
    messages=state.get('messages',[])
    if saved is not None:
        messages=[m for m in messages if m.get('role')=='user'][-1:] if refresh else []
    result=resolve_defaults(messages,products,requests,previous=saved)
    if not result['draft'].get('kind'):
        inferred={'account-activity':'statement','account-balance':'products_summary','my-cards':'products_summary','request-status':'requests_summary'}.get(state['context'].get('intent'))
        if inferred:result=resolve_defaults([],products,requests,previous={**result['draft'],'kind':inferred,'scope':result['draft'].get('scope','all')})
    return result


def apply_query_context(db, owner, conversation_id, state, locale):
    ctx=state['context'];intent=ctx.get('intent')
    if ctx.get('triage',{}).get('family')!='query' or intent not in ('documents','account-activity','account-balance','my-cards','request-status'):return None
    had_defaults='queryDefaults' in state
    result=conversation_defaults(db,owner,state,refresh=True)
    draft=result['draft'];state['queryDefaults']=draft
    signal_messages=[m for m in state.get('messages',[]) if m.get('role')=='user']
    for item in (signal_messages[-1:] if had_defaults else signal_messages):
        signal=period(item.get('content',''),datetime.now(ZONE).date())
        if signal is not None:state['queryPeriodUnclear']=not bool(signal)
    i=('es','en','pt').index(locale)
    if intent=='documents':
        kinds={'statement':('estado de cuenta','account statement','extrato'),'products_summary':('resumen de productos','product summary','resumo de produtos'),'requests_summary':('seguimiento de solicitudes','request tracking','acompanhamento de solicitações')}
        if draft.get('kind'):
            name=kinds[draft['kind']][i]
            span=f" {draft['startDate']} — {draft['endDate']}" if draft.get('startDate') else ''
            ctx['reply']=(f'Preparé los datos para tu {name}{span}. Abre Preparar PDF para revisar la selección y completar lo que falte antes de generarlo.',f'I prepared the details for your {name}{span}. Open Prepare PDF to review the selection and fill in any missing information before generating it.',f'Preparei os dados para seu {name}{span}. Abra Preparar PDF para revisar a seleção e preencher o que falta antes de gerar.')[i]
        return result
    if intent!='account-activity':return result
    # An unresolved stated scope/period must not silently fall back to all records.
    if 'selection' in result['missing'] or state.get('queryPeriodUnclear'):
        ctx['reply']=('Indícame la cuenta y las fechas exactas que quieres revisar para aplicar los filtros correctos.','Tell me the account and exact dates to apply the right filters.','Informe a conta e as datas exatas para aplicar os filtros corretos.')[i]
        ctx['navigation']=None;return result
    if not draft.get('startDate') and not draft.get('productId') and not draft.get('allHistory'):return result
    query=select(Transaction).where(Transaction.user_id==owner)
    filters={}
    if draft.get('productId'):
        query=query.where(Transaction.product_id==draft['productId']);filters['product']=draft['productId']
    if draft.get('startDate'):
        start=datetime.combine(date.fromisoformat(draft['startDate']),time.min,ZONE).astimezone(timezone.utc)
        end=datetime.combine(date.fromisoformat(draft['endDate'])+timedelta(days=1),time.min,ZONE).astimezone(timezone.utc)
        query=query.where(Transaction.occurred_at>=start,Transaction.occurred_at<end)
        filters.update(start=draft['startDate'],end=draft['endDate'])
    sub=query.subquery()
    totals=db.execute(select(sub.c.currency,sub.c.status,func.count(),func.sum(sub.c.amount_minor)).group_by(sub.c.currency,sub.c.status)).all()
    count=sum(row[2] for row in totals)
    period_label=(draft.get('startDate','')+' — '+draft.get('endDate','')).strip(' —')
    heading=(f'Encontré {count} movimientos'+(f' del {period_label}' if period_label else '')+'.',f'I found {count} transactions'+(f' for {period_label}' if period_label else '')+'.',f'Encontrei {count} movimentações'+(f' de {period_label}' if period_label else '')+'.')[i]
    # Show completed income and outflow separately; pending operations are not settled.
    amounts=db.execute(select(sub.c.currency,func.sum(sub.c.amount_minor)).where(sub.c.status=='completed').group_by(sub.c.currency,sub.c.amount_minor<0)).all()
    lines=[heading]
    for currency,amount in amounts:
        name=(('Pagos y salidas','Payments and outflows','Pagamentos e saídas') if amount<0 else ('Entradas','Incoming funds','Entradas'))[i]
        displayed=f'{abs(Decimal(amount))/100:,.2f}'
        if locale=='pt':displayed=displayed.translate(str.maketrans({',':'.','.':','}))
        lines.append(f'{name}: {currency} {displayed}')
    pending=sum(r[2] for r in totals if r[1]=='pending')
    if pending:lines.append((f'{pending} pendientes de procesamiento.',f'{pending} pending processing.',f'{pending} pendentes de processamento.')[i])
    lines.append(('Abrí Movimientos con esos filtros. Puedes revisar cada operación o preparar el PDF de este período.','I opened Transactions with these filters. Review each transaction or prepare a PDF for this period.','Abri Movimentações com esses filtros. Revise cada operação ou prepare o PDF deste período.')[i])
    ctx['reply']='\n\n'.join(lines);ctx['navigation']=navigate_in_app('movements','customer',filters=filters or None)
    db.add(AuditEvent(id=str(uuid4()),user_id=owner,actor_id=owner,conversation_id=conversation_id,action='tool_filtered_transactions'))
    db.flush()
    return result
