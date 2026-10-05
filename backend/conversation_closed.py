from fastapi import HTTPException
from sqlalchemy import select
from .models import ChatDocument


def document_closed(db, conversation):
    return bool(db.scalar(select(ChatDocument.id).where(ChatDocument.conversation_id==conversation.id, ChatDocument.user_id==conversation.user_id).limit(1)))


def require_open(db, conversation):
    if document_closed(db, conversation):
        raise HTTPException(409, 'conversation_closed')
