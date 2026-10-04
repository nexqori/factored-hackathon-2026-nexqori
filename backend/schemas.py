from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .navigation import Destination
Locale = Literal["es","en","pt"]
Service = Literal["general","accounts","cards","transfers","payments","loans","investments","insurance","cash","support"]

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class Login(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

class LocaleInput(StrictModel):
    locale: Locale

class ConfirmInput(StrictModel):
    confirmed: Literal[True]

class RequestInput(ConfirmInput):
    transactionId: str | None = Field(default=None, max_length=64)
    requestKey: str = Field(min_length=16, max_length=64, pattern=r"^[a-zA-Z0-9-]+$")
    service: Service = "general"
    reason: Literal["unknown","amount","payment","other"]
    details: str = Field(min_length=10, max_length=1000)

class ChatInput(StrictModel):
    currentPage: Destination = "home"
    message: str = Field(min_length=1, max_length=1000)
    locale: Locale

class ChatFeedbackInput(StrictModel):
    metric: Literal["nps","csat","ces"]
    score: int = Field(ge=0, le=10)
    locale: Locale
    submissionId: str = Field(min_length=36, max_length=36, pattern=r"^[0-9a-fA-F-]{36}$")
    formDurationMs: int = Field(ge=0, le=86400000)
    conversationDurationMs: int = Field(ge=0, le=604800000)
