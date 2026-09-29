import re
import unicodedata
from .navigation import navigate_in_app
from .catalog import search_services

COPY = {
"es": {
"settings": "Abrí Configuración. Aquí puedes elegir el tamaño de letra que prefieras.",
"balance": "Tu saldo disponible es {amount} MXN. Abrí tus productos para ver el detalle.",
"movements": "Abrí tus movimientos. Puedes buscar por comercio o estado y elegir el que quieres revisar.",
"report": "Vamos paso a paso. Elige el movimiento y cuéntanos qué ocurrió. Revisarás los datos antes de confirmar la solicitud.",
"requests": "Abrí tus solicitudes. Allí puedes consultar el seguimiento y pedir atención humana.",
"human": "Puedo ayudarte a preparar una solicitud de atención. Revisa el detalle antes de enviarla.",
"unknown": "Puedo ayudarte a consultar tu saldo, navegar por tus servicios o seguir una solicitud. ¿Qué necesitas?"},
"en": {
"settings": "I opened Settings. You can choose the text size that feels right for you here.",
"balance": "Your available balance is {amount} MXN. I opened your products so you can see the details.",
"movements": "I opened your transactions. Search by merchant or status and choose one to review.",
"report": "Let’s take it step by step. Choose a transaction and tell us what happened. You will review the details before confirming.",
"requests": "I opened your requests. You can track progress and ask for human support there.",
"human": "I can help you prepare a support request. Review the details before sending it.",
"unknown": "I can help you check your balance, navigate your services or track a request. What would you like to do?"},
"pt": {
"settings": "Abri Configurações. Aqui você pode escolher o tamanho de letra que preferir.",
"balance": "Seu saldo disponível é {amount} MXN. Abri seus produtos para você consultar os detalhes.",
"movements": "Abri suas movimentações. Busque por estabelecimento ou status e escolha uma para revisar.",
"report": "Vamos por partes. Escolha a movimentação e conte o que aconteceu. Você revisará os dados antes de confirmar.",
"requests": "Abri suas solicitações. Lá você pode acompanhar o andamento e pedir atendimento humano.",
"human": "Posso ajudar a preparar uma solicitação de atendimento. Revise os detalhes antes de enviá-la.",
"unknown": "Posso ajudar a consultar seu saldo, navegar pelos serviços ou acompanhar uma solicitação. O que você precisa?"}
}
def classify(text):
    value="".join(c for c in unicodedata.normalize("NFD",text.lower()) if unicodedata.category(c)!="Mn")
    if re.search(r"\b(admin|administracion|administration|administracao)\b", value): return "restricted"
    if re.search(r"\b(no|not|don['’]?t|nao|never|nunca)\b.{0,18}\b(abr|open|naveg|navigate|ir)" ,value): return "unknown"
    for intent,pattern in [
        ("settings",r"configurac|settings|preferences|preferencias|tamano de letra|tamanho da letra|text size|font size"),
        ("human",r"humano|human|persona|person|pessoa|agente|asesor|atendente"),
        ("report",r"no reconozco|nao reconheco|don.t recognize|unrecognized|cobro|cobranca|charge|reclamar|reportar|report a"),
        ("requests",r"seguimiento|solicitud|solicitac|reclamo|reclamac|acompanhar|request|track|case"),
        ("balance",r"saldo|balance"),
        ("movements",r"movimientos|movimentacoes|transactions|historial|historico|history"),
        ("transfers",r"transferenc|transfer"),
        ("payments",r"pagar|pago|pagamento|bill|pay a|payment"),
        ("cards",r"tarjeta|cartao|cartoes|card"),
        ("accounts",r"cuenta|conta|account"),
        ("loans",r"prestamo|credito|hipoteca|loan|mortgage|emprestimo"),
        ("investments",r"inversion|investimento|investment"),
        ("insurance",r"seguro|insurance"),
        ("cash",r"retiro|deposito|withdraw|deposit|saque"),
        ("products",r"producto|produto|product"),
        ("services",r"servicio|servico|service"),
        ("help",r"ayuda|ajuda|help"),
        ("home",r"inicio|home|overview"),
        ("movements",r"movimiento|movimento|transaccion|transac|pago|pagamento|payment|tarjeta|cartao|card")
    ]:
        if re.search(pattern,value): return intent
    return "unknown"

