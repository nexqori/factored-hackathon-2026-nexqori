"""Explicit application commands from the customer's own text, never model output.

These commands interrupt neither the saved attention graph nor its pending question.
Financial operations remain outside this allowlist.
"""
import re
import unicodedata
from .navigation import navigate_in_app


def application_command(text, locale):
    value = ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn')
    value = re.sub(r'\s+', ' ', value).strip(' .!¡?¿')
    value = re.sub(r'^(por favor|please|por gentileza),?\s+', '', value)
    value = re.sub(r'[, ]+(por favor|please|por gentileza)$', '', value)
    # Match the entire request: negations, quoted instructions and mixed banking
    # requests must continue through the existing interpreter.
    value = re.sub(r'^(puedes|podrias|me puedes|me podrias|podes|voce pode|could you|can you) ', '', value)
    action = None
    navigation = None
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
