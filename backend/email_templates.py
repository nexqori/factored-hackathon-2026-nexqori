"""Responsive, self-contained transactional mail; no tracking or remote assets."""
from html import escape

_COPY = {
    'es': {
        'label': 'UN PASO MÁS, CONTIGO', 'tagline': 'Tu banca, más cerca.',
        'email_title': 'Confirma tu correo', 'card_title': 'Tú decides sobre tu tarjeta',
        'email_subject': 'Confirma tu correo', 'card_subject': 'Confirma el bloqueo de tu tarjeta',
        'email_intro': 'Verifica esta dirección para recibir tus códigos de seguridad y continuar con tus gestiones.',
        'card_intro': 'Solicitaste bloquear la tarjeta terminada en {last4}. Confirma que fuiste tú con este código.',
        'code_label': 'TU CÓDIGO DE CONFIRMACIÓN', 'expiry': 'Válido durante 5 minutos',
        'step': 'Continúa en Nexqori',
        'instruction': 'Escribe el código en la misma ventana donde lo solicitaste. No necesitas responder a este correo.',
        'guard_title': 'Este código es sólo para ti',
        'guard': 'No lo compartas ni lo escribas en el chat. Si no lo solicitaste, ignora este mensaje.',
        'email_effect': 'Verificar tu correo no cambia tu contraseña ni realiza operaciones.',
        'card_effect': 'La tarjeta se bloqueará cuando confirmes el código en Nexqori.',
        'footer': 'Contigo en cada paso.',
    },
    'en': {
        'label': 'ONE MORE STEP, TOGETHER', 'tagline': 'Banking, closer to you.',
        'email_title': 'Confirm your email', 'card_title': 'Your card. Your decision.',
        'email_subject': 'Confirm your email', 'card_subject': 'Confirm your card block',
        'email_intro': 'Verify this address to receive your security codes and continue managing your account.',
        'card_intro': 'You requested to block your card ending in {last4}. Use this code to confirm it was you.',
        'code_label': 'YOUR CONFIRMATION CODE', 'expiry': 'Valid for 5 minutes',
        'step': 'Continue in Nexqori',
        'instruction': 'Enter the code in the same window where you requested it. You do not need to reply to this email.',
        'guard_title': 'This code is just for you',
        'guard': 'Do not share it or enter it in chat. If you did not request it, ignore this message.',
        'email_effect': 'Verifying your email does not change your password or carry out transactions.',
        'card_effect': 'Your card will be blocked when you confirm the code in Nexqori.',
        'footer': 'With you at every step.',
    },
    'pt': {
        'label': 'MAIS UM PASSO, COM VOCÊ', 'tagline': 'Seu banco, mais perto.',
        'email_title': 'Confirme seu email', 'card_title': 'Você decide sobre seu cartão',
        'email_subject': 'Confirme seu email', 'card_subject': 'Confirme o bloqueio do cartão',
        'email_intro': 'Verifique este endereço para receber seus códigos de segurança e continuar com suas solicitações.',
        'card_intro': 'Você solicitou o bloqueio do cartão terminado em {last4}. Use este código para confirmar que foi você.',
        'code_label': 'SEU CÓDIGO DE CONFIRMAÇÃO', 'expiry': 'Válido por 5 minutos',
        'step': 'Continue no Nexqori',
        'instruction': 'Digite o código na mesma janela em que o solicitou. Não é necessário responder a este email.',
        'guard_title': 'Este código é só para você',
        'guard': 'Não compartilhe nem escreva no chat. Se não o solicitou, ignore esta mensagem.',
        'email_effect': 'Verificar seu email não altera sua senha nem realiza operações.',
        'card_effect': 'O cartão será bloqueado quando você confirmar o código no Nexqori.',
        'footer': 'Com você em cada passo.',
    },
}


