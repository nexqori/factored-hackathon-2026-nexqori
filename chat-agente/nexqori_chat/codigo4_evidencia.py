"""Código 4: extracción anclada al texto, juicio Jev y preguntas LLM por turno."""
from .contratos import require, parse_date
from .proveedores import object_schema

FIELDS = ['document_type', 'scope', 'product_id', 'transaction_id', 'request_id', 'start', 'end', 'all_history', 'details', 'service', 'topic']
EXTRACTION_SCHEMA = object_schema({
    'understood': {'type': 'boolean'},
    'fields': {'type': 'array', 'items': object_schema({
        'name': {'type': 'string', 'enum': FIELDS}, 'value': {'type': 'string'}, 'quote': {'type': 'string'}})}})


def extraer_datos(context, latest_text, action, providers):
    value = providers.generate('codigo4.extraer', {'conversation': context, 'latest_text': latest_text, 'action': action},
        'Extrae sólo datos aportados por el último mensaje. fields contiene nombre, valor y una cita literal del '
        'último texto que respalda el valor. understood indica si el mensaje es comprensible y pertinente a la '
        'solicitud/pregunta pendiente, incluso si dice no saber el dato. No inventes IDs, fechas, permisos ni datos '
        'bancarios. No copies datos afirmados sólo por el agente. scope=all o selected; '
        'scope=all exige que el usuario pida explícitamente todos/todas/all/todos os productos, cuentas o registros. '
        'Una petición como "mi saldo" o "meu saldo" no define scope: omite ese campo y deja que se pregunte. '
        'Si identifica un producto o registro concreto, extrae scope=selected además de su ID literal. '
        'all_history=true o false; '
        'start/end ISO8601 con zona explícita (end exclusivo). Sin zona/periodo inequívoco no extraer fechas. '
        'document_type sólo puede ser statement, products_summary o requests_summary según el documento pedido; no inferirlo de una petición genérica de PDF. IDs deben aparecer literalmente. details copia descripción literal. service usa general, accounts, cards, '
        'transfers, payments, loans, investments, insurance, cash, support. Sólo extrae campos pertinentes.',
        EXTRACTION_SCHEMA)
    require(len(value['fields']) <= len(FIELDS), 'EXTRACTION_DUPLICATES', 'Demasiados campos extraídos.')
    result, sources = {}, {}
    for item in value['fields']:
        name, text, quote = item['name'], item['value'], item['quote']
        require(name not in result, 'EXTRACTION_DUPLICATES', 'Campo duplicado.')
        require(bool(quote.strip()) and quote in latest_text and len(text) <= 1000, 'UNSUPPORTED_EXTRACTION', 'Valor sin cita literal del usuario.')
        if name.endswith('_id'):
            require(text in quote and 0 < len(text) <= 64, 'INVENTED_ID', 'Identificador no literal.')
        elif name == 'document_type':
            require(text in {'statement', 'products_summary', 'requests_summary'}, 'INVALID_DOCUMENT', 'Documento no admitido.')
        elif name == 'scope':
            require(text in {'all', 'selected'}, 'INVALID_SCOPE', 'Alcance inválido.')
        elif name == 'all_history':
            require(text in {'true', 'false'}, 'INVALID_HISTORY', 'Indicador de historial inválido.')
            text = text == 'true'
        elif name in {'start', 'end'}:
            parse_date(text)
        elif name == 'service':
            require(text in {'general', 'accounts', 'cards', 'transfers', 'payments', 'loans', 'investments', 'insurance', 'cash', 'support'}, 'INVALID_SERVICE', 'Servicio inválido.')
        elif name == 'details':
            require(text in quote and len(text.strip()) >= 10, 'INVALID_DETAILS', 'Descripción insuficiente.')
        result[name], sources[name] = text, {'quote': quote, 'source': 'user_message'}
    return {'understood': value['understood'], 'fields': result, 'sources': sources}


