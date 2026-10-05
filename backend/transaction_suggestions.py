"""Small, deterministic lookup of a possible movement, never evidence or consent.

Only the authenticated bank adapter calls this after classification. Candidate
records and bank-enriched replies must stay outside provider message history.
"""
import re
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from decimal import Decimal
from zoneinfo import ZoneInfo
from .catalog import SERVICES, normalize

FINANCIAL_PROBLEMS = {'unrecognized-charge', 'incorrect-charge', 'payment-status'}
TOPICS = {
    'phone-bill': ('celular telefono telefonia movil celualar phone mobile cell telephone telefone', None),
    'internet-bill': ('internet wifi broadband', None),
    'transfer': ('transferencia transfer transferencia', 'transfer'),
}
YES = {'si', 'si es ese', 'si es este', 'ese mismo', 'es ese', 'yes', 'yes that one',
       'yes this one', 'that one', 'sim', 'sim e esse', 'e esse', 'esse mesmo',
       'si ese', 'si es esa', 'correcto', 'exacto', 'si correcto', 'yes correct', 'sim e essa'}
NO = {'no', 'no es ese', 'no es otro', 'es otro', 'otro', 'no es este', 'no not that one', 'no another one', 'another',
      'not that one', 'nao', 'nao e esse', 'nao e outro', 'outro', 'e outro'}


def submit_review(message):
    """Explicit spoken assent, scoped later to a displayed current draft.

    Bare yes selects a movement, never submits. No substring/fuzzy matching.
    A comma after No answers the prior extras question; without it we refuse.
    """
    text = normalize(message).strip()
    text = re.sub(r'^no,\s*', '', text)
    text = ' '.join(re.findall(r'\w+', text))
    return bool(re.fullmatch(
        r'(?:(?:si|correcto|ok|yes|sim) )?'
        r'(?:confirmar y enviar|confirmo el envio|confirma y envia|envialo|enviemoslo(?: a revision)?|'
        r'envia (?:el|mi) reclamo|send it|confirm and send|submit (?:the|my) complaint|'
        r'confirmar e enviar|confirmo o envio|envie a reclamacao)'
        r'(?: por favor| please)?', text))


def review_requested(message):
    """Request a review form only; never authorization to register or pay."""
    if submit_review(message): return True
    text = ' '.join(re.findall(r'\w+', normalize(message)))
    if re.search(r"\b(?:no|not|nao|never|don t|do not)\s+(?:quiero|deseo|necesito|quero|want|prepare|file|submit|request|hagas|prepares|registre|registres|solicites|pidas|pongas)\b", text):
        return False
    return bool(re.search(
        r"\b(?:(?:hacerme|hazme|haz|hacer|prepara|preparar|registrar|crear|presentar|enviar|poner|ponerme|solicitar|pedir|tramitar|levantar|iniciar)\s+(?:me\s+)?(?:un|una|el|la|mi|este|esta)?\s*(?:reclamo|queja|reembolso|devolucion|solicitud de devolucion|solicitud de reembolso)|"
        r"(?:prepare|file|create|submit|open|request)\s+(?:a|the|my|this)\s+(?:complaint|claim|refund)|"
        r"(?:preparar|prepare|registrar|registre|criar|abrir|enviar|pedir|solicitar)\s+(?:um|uma|o|a|minha|meu|esta)\s+(?:reclamacao|reembolso|devolucao))\b", text))


def review_only(message):
    """Opening the current review is not a new extraction of known details."""
    if submit_review(message): return True
    value = ' '.join(re.findall(r'\w+', normalize(message)))
    return bool(re.fullmatch(
        r"(?:(?:por favor|please|por favor) )?(?:(?:puedes|podrias|quiero|quisiera|necesito|can you|could you|i want to|pode|quero) )?"
        r"(?:(?:hacerme|hazme|haz|hacer|prepara|preparar|registrar|crear|presentar|enviar) (?:un|una|el|la|mi|este|esta) (?:reclamo|queja)|"
        r"(?:prepare|file|create|submit|open) (?:a|the|my|this) (?:complaint|claim)|"
        r"(?:preparar|prepare|registrar|registre|criar|abrir|enviar) (?:uma|a|minha|esta) reclamacao)"
        r"(?: por favor| please)?", value))


