"""Explicit application commands from the customer's own text, never model output.

These commands interrupt neither the saved attention graph nor its pending question.
Financial operations remain outside this allowlist.
"""
import re
import unicodedata
from .navigation import navigate_in_app
from .chat_language import wrong_language, language_reply


def command_text(text):
    value = ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn')
    value = re.sub(r'\s+', ' ', value).strip(' .!¡?¿')
    value = re.sub(r'^(por favor|please|por gentileza),?\s+', '', value)
    value = re.sub(r'[, ]+(por favor|please|por gentileza)$', '', value)
    # Match the entire request: negations, quoted instructions and mixed banking
    # requests must continue through the existing interpreter.
    value = re.sub(r'^(puedes|podrias|me puedes|me podrias|podes|voce pode|could you|can you) ', '', value)
    return value


def _application_command(text, locale):
    value = command_text(text)
    action = None
    navigation = None
    value = re.sub(r'^(show|show me|view) (?:my |the )?card (details|number|cvv)(.*)$', r'\1 \2 of my card\3', value)
    card = re.fullmatch(r'(?:(ver|mostrar|muestrame|quiero ver|show|show me|view|i want to see|mostre|quero ver) (?:el |o |los |os |the |my |mis |meu |meus )?(?:datos|detalles|details|dados|numero|number|cvv)(?: de | da | do | of | for | )(?:(?:mi|la|my|the|meu|minha|o|a) )?(?:tarjeta|card|cartao)|(?P<block>bloquea|bloquear|bloqueame|quiero bloquear|block|lock|bloquear|bloqueie) (?:(?:mi|la|my|the|meu|minha|o|a) )?(?:tarjeta|card|cartao))(?: (?:terminada en|ending in|final) (\d{4}))?', value)
    if card:
        operation = 'block' if card['block'] else 'reveal'
        return {'text': ('Abro Tarjetas para que confirmes tu identidad.','I will open Cards so you can confirm your identity.','Vou abrir Cartões para você confirmar sua identidade.')[('es','en','pt').index(locale)],
                'destination': 'cards', 'navigation': navigate_in_app('cards','customer'),
                'appCommand': {'type':'prepare_card', 'action':operation, 'last4':card[3]}}
    if re.fullmatch(r'(cierra|cerrar|cierre|cerrame|quiero cerrar) (mi |la )?sesion|salir(?: de (?:mi |la )?cuenta)?|desconectame|log ?out|log me out|sign (me )?out|(encerrar|encerre|fechar|feche) (a |minha )?sessao|sair( da (minha )?conta)?', value):
        action = {'type': 'logout'}
        reply = ('Voy a cerrar tu sesión.', 'I will sign you out.', 'Vou encerrar sua sessão.')
    else:
        language = re.fullmatch(r'(?:cambia|cambiar|cambiame|pon|poner|quiero cambiar|change|switch|set|muda|mude|mudar|troca|troque|alterar|altere) (?:(?:el idioma|idioma|el idioma de la plataforma|la plataforma|the language|language|o idioma|o idioma da plataforma|a plataforma) )?(?:a |al |to |para |para o |em )?(espanol|spanish|espanhol|ingles|english|portugues|portuguese)', value)
        if language:
            target = {'espanol':'es', 'spanish':'es', 'espanhol':'es', 'ingles':'en', 'english':'en', 'portugues':'pt', 'portuguese':'pt'}[language[1]]
            action = {'type': 'set_locale', 'locale': target}
            reply = ('Voy a cambiar el idioma de la plataforma.', 'I will change the platform language.', 'Vou alterar o idioma da plataforma.')
        else:
            route = re.fullmatch(r'(?:llevame|llevarme|llevar|ir|ve|volver|vuelve|abre|abrir|muestra|muestrame|ver|quiero ver|quiero ir|take me|go|return|show|show me|open|navigate|me leve|leve-me|ir|va|abra|mostrar|mostre|quero ver) (?:a |al |a la |a las |a los |el |la |las |los |to |to the |the |ao |aos |as |o |os )*(?:(?:mis|mi|my|minhas|meus|minha|meu) )?(solicitudes|requests|solicitacoes|reclamos|reclamaciones|complaints|reclamacoes|tarjetas|cards|cartoes|inicio|home|overview|pagina inicial|centro de ayuda|help center|central de ajuda|centro de ajuda)', value)
            if not route:
                return None
            destination = next(key for key, names in {
                'requests': ('solicitudes','requests','solicitacoes'),
                'complaints': ('reclamos','reclamaciones','complaints','reclamacoes'),
                'cards': ('tarjetas','cards','cartoes'),
                'home': ('inicio','home','overview','pagina inicial'),
                'help': ('centro de ayuda','help center','central de ajuda','centro de ajuda'),
            }.items() if route[1] in names)
            navigation = navigate_in_app(destination, 'customer')
            labels = {'requests': ('Mis solicitudes','My requests','Minhas solicitações'), 'complaints': ('Mis reclamos','My complaints','Minhas reclamações'),
                      'cards': ('Mis tarjetas','My cards','Meus cartões'), 'home': ('Inicio','Overview','Início'), 'help': ('Centro de ayuda','Help center','Central de ajuda')}
            reply = tuple(template.format(screen=label) for template, label in zip(('Abrí {screen}.','I opened {screen}.','Abri {screen}.'), labels[destination]))
    return {'text': reply[('es','en','pt').index(locale)], 'destination': navigation['destination'] if navigation else None,
            'navigation': navigation, 'appCommand': action}


