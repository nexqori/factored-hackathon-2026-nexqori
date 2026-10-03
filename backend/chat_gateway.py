"""Puente de sesión HTTP a chat-agente. Sin persistencia ni herramientas de escritura."""
import os
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, func

from .models import Session, User, Product
from .security import digest

# El paquete independiente conserva su ubicación y sus contratos versionados.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "chat-agente"))
from nexqori_chat.codigo1_orquestador import ChatAgent
from nexqori_chat.config import Settings
from nexqori_chat.contratos import UserMessage, now
from nexqori_chat.postgres import PostgresRepository
from nexqori_chat.proveedores import Providers
from nexqori_chat.mensajes import accion_pendiente
from .chat_actions import ChatActions


class ChatGateway:
    """Un worker; estado por cookie, 30 min de inactividad, cuotas acotadas."""
    def __init__(self, engine, sessions, *, mode=None, settings=None,
                 repository=None, provider_factory=Providers):
        self.sessions = sessions
        self.mode = mode or os.getenv("CHAT_AGENT_MODE", "rules")
        if self.mode not in {"agent", "rules"}:
            raise ValueError("CHAT_AGENT_MODE debe ser agent o rules")
        self.settings = settings or Settings(
            database_url=engine.url.render_as_string(hide_password=False),
            openai_key=os.getenv("OPENAI_API_KEY", ""),
            typesafe_key=os.getenv("TYPESAFE_API_KEY", ""),
            allow_api=True,
            allow_external_data=os.getenv("CHAT_AGENT_ALLOW_EXTERNAL_DATA", "false").lower() == "true",
            timeout_s=20, max_calls_per_turn=10)
        self.repository = repository or PostgresRepository(self.settings)
        self.provider_factory = provider_factory
        self.actions = ChatActions(self)
        self.entries = {}
        self.lock = threading.RLock()

    def forget(self, token):
        with self.lock:
            self.entries.pop(digest(token), None)
        self.actions.forget(token)

    def authorize(self, token, user_id):
        # Una sesión nueva evita reutilizar la identidad almacenada antes de una llamada larga.
        with self.sessions() as db:
            session = db.get(Session, digest(token))
            user = db.get(User, user_id)
            if not session or session.user_id != user_id or session.expires_at <= time.time():
                raise HTTPException(401, "unauthorized")
            if not user or user.role != "customer":
                raise HTTPException(403, "forbidden")

    def handle(self, payload, token, user_id):
        self.authorize(token, user_id)
        if self.mode == "rules":
            return self._baseline(payload, user_id)
        key = digest(token)
        with self.lock:
            cutoff = time.monotonic() - 1800
            self.entries = {k: v for k, v in self.entries.items() if v["used"] > cutoff or v["busy"]}
            if key not in self.entries:
                if len(self.entries) >= 100:
                    raise HTTPException(429, "chat_busy")
                self.entries[key] = {"agent": ChatAgent(self.settings, self.repository,
                    provider_factory=self.provider_factory, document_handler=self.actions.document,
                    human_handler=lambda conversation, context: self.actions.offer(conversation, context, token)), "used": time.monotonic(),
                    "busy": False, "messages": {}}
            entry = self.entries[key]
            if entry["busy"]:
                raise HTTPException(409, "chat_busy")
            agent = entry["agent"]
            if payload.conversationId and payload.conversationId not in agent.store.conversations:
                raise HTTPException(409, "chat_expired")
            message_id = payload.messageId or str(uuid4())
            fingerprint = (payload.message.strip(), payload.locale, payload.conversationId)
            previous = entry["messages"].get(message_id)
            if previous and previous[0] != fingerprint:
                raise HTTPException(409, "chat_conflict")
            if not previous and len(entry["messages"]) >= 60:
                raise HTTPException(429, "chat_limit")
            # Timestamp del servidor estable para reintentos HTTP con el mismo messageId.
            timestamp = previous[1] if previous else now()
            entry["messages"][message_id] = (fingerprint, timestamp)
            entry["busy"] = True
        try:
            result = agent.handle_message(UserMessage(user_id, payload.message.strip(), payload.locale,
                timestamp, message_id, payload.conversationId), session_token=token)
            self.authorize(token, user_id)
            # Allowlist: nunca devolver persistence, SQL, prompts, claves ni órdenes ejecutables.
            public = {"text": result["text"], "status": result["status"],
                "conversationId": result["conversation_id"] if result["status"] != "error" else None,
                "traceId": result["trace_id"], "destination": None, "navigation": None,
                "execution_authorized": False}
            for field in ("document", "handoff"):
                if field in result: public[field] = result[field]
            return public
        finally:
            with self.lock:
                entry["busy"] = False
                entry["used"] = time.monotonic()

    def _baseline(self, payload, user_id):
        """Fallback explícito y local; nunca se activa por fallo de un proveedor."""
        from .assistant import answer
        with self.sessions() as db:
            balance = db.scalar(select(func.coalesce(func.sum(Product.balance_minor), 0)).where(
                Product.user_id == user_id, Product.type.in_(["account", "savings"]), Product.currency == "MXN"))
        result = answer(payload.message, payload.locale, balance, payload.currentPage)
        if result["intent"] == "balance":
            result["text"] = result["text"].split(" MXN.")[0] + " MXN."
        elif result["intent"] == "unknown":
            result["text"] = {"es": "No entendí tu solicitud. ¿Puedes escribirla de nuevo?",
                "en": "I did not understand your request. Could you write it again?",
                "pt": "Não entendi sua solicitação. Pode escrevê-la novamente?"}[payload.locale]
        if result["intent"] not in {"balance", "unknown", "restricted"}:
            kind = {"report": "complaint", "human": "human", "documents": "document"}.get(result["intent"], "navigate")
            result.update(accion_pendiente(kind, payload.locale))
        return {**result, "destination": None, "navigation": None, "conversationId": None,
            "status": result.get("status", "answered"), "execution_authorized": False}
