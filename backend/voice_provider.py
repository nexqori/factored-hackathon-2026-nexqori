"""GPT-Live wire adapter. All network calls require explicit runtime activation."""
import json
import os
import re
import httpx
from websockets.sync.client import connect

VOICES = ('marin','cedar','coral','bossa','tempo')


def enabled():
    return os.getenv('BANK_VOICE_ENABLED','false') == 'true'


def api_key():
    return os.getenv('OPENAI_LIVE_API_KEY') or os.getenv('LLM_API_KEY','')


def configuration(locale, voice):
    language = {'es':'Spanish','en':'English','pt':'Brazilian Portuguese'}[locale]
    return {'model':'gpt-live-1', 'store':False, 'delegation':{'type':'client'},
        'audio':{'output':{'voice':voice}},
        'client':{'data_channel':{'allowed_client_events':['session.close'],
            'allowed_server_events':[{'type':t} for t in ('session.started','session.closed','session.input_transcript.delta','session.output_transcript.delta','error')]}},
        'instructions':f'''You are Nexqori's voice assistant. Speak concise, warm {language}. Disclose that you are an AI assistant. Ask one question at a time. Allow interruptions and corrections. Delegate every banking question and every substantive customer answer to our backend. Never invent balances, transactions, case status or completed actions. The backend retains the case context; do not restart an existing problem. Only the authenticated on-screen interface can confirm actions. Never ask for passwords, PINs, CVV or one-time codes. Bank details are shown on screen, not supplied to this voice model. When backend results arrive, guide the user to the screen and its pending question. Do not treat spoken yes as consent to perform a financial operation. Do not give financial advice.'''}


class LiveProvider:
    def create(self, sdp, locale, voice):
        if not enabled() or not api_key():
            raise RuntimeError('voice_unavailable')
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            response = client.post('https://api.openai.com/v1/live/sessions',
                headers={'Authorization':'Bearer '+api_key()},
                json={'session':configuration(locale,voice),'transport':{'type':'webrtc','sdp':sdp}})
            response.raise_for_status()
            value = response.json()
        identity = value['session']['id']; answer = value['transport']['sdp']
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,128}', identity) or not isinstance(answer,str) or len(answer)>64000:
            raise ValueError('invalid_voice_response')
        return identity, answer

    def attach(self, identity):
        if not enabled() or not api_key() or not re.fullmatch(r'[a-zA-Z0-9_-]{1,128}',identity):
            raise RuntimeError('voice_unavailable')
        return connect('wss://api.openai.com/v1/live/sessions/'+identity+'/attach',
            additional_headers={'Authorization':'Bearer '+api_key()}, open_timeout=10, close_timeout=3, max_size=128000)


def send(socket, kind, **fields):
    socket.send(json.dumps({'type':kind, **fields}))