def code_message(code, purpose, locale, last4=None):
    copy = _COPY[locale]
    kind = 'email' if purpose == 'notification_email' else 'card'
    title = copy[kind + '_title']
    intro = copy[kind + '_intro'].format(last4=last4)
    effect = copy[kind + '_effect']
    subject = 'Nexqori · ' + copy[kind + '_subject']
    plain = '\n\n'.join((title, intro, code, copy['expiry'], copy['instruction'], effect, copy['guard'], 'Nexqori · ' + copy['footer']))
    def e(key): return escape(copy[key])
    # Tables and inline styles keep the layout usable when a mail client strips CSS.
    html = f'''<!doctype html>
<html lang="{escape(locale)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F6F0EA;color:#392C27;font-family:'Segoe UI',Arial,sans-serif">
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all">{escape(title)} · {e('expiry')}</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:24px 16px">
<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="width:100%;max-width:600px;background:#FFFCF9;border:1px solid #E8D9D0;border-radius:24px">
<tr><td style="padding:28px 24px;border-bottom:1px solid #E8D9D0">
<table role="presentation" cellspacing="0" cellpadding="0"><tr>
<td width="48" height="48" align="center" style="background:#9A4B32;border-radius:14px;color:#FFFCF9;font-family:Georgia,serif;font-style:italic;font-size:36px;font-weight:bold" aria-hidden="true">n</td>
<td style="padding-left:14px"><div style="font-size:26px;letter-spacing:-1px;font-weight:700">nexqori</div><div style="font-size:12px;color:#735C50;margin-top:3px">{e('tagline')}</div></td>
</tr></table></td></tr>
<tr><td style="padding:32px 24px 24px">
<p style="margin:0 0 14px;color:#9A4B32;font-size:11px;letter-spacing:1.8px;font-weight:700">{e('label')}</p>
<h1 style="font-family:Georgia,serif;font-size:32px;line-height:1.2;font-weight:400;letter-spacing:-.5px;margin:0 0 18px">{escape(title)}</h1>
<p style="font-size:16px;line-height:1.65;margin:0 0 26px">{escape(intro)}</p>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#F2D8C8;border:1px solid #E8C5B4;border-radius:16px"><tr><td align="center" style="padding:24px 12px">
<p style="font-size:10px;letter-spacing:1.4px;font-weight:700;margin:0 0 12px">{e('code_label')}</p>
<p style="font-family:'Courier New',monospace;font-size:36px;letter-spacing:6px;font-weight:bold;margin:0 0 12px;white-space:nowrap">{escape(code)}</p>
<p style="font-size:13px;margin:0">{e('expiry')}</p>
</td></tr></table>
<h2 style="font-size:17px;margin:26px 0 8px">{e('step')}</h2>
<p style="font-size:15px;line-height:1.65;margin:0 0 12px">{e('instruction')}</p>
<p style="font-size:13px;line-height:1.65;color:#735C50;margin:0">{escape(effect)}</p>
</td></tr>
<tr><td style="padding:0 24px 28px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#F7F2ED;border-radius:12px"><tr><td style="padding:18px;border-left:3px solid #9A4B32">
<h2 style="font-size:14px;margin:0 0 7px">{e('guard_title')}</h2><p style="font-size:13px;line-height:1.6;margin:0;color:#735C50">{e('guard')}</p>
</td></tr></table></td></tr>
<tr><td style="padding:22px 24px;border-top:1px solid #E8D9D0;text-align:center;font-size:12px;color:#735C50"><strong style="color:#392C27">Nexqori</strong> · {e('footer')}</td></tr>
</table></td></tr></table></body></html>'''
    return subject, plain, html


_REFUND_COPY = {
    'es': ('Tu reembolso ya está en tu cuenta', 'El abono se completó. Puedes verlo en Movimientos.', 'Importe abonado', 'Expediente', 'Referencia del abono', 'Cuenta terminada en', 'No necesitas realizar ninguna acción ni compartir códigos.'),
    'en': ('Your refund is now in your account', 'The credit is complete. You can see it in Transactions.', 'Amount credited', 'Case', 'Credit reference', 'Account ending in', 'No action or security code is needed.'),
    'pt': ('Seu reembolso já está na sua conta', 'O crédito foi concluído. Você pode vê-lo em Movimentações.', 'Valor creditado', 'Protocolo', 'Referência do crédito', 'Conta terminada em', 'Você não precisa fazer nada nem compartilhar códigos.'),
}


