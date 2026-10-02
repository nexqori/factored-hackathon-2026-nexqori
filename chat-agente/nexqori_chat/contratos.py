from __future__ import annotations

import copy
import hashlib
import json
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


class AgentError(RuntimeError):
    def __init__(self, code: str, message: str, stage: str = ''):
        super().__init__(message)
        self.code, self.stage = code, stage


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise AgentError(code, message)


def parse_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'INVALID_DATE', 'Fecha sin zona horaria.')
    return parsed


@dataclass(frozen=True)
class UserMessage:
    user_id: str
    text: str
    language: str
    timestamp: str
    message_id: str
    conversation_id: str | None = None
    channel: str = 'text'
    audio_ref: str | None = None  # Referencia privada; no se descarga ni envía al modelo.

    def validate(self) -> None:
        require(isinstance(self.user_id, str) and 0 < len(self.user_id) <= 64, 'INVALID_USER', 'user_id requerido.')
        require(isinstance(self.text, str) and 0 < len(self.text.strip()) <= 4000, 'INVALID_TEXT', 'Texto requerido, máximo 4000 caracteres.')
        require(self.language in {'es', 'en', 'pt'}, 'INVALID_LANGUAGE', 'Idioma no admitido.')
        require(self.channel in {'text', 'voice'}, 'INVALID_CHANNEL', 'Canal no admitido.')
        require(isinstance(self.message_id, str) and 0 < len(self.message_id) <= 100, 'INVALID_MESSAGE_ID', 'message_id requerido.')
        if self.conversation_id is not None:
            uuid.UUID(self.conversation_id)
        parse_date(self.timestamp)
        require(self.audio_ref is None or (isinstance(self.audio_ref, str) and len(self.audio_ref) <= 500), 'INVALID_AUDIO_REF', 'Referencia de audio inválida.')


@dataclass
class Conversation:
    id: str
    user_id: str
    created_at: str = field(default_factory=now)
    version: int = 0
    messages: list[dict] = field(default_factory=list)
    fields: dict = field(default_factory=dict)
    field_sources: dict = field(default_factory=dict)
    intent: str | None = None
    action_id: str | None = None
    question: str | None = None
    misunderstood_replies: int = 0
    clarification_rounds: int = 0
    status: str = 'new'
    cache: dict = field(default_factory=dict, repr=False)

    def model_context(self) -> dict:
        # Identidad/token nunca son parte del prompt. El historial lo conserva el servidor.
        return {'messages': [{k: m[k] for k in ('role', 'text', 'language', 'timestamp')} for m in self.messages],
                'pending_question': self.question, 'intent': self.intent,
                'action_id': self.action_id, 'fields': copy.deepcopy(self.fields)}

    def snapshot(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k != 'cache'}


class Trace:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.events: list[dict] = []

    def add(self, stage: str, **payload) -> None:
        self.events.append({'id': str(uuid.uuid4()), 'stage': stage, 'created_at': now(), **copy.deepcopy(payload)})

    def call(self, stage: str, function: Callable, *args, **kwargs):
        self.add(stage, status='started')
        try:
            result = function(*args, **kwargs)
            self.add(stage, status='completed')
            return result
        except Exception as exc:
            frames = [{'file': f.filename.replace('\\', '/').split('/')[-1], 'line': f.lineno, 'function': f.name}
                      for f in traceback.extract_tb(exc.__traceback__)]
            error = {'code': exc.code if isinstance(exc, AgentError) else type(exc).__name__,
                     'message': str(exc) if isinstance(exc, AgentError) else 'Fallo externo; revisar tipo/código y origen.',
                     'stage': exc.stage if isinstance(exc, AgentError) and exc.stage else stage,
                     'exception_type': type(exc).__name__, 'frames': frames}
            if getattr(exc, 'sqlstate', None):
                error['sqlstate'] = exc.sqlstate
            if getattr(exc, 'response', None) is not None:
                error['http_status'] = exc.response.status_code
            self.add(stage, status='error', error=error)
            wrapped = AgentError(error['code'], error['message'], error['stage'])
            raise wrapped from None