NAV_LABELS = {
"es":{"settings":"Configuración","home":"Inicio","products":"Mis productos","movements":"Movimientos","requests":"Mis solicitudes","services":"Servicios","help":"Centro de ayuda","accounts":"Cuentas","cards":"Tarjetas","transfers":"Transferencias","payments":"Pagos de servicios","loans":"Préstamos","investments":"Inversiones","insurance":"Seguros","cash":"Retiros y depósitos"},
"en":{"settings":"Settings","home":"Overview","products":"My products","movements":"Transactions","requests":"My requests","services":"Services","help":"Help center","accounts":"Accounts","cards":"Cards","transfers":"Transfers","payments":"Bill payments","loans":"Loans","investments":"Investments","insurance":"Insurance","cash":"Withdrawals and deposits"},
"pt":{"settings":"Configurações","home":"Início","products":"Meus produtos","movements":"Movimentações","requests":"Minhas solicitações","services":"Serviços","help":"Central de ajuda","accounts":"Contas","cards":"Cartões","transfers":"Transferências","payments":"Pagamento de serviços","loans":"Empréstimos","investments":"Investimentos","insurance":"Seguros","cash":"Saques e depósitos"}}

def answer(text,locale,balance_minor,current_page="home"):
    intent=classify(text)
    normalized="".join(c for c in unicodedata.normalize("NFD",text.lower()) if unicodedata.category(c)!="Mn").strip()
    if intent!="restricted" and not re.search(r"\b(no|not|don['’]?t|nao|never|nunca)\b.{0,18}\b(abr|open|naveg|navigate|ir)",normalized):
        matches=search_services(text,locale=locale)
        if len(matches)==1 and matches[0]["kind"]=="bill":
            item=matches[0]
            response={"es":"Encontré {title}, con {provider}. Completa los datos y revísalos antes de confirmar la solicitud.",
                      "en":"I found {title}, with {provider}. Enter the details and review them before confirming your request.",
                      "pt":"Encontrei {title}, com {provider}. Preencha os dados e revise antes de confirmar a solicitação."}[locale]
            return {"text":response.format(title=item["copy"][locale]["title"],provider=item["provider"]),"destination":"services","intent":"service","navigation":navigate_in_app("services","customer",item["id"])}
    if normalized in ("ahi","alli","there","la","aqui") and current_page in NAV_LABELS[locale]: intent=current_page
    amount=f"{balance_minor/100:,.2f}"
    if locale=="pt": amount=amount.translate(str.maketrans({",":".",".":","}))
    destination={"balance":"products","movements":"movements","report":"new-request","requests":"requests","human":"new-request","unknown":None,"restricted":None}.get(intent,intent)
    if intent=="restricted":
        response={"es":"Tu cuenta no tiene acceso al panel administrativo. Puedo ayudarte a navegar tus productos y solicitudes.","en":"Your account cannot access the admin panel. I can help you navigate your products and requests.","pt":"Sua conta não tem acesso ao painel administrativo. Posso ajudar a navegar seus produtos e solicitações."}[locale]
    elif intent in COPY[locale]: response=COPY[locale][intent].replace("{amount}",amount)
    else:
        response={"es":"Abrí {screen}. Puedes consultar la información o preparar una solicitud.","en":"I opened {screen}. You can view the information or prepare a request.","pt":"Abri {screen}. Você pode consultar informações ou preparar uma solicitação."}[locale].replace("{screen}",NAV_LABELS[locale][intent])
    command=navigate_in_app(destination,"customer") if destination and destination!="new-request" else None
    return {"text":response,"destination":destination,"intent":intent,"navigation":command}