def merge_fields(conversation, extracted):
    updates = extracted['fields']
    # Un cambio de selección/periodo invalida selecciones/periodos anteriores, no los mezcla.
    if any(k in updates for k in ('product_id', 'transaction_id', 'request_id')) or updates.get('scope') == 'all':
        for k in ('product_id', 'transaction_id', 'request_id'):
            conversation.fields.pop(k, None); conversation.field_sources.pop(k, None)
    if updates.get('all_history'):
        for k in ('start', 'end'):
            conversation.fields.pop(k, None); conversation.field_sources.pop(k, None)
    if any(k in updates for k in ('start', 'end')):
        conversation.fields.pop('all_history', None)
        conversation.field_sources.pop('all_history', None)
        if conversation.fields.get('start') and conversation.fields.get('end'):
            # Un nuevo periodo no puede reutilizar por accidente el otro extremo del anterior.
            for k in ('start', 'end'):
                conversation.fields.pop(k, None); conversation.field_sources.pop(k, None)
    conversation.fields.update(updates)
    conversation.field_sources.update(extracted['sources'])


def missing_fields(action, fields):
    missing = []
    for name in action['requires']:
        if name == 'period':
            valid = fields.get('all_history') is True or bool(fields.get('start') and fields.get('end'))
        else:
            valid = bool(fields.get(name))
        if not valid:
            missing.append(name)
    if action['kind'] == 'document':
        kind = fields.get('document_type')
        if kind == 'statement' and not (fields.get('all_history') is True or (fields.get('start') and fields.get('end'))):
            missing.append('period')
        if fields.get('scope') == 'selected':
            selection = 'request_id' if kind == 'requests_summary' else 'product_id'
            if not fields.get(selection): missing.append('selection')
    if fields.get('start') and fields.get('end'):
        require(parse_date(fields['start']) < parse_date(fields['end']), 'INVALID_PERIOD', 'Inicio debe ser anterior al fin.')
    if action['kind'] == 'read' and fields.get('scope') == 'selected':
        query = action['query']
        selection = {'products': ('product_id',), 'transactions': ('transaction_id', 'product_id'),
                     'requests': ('request_id',), 'catalog': ()}[query]
        if selection and not any(fields.get(k) for k in selection):
            missing.append('selection')
    return sorted(set(missing))


def clasificar_evidencia(context, action, rules, providers):
    missing = missing_fields(action, context['fields'])
    judgment = providers.choice('codigo4.evidencia',
        {'conversation': context, 'action': action, 'missing': missing, 'questions': rules['questions']},
        'Evalúa evidencia para la acción propuesta, no permisos. desconocido si no se entiende; insatisfecho si '
        'faltan datos mínimos o la petición es contradictoria; humano si la regla exige humano/capacidad ausente; '
        'supervisado si necesita confirmación; automatico para consulta con datos mínimos completos. '
        'La lectura y titularidad se verificarán en servidor antes de responder.', rules['classes'])
    raw = judgment['label']
    effective = raw
    if raw != 'desconocido':
        if missing:
            effective = 'insatisfecho'
        elif action['kind'] in {'human', 'unsupported'}:
            effective = 'humano'
        elif action['kind'] == 'supervised' and raw == 'automatico':
            effective = 'supervisado'
    return {'judgment': judgment, 'effective': effective, 'missing': missing,
            'execution_authorized': False, 'override_reason': 'deterministic_requirements' if raw != effective else None}


def preguntar(context, rules, action, missing, language, providers, *, not_understood=False):
    schema = object_schema({'question': {'type': 'string'}})
    questions = {k: rules['questions'][k][language] for k in missing if k in rules['questions']}
    result = providers.generate('codigo4.preguntar', {'conversation': context, 'action': action,
        'missing': missing, 'question_rules': questions, 'language': language, 'not_understood': not_understood},
        'Redacta una pregunta específica y breve en language para obtener los datos faltantes de la regla. '
        'No pidas credenciales, permisos, tokens ni datos ajenos. Si not_understood=true, empieza diciendo que '
        'no entendiste la respuesta y reformula la pregunta pendiente. Si faltan varios datos, agrupa sólo los '
        'relacionados. No afirme operaciones ni conexión humana. Si no hay campo concreto, pide precisar el '
        'objetivo de la solicitud. Devuelve question.', schema)
    require(0 < len(result['question'].strip()) <= 1800, 'INVALID_QUESTION', 'Pregunta vacía o excesiva.')
    return result['question']