def confirmation(message):
    # Selecting the one outstanding owned proposal is not banking consent.
    # Speech often combines assent, the symptom and a request for the review.
    value = ' '.join(re.findall(r'\w+', normalize(message)))
    if value in YES: return 'yes'
    if value in NO: return 'no'
    if re.search(r"\b(?:otro|otra|another|different|outro|outra|quizas|tal vez|maybe|perhaps|talvez|if|ejemplo|example|exemplo|dije|dijo|said|disse)\b|"
                 r"\b(?:no es|no estoy segur|not that|not sure|nao e|nao tenho certeza)", value):
        return None
    # This explicit referent is safe even if an earlier transcript fragment
    # precedes it (e.g. 'pasar Sí, no reconozco ese cobro').
    explicit = (r"\bsi no reconozco (?:ese|este) (?:cobro|cargo|pago|movimiento)\b|"
                r"\byes i (?:do not|don t) recognize (?:that|this) (?:charge|payment|transaction)\b|"
                r"\bsim nao reconheco (?:essa|esta|esse|este) (?:cobranca|pagamento|movimentacao)\b")
    if re.search(explicit, value): return 'yes'
    # Resolve the customer's assent independently from what they want to do
    # next. A review request is not a prerequisite for confirming a proposal.
    if re.match(r"^(?:(?:si|correcto|exacto) (?:es )?(?:ese|este|esa|esta)|(?:ese|este|esa|esta) (?:es|mismo|misma)|yes (?:that|this)(?: is| one)?|(?:that|this) is the one|sim (?:e )?(?:esse|este|essa|esta)|(?:esse|essa) mesmo)\b", value):
        return 'yes'
    return None


def words(value):
    return set(re.findall(r'[a-z0-9]+', normalize(value)))


def related(left, right):
    return any(a == b or (min(len(a), len(b)) >= 5 and SequenceMatcher(None, a, b).ratio() >= .86)
               for a in left for b in right)


def local_date(value):
    at = datetime.fromisoformat(value)
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return at.astimezone(ZoneInfo('America/Mexico_City')).date().isoformat()


def browse_request(message):
    text = normalize(message)
    if re.search(r"\b(?:no|not|nao|never|don'?t)\s+(?:me\s+)?(?:muestr\w*|mostrar\w*|abras|abrir|show|open|list|ver)\b", text):
        return False
    return bool(re.search(r'\b(?:muestra\w*|mostrar\w*|ver|abre|abrir|llevame|show|list|open|see|mostr\w*|veja)\b', text)
                and re.search(r'\b(?:movimientos?|transacciones?|pagos?|cargos?|transactions?|payments?|charges|movimentacoes|pagamentos?)\b', text))