def refund_message(locale, amount_minor, currency, case_id, credit_id, last4):
    locale = locale if locale in _REFUND_COPY else 'es'
    title, intro, amount_label, case_label, credit_label, account_label, instruction = _REFUND_COPY[locale]
    # Integer minor units avoid rounding a financial amount through binary floats.
    amount = f'{currency} {amount_minor // 100:,}.{amount_minor % 100:02d}'
    details = [(amount_label, amount), (case_label, case_id), (credit_label, credit_id), (account_label, last4)]
    plain = '\n\n'.join([title, intro, *[f'{label}: {value}' for label, value in details], instruction, 'Nexqori'])
    rows = ''.join(f'<tr><td style="padding:12px 16px;color:#735C50">{escape(label)}</td><td style="padding:12px 16px;overflow-wrap:anywhere;font-weight:600">{escape(str(value))}</td></tr>' for label, value in details)
    html = f'''<!doctype html><html lang="{locale}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;background:#F6F0EA;font-family:Segoe UI,Arial,sans-serif;color:#392C27">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:24px 16px">
<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="width:100%;max-width:600px;background:#FFFCF9;border:1px solid #E8D9D0;border-radius:24px">
<tr><td style="padding:24px;border-bottom:1px solid #E8D9D0;font-size:28px;font-weight:700;color:#9A4B32">nexqori.</td></tr>
<tr><td style="padding:28px 24px"><h1 style="font-family:Georgia,serif;font-weight:400;font-size:30px;margin:0 0 16px">{escape(title)}</h1><p style="line-height:1.6">{escape(intro)}</p>
<table width="100%" cellspacing="0" cellpadding="0" style="background:#F7F2ED;border-radius:16px;font-size:14px">{rows}</table>
<p style="font-size:13px;line-height:1.6;color:#735C50;margin-top:24px">{escape(instruction)}</p></td></tr>
<tr><td style="padding:20px 24px;border-top:1px solid #E8D9D0;color:#735C50;font-size:12px">Nexqori · {escape(_COPY[locale]['footer'])}</td></tr>
</table></td></tr></table></body></html>'''
    return 'Nexqori · ' + title, plain, html


def request_message(locale, case_id, is_claim=True):
    locale=locale if locale in ('es','en','pt') else 'es'
    title, intro, label, next_step = {
        'es': ('Recibimos tu reclamo' if is_claim else 'Recibimos tu solicitud', 'Tu expediente quedó registrado y está pendiente de revisión.', 'Número de expediente', 'Puedes consultar su avance en Mis reclamos.' if is_claim else 'Puedes consultar su avance en Mis solicitudes.'),
        'en': ('We received your complaint' if is_claim else 'We received your request', 'Your case is registered and awaiting review.', 'Case number', 'Track its progress in My complaints.' if is_claim else 'Track its progress in My requests.'),
        'pt': ('Recebemos sua reclamação' if is_claim else 'Recebemos sua solicitação', 'Seu protocolo foi registrado e está aguardando análise.', 'Número do protocolo', 'Acompanhe em Minhas reclamações.' if is_claim else 'Acompanhe em Minhas solicitações.'),
    }[locale]
    plain='\n\n'.join([title, intro, f'{label}: {case_id}', next_step, 'Nexqori'])
    html=f'''<!doctype html><html lang="{locale}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#F6F0EA;color:#392C27;font-family:Segoe UI,Arial,sans-serif"><table role="presentation" width="100%"><tr><td align="center" style="padding:24px 16px"><table role="presentation" width="600" style="width:100%;max-width:600px;background:#FFFCF9;border:1px solid #E8D9D0;border-radius:24px">
<tr><td style="padding:24px;border-bottom:1px solid #E8D9D0;font-size:28px;font-weight:700;color:#9A4B32">nexqori.</td></tr>
<tr><td style="padding:28px 24px"><h1 style="font-family:Georgia,serif;font-size:30px;font-weight:400;margin:0 0 18px">{escape(title)}</h1><p style="line-height:1.7">{escape(intro)}</p><p style="padding:20px;background:#F7F2ED;border-radius:12px;line-height:1.7">{escape(label)}<br><strong>{escape(case_id)}</strong></p><p style="line-height:1.7">{escape(next_step)}</p></td></tr>
<tr><td style="padding:20px 24px;border-top:1px solid #E8D9D0;color:#735C50;font-size:12px">Nexqori · {escape(_COPY[locale]['footer'])}</td></tr></table></td></tr></table></body></html>'''
    return 'Nexqori · '+title,plain,html
