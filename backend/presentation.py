"""Render previous canned copy with the current tone; stored history stays intact."""
import re
COPY_CHANGES = [('Tu saldo disponible de demo es {amount} MXN. Abrí tus productos para ver el detalle.', 'Tu saldo disponible es {amount} MXN. Abrí tus productos para ver el detalle.'), ('Puedo preparar una solicitud para una persona. La derivación es simulada: no hay un agente real conectado.', 'Puedo ayudarte a preparar una solicitud de atención. Revisa el detalle antes de enviarla.'), ('Para orientarte mejor, ¿quieres consultar tu saldo, revisar un movimiento o seguir una solicitud? Este asistente de demo usa respuestas guiadas.', 'Puedo ayudarte a consultar tu saldo, navegar por tus servicios o seguir una solicitud. ¿Qué necesitas?'), ('Your available demo balance is {amount} MXN. I opened your products so you can see the details.', 'Your available balance is {amount} MXN. I opened your products so you can see the details.'), ('I can prepare a request for a person. This handoff is simulated: no real support agent is connected.', 'I can help you prepare a support request. Review the details before sending it.'), ('Would you like to check your balance, review a transaction or track a request? This demo assistant uses guided responses.', 'I can help you check your balance, navigate your services or track a request. What would you like to do?'), ('Seu saldo disponível de demo é {amount} MXN. Abri seus produtos para você consultar os detalhes.', 'Seu saldo disponível é {amount} MXN. Abri seus produtos para você consultar os detalhes.'), ('Posso preparar uma solicitação para uma pessoa. O encaminhamento é simulado: não há um atendente real conectado.', 'Posso ajudar a preparar uma solicitação de atendimento. Revise os detalhes antes de enviá-la.'), ('Você quer consultar seu saldo, revisar uma movimentação ou acompanhar uma solicitação? Este assistente de demo usa respostas guiadas.', 'Posso ajudar a consultar seu saldo, navegar pelos serviços ou acompanhar uma solicitação. O que você precisa?')]

def present_message(text, role):
    if role != 'assistant':
        return text
    for previous, current in COPY_CHANGES:
        if '{amount}' in previous:
            pattern = re.escape(previous).replace(r'\{amount\}', r'(?P<amount>[0-9.,]+)')
            match = re.fullmatch(pattern, text)
            if match:
                return current.format(amount=match.group('amount'))
        elif text == previous:
            return current
    return text