def application_command(text, locale):
    command = _application_command(text, locale)
    if command and (command.get('appCommand') or {}).get('type') == 'set_locale':
        return command
    if wrong_language(text, locale):
        return language_reply(locale)
    if command:
        return command
    from .chat_language import normalized
    value = command_text(text)
    if re.search({'es':r'\b(no|nunca)\b','en':r'\b(no|not|never|dont)\b','pt':r'\b(nao|nunca)\b'}[locale], value) or any(c in value for c in ('"','“','”')):
        return None
    verbs = {'es':r'(?:cambia|cambiar|quiero cambiar|actualiza|modifica|pon|ajusta|aumenta|reduce)', 'en':r'(?:change|set|update|i want to change|adjust|increase|decrease)', 'pt':r'(?:mude|mudar|altere|alterar|quero mudar|atualize|ajuste|aumente|diminua)'}
    match = re.fullmatch(verbs[locale] + r' (.{1,180})', value)
    if not match:
        # A named card remains a proposal, never an authorization to reveal it.
        named = re.fullmatch({'es':r'(?:ver|muestrame|mostrar|quiero ver) (?:los )?(?:datos|detalles) de (?:mi |la )?tarjeta (.{1,80})',
            'en':r'(?:show|show me|view) (?:the |my )?(?:details of (?:my |the )?card|card details for) (.{1,80})',
            'pt':r'(?:mostre|mostrar|quero ver) (?:os )?dados d[oa] (?:meu |minha )?cartao (.{1,80})'}[locale], value)
        if named:
            result = _application_command({'es':'ver datos de mi tarjeta','en':'show my card details','pt':'mostre os dados do meu cartao'}[locale], locale)
            result['appCommand']['name'] = named[1]
            return result
        from .assistant import NAV_LABELS
        route = re.fullmatch({'es':r'(?:llevame|abre|abrir|muestrame|ver|quiero ver|ir) (?:a |al |a la |a los |a las |mis |mi |los |las |el |la )*(.+)',
            'en':r'(?:take me|go|open|show|show me|view) (?:to |the |my )*(.+)',
            'pt':r'(?:me leve|leve-me|va|abra|abrir|mostre|ver|quero ver) (?:a |ao |aos |as |os |o |meus |minhas |minha |meu )*(.+)'}[locale],value)
        if route:
            labels = {**NAV_LABELS[locale], 'documents':{'es':'Mis documentos','en':'My documents','pt':'Meus documentos'}[locale]}
            for destination,label in labels.items():
                target=re.sub(r'^(mis |my |meus |minhas )','',normalized(label))
                if route[1]==target:
                    return {'text':{'es':'Abrí ','en':'I opened ','pt':'Abri '}[locale]+label+'.', 'destination':destination,
                            'navigation':navigate_in_app(destination,'customer'),'appCommand':None}
        return None
    subject = match[1]
    fields = {
        'birthDate': r'fecha de nacimiento|date of birth|birth date|birthday|data de nascimento',
        'digitalExperience': r'banca digital|digital banking|banco digital|experiencia digital|digital experience',
        'bankingExperience': r'frecuencia|frecuentemente|frequency|how often|frequencia|banking experience|experiencia bancaria',
        'assistance': r'acompan|asistencia|assist|support preference|preferencia de ajuda',
        'textSize': r'tamano (?:de |del )?(?:texto|letra)|text size|font size|tamanho (?:da |de |do )?(?:letra|texto)|letra (?:pequena|mediana|media|grande)',
    }
    for field, pattern in fields.items():
        if re.search(pattern, subject):
            size = None
            if field == 'textSize':
                size = next((key for key, pattern in {'small':r'pequen[oa]|small','medium':r'median[oa]|medium|medi[oa]','large':r'grande|large'}.items() if re.search(r'\b(?:'+pattern+r')\b',subject)),None)
            return {'text': {'es':'Elige el dato y confirma el cambio aquí.', 'en':'Choose the value and confirm the change here.', 'pt':'Escolha o dado e confirme a alteração aqui.'}[locale],
                    'navigation':None,'destination':None,'appCommand':{'type':'prepare_profile','field':field,'value':size}}
    return None
