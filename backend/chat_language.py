"""Local language boundary, before commands or providers; no bank data leaves here."""
import re
import unicodedata


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn')


WORDS = {
    'es': set('quiero necesito llevame muestra muestrame abre abrir ver cambia cambiar cerrar cierra sesion solicitudes solicitud reclamo reclamos tarjetas tarjeta cuenta cuentas movimientos movimiento ayuda nacimiento letra tamano pequeno pequena mediano mediana grande frecuencia bancarios sientes prefieres acompanemos idioma espanol pagar pago pagos prestamo prestamos inversiones seguro seguros retiro retiros desconocido cobro cobraron reconozco mis mi estoy tengo como que cual cuanto donde puedes podrias por favor'.split()),
    'en': set('i want need take show open view change switch close log logout sign out requests request complaint complaints cards card account accounts movements transactions transaction help birth birthday font text size small medium large banking frequency feel digital prefer support language english pay payment payments loan loans investments insurance withdrawal withdrawals unknown charged recognize my the me please could would how what where balance home settings services'.split()),
    'pt': set('quero preciso leve mostre mostrar abra abrir ver mude mudar altere alterar encerre encerrar feche fechar sessao solicitacoes solicitacao reclamacao reclamacoes cartoes cartao conta contas movimentacoes movimentacao ajuda nascimento letra tamanho pequeno pequena medio media grande frequencia bancarios sente prefere acompanhemos idioma portugues pagar pagamento pagamentos emprestimo emprestimos investimentos seguro seguros saque saques desconhecido cobranca cobraram reconheco meus minhas meu minha estou tenho como que qual quanto onde voce pode gentileza'.split()),
}
WORDS['es'].update('hola adios gracias si no del las los el una un al llevame vuelve volver bloquea bloquear desbloquear datos detalles recibo resumen imprimir quiero pequena mediana recibida'.split())
WORDS['en'].update('hello goodbye thanks yes no not do dont go return block lock details receipt summary print how often feel using accompany as'.split())
WORDS['en'].discard('me')
WORDS['pt'].update('ola obrigado obrigada sim nao no do da das dos os as ao aos va volte voltar bloqueie bloquear desbloquear dados detalhes recibo resumo imprimir inicio banco'.split())
WORDS['es'].update('inicio productos producto configuracion servicios servicio transferencias transferencia inversiones inversion documentos documento historial estado cuenta recibos saldo asesor telefono celular'.split())
WORDS['en'].update('products product configuration transfers transfer documents document history statement receipts advisor phone mobile'.split())
WORDS['pt'].update('produtos produto configuracoes servicos servico transferencias transferencia documentos documento historico extrato recibos saldo atendente telefone celular'.split())
WORDS['es'].update('va mostrar cierre cerrame salir desconectame llevarme llevar ir ve vuelve volver bloqueame actualiza modifica pon poner ajusta aumenta reduce medio media'.split())
WORDS['en'].update('set adjust increase decrease update navigate see number ending'.split())
WORDS['pt'].update('estado ir por favor sair muda troca troque atualize ajuste aumente diminua podes'.split())
for words in WORDS.values():
    words.add('digital')


def wrong_language(text, locale):
    # Product/case IDs are neutral references, not words in a foreign language.
    value = re.sub(r'\b(?:tx|nq|pay|trf|refund|card)-[a-z0-9-]+\b|\b[a-z][a-z0-9-]*\d[a-z0-9-]*\b', '', normalized(text))
    words = set(re.findall(r'[a-z]+', value))
    foreign = set().union(*(tokens for lang,tokens in WORDS.items() if lang != locale)) - WORDS[locale]
    # A merchant name can contain a foreign word (e.g. Mercado Llevar).
    # Reject a foreign request, not an otherwise local sentence naming it.
    own = WORDS[locale] - set().union(*(tokens for lang,tokens in WORDS.items() if lang != locale))
    return len(words & foreign) > len(words & own)


def language_reply(locale):
    return {'text': {'es':'Escribe en español para continuar, o pídeme cambiar el idioma.',
        'en':'Please write in English to continue, or ask me to change the language.',
        'pt':'Escreva em português para continuar, ou peça para mudar o idioma.'}[locale],
        'destination':None, 'navigation':None, 'appCommand':None}