def search_clues(messages, locale='es'):
    """Latest explicit clue wins per field; short replies retain earlier clues.

    All values only narrow an owned read. They never bind a transaction or fill
    verified facts. Expected plan prices are not mistaken for charged amounts.
    """
    clues = {}
    for entry in reversed(messages):
        if entry['role'] != 'user':
            continue
        text = normalize(entry['content']); tokens = words(text)
        reference = re.search(r'\btx-[a-z0-9-]+\b', text, re.I)
        if reference and 'q' not in clues:
            # A precise reference supersedes an earlier guess about its status.
            return {'q':reference.group().upper()}
        if 'q' not in clues and 'category' not in clues:
            for service, (aliases, category) in TOPICS.items():
                if related(tokens, words(aliases)):
                    if category: clues['category'] = category
                    else: clues['q'] = SERVICES[service]['provider']
                    break
        if 'status' not in clues:
            if re.search(r'\b(?:pendiente|pending|pendente)\b', text): clues['status'] = 'pending'
            elif re.search(r'\b(?:fallid[oa]|fallo|rechazad[oa]|failed|declined|rejected|falh[oa]|falhou|recusad[oa])\b', text): clues['status'] = 'declined'
        if 'date' not in clues:
            found = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', text)
            parts = found.groups() if found else None
            if not parts:
                found = re.search(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', text)
                if found:
                    a,b,y=found.groups();parts=(y,a,b) if locale=='en' else (y,b,a)
            if parts:
                try: clues['date'] = date(*map(int,parts)).isoformat()
                except ValueError: pass
        if 'amountMinor' not in clues:
            number=r'(\d+(?:[.,]\d{3})*(?:[.,]\d{1,2})?)'
            amount = re.search(r'\b(?:cobraron|cobro|cargo|pague|pago|charged|charge|paid|payment|cobraram|cobranca|paguei|pagamento)(?:\s+(?:de|por|for|of|me|es|fue))*\s+\$?\s*'+number+r'(?![\d.,])',text)
            if not amount:
                amounts=list(re.finditer(r'(?<![\d.,])'+number+r'\s*(?:mxn|pesos|dolares|dollars|reais)\b',text))
                if len(amounts)==1 and not re.search(r'\b(?:esper\w*|plan|habitual|expected|usually|plano)\b',text): amount=amounts[0]
            if amount:
                value=int(Decimal(re.sub(r'[.,](?=\d{3}(?:[.,]|$))','',amount.group(1)).replace(',','.'))*100)
                if 0 < value <= 10**12: clues['amountMinor']=value
        # An explicit new topic bounds previous clues, even when it has no amount.
        from .conversation_context import changes_topic
        if changes_topic(entry['content']): break
    return clues


def search_navigation(clues, candidate=None):
    if candidate: return {'transaction':candidate['id']}
    filters={k:clues[k] for k in ('q','status','category','amountMinor') if k in clues}
    if 'date' in clues: filters.update(start=clues['date'],end=clues['date'])
    return filters or None


def search_reply(locale, *, browsing=False):
    index=('es','en','pt').index(locale)
    if browsing:
        return ('Te muestro tus movimientos para que ubiquemos el correcto. Puedes indicarme el comercio, el importe o la referencia. Conservaremos el problema que estábamos revisando.',
                'Here are your transactions so we can find the right one. Tell me the merchant, the amount or the reference. We will keep the issue we were reviewing.',
                'Mostro suas movimentações para encontrarmos a correta. Diga o estabelecimento, o valor ou a referência. Vamos manter o problema que estávamos analisando.')[index]
    return ('No encontré un cargo que coincida con esas pistas. Te muestro la búsqueda en Movimientos. ¿Recuerdas el comercio o prefieres ver todos tus movimientos?',
            'I found no charge matching those clues. The search is shown in Transactions. Do you remember the merchant, or would you prefer to see all your transactions?',
            'Não encontrei uma cobrança com essas informações. A busca aparece em Movimentações. Lembra do estabelecimento ou prefere ver todas as movimentações?')[index]


def choose(transactions, messages, dismissed, locale='es'):
    # Gateway already sorts newest first and bounds the owner's results to 20.
    rows = [t for t in transactions if t['amountMinor'] < 0 and t['id'] not in dismissed]
    clues=search_clues(messages,locale)
    if 'status' in clues: rows=[t for t in rows if t.get('status')==clues['status']]
    if 'amountMinor' in clues: rows=[t for t in rows if abs(t['amountMinor'])==clues['amountMinor']]
    if 'date' in clues: rows=[t for t in rows if local_date(t['date'])==clues['date']]
    if 'category' in clues: rows=[t for t in rows if t.get('category')==clues['category']]
    if 'q' in clues: rows=[t for t in rows if normalize(clues['q']) in normalize(t['merchant']+' '+t['id'])]
    if not rows:
        return None
    for entry in reversed(messages):
        if entry['role'] != 'user':
            continue
        text = entry['content']; tokens = words(text)
        # Respect an explicit date or reference rather than falling back to a
        # different recent charge. Ambiguous dates use the conversation locale.
        dates = re.findall(r'\b(\d{4})-(\d{2})-(\d{2})\b', text)
        for a, b, y in re.findall(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', text):
            dates.append((y, a.zfill(2), b.zfill(2)) if locale == 'en' else (y, b.zfill(2), a.zfill(2)))
        if dates:
            rows = [t for t in rows if local_date(t['date']) in {'-'.join(d) for d in dates}]
            if not rows:
                return None
        reference = next((t for t in rows if re.search(r'(?<![\w-])' + re.escape(t['id']) + r'(?![\w-])', text, re.I)), None)
        if reference:
            return reference
        if re.search(r'\btx-[\w-]+', text, re.I):
            return None
        # Prefer a named merchant, then service keywords. A phone mention with no
        # matching provider returns nothing instead of proposing an unrelated bill.
        merchant_matches = [t for t in rows if related(tokens, words(t['merchant']) - {'empresa', 'the', 'de', 'do', 'bank', 'banco'})]
        if merchant_matches:
            return merchant_matches[0]
        for service, (aliases, category) in TOPICS.items():
            if related(tokens, words(aliases)):
                provider = normalize(SERVICES.get(service, {}).get('provider') or '')
                return next((t for t in rows if (provider and provider in normalize(t['merchant']))
                             or (category and t.get('category') == category)), None)
        if dates:
            return rows[0]
    return rows[0]


def suggestion_reply(tx, locale):
    amount = f"{Decimal(abs(tx['amountMinor'])) / 100:,.2f}"
    if locale == 'pt':
        amount = amount.translate(str.maketrans({',': '.', '.': ','}))
    y, m, d = local_date(tx['date']).split('-')
    date = f'{m}/{d}/{y}' if locale == 'en' else f'{d}/{m}/{y}'
    status = {
        'es': {'completed': 'Completado', 'pending': 'Pendiente', 'declined': 'Rechazado'},
        'en': {'completed': 'Completed', 'pending': 'Pending', 'declined': 'Declined'},
        'pt': {'completed': 'Concluído', 'pending': 'Pendente', 'declined': 'Recusado'},
    }[locale][tx['status']]
    copy = {
        'es': 'Encontré este cargo reciente que podemos revisar:\n{merchant} · {amount} {currency}\nFecha: {date} · Referencia: {id}\n\n¿Te refieres a este movimiento o a otro? Puedes confirmarlo aquí o indicarme la fecha o referencia del otro.',
        'en': 'I found this recent charge we can review:\n{merchant} · {amount} {currency}\nDate: {date} · Reference: {id}\n\nIs this the transaction you mean, or another one? Confirm it here or tell me the date or reference of the other transaction.',
        'pt': 'Encontrei esta cobrança recente que podemos revisar:\n{merchant} · {amount} {currency}\nData: {date} · Referência: {id}\n\nVocê se refere a esta movimentação ou a outra? Confirme aqui ou informe a data ou referência da outra.',
    }
    return copy[locale].format(**(tx | {'merchant':tx['merchant'] + ' · ' + status, 'amount': amount, 'date': date}))
