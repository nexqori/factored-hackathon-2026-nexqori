from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from .navigation import Destination
Locale = Literal["es","en","pt"]
Service = Literal["general","accounts","cards","transfers","payments","loans","investments","insurance","cash","support"]

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class Login(StrictModel):
    identifier: str = Field(min_length=3, max_length=254, validation_alias=AliasChoices("identifier", "email"))
    password: str = Field(min_length=1, max_length=256)

class LocaleInput(StrictModel):
    locale: Locale

class CardCvvInput(StrictModel):
    revealToken: str = Field(min_length=66, max_length=90, pattern=r'^\d{1,12}\.[a-f0-9]{64}$')


class CardRevealInput(StrictModel):
    password: str = Field(min_length=1, max_length=256)

class ExperienceInput(StrictModel):
    birthDate: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    bankingExperience: Literal["new", "occasional", "frequent"]
    digitalExperience: Literal["new", "learning", "confident"]
    assistance: Literal["auto", "guided", "standard"]

class RegisterInput(ExperienceInput):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    identityNumber: str = Field(min_length=5, max_length=32)
    password: str = Field(min_length=12, max_length=128)
    locale: Locale
    textSize: Literal["small", "medium", "large"]
    confirmed: Literal[True]

class PreferencesInput(StrictModel):
    textSize: Literal["small", "medium", "large"]


class ProfileFieldInput(StrictModel):
    field: Literal['birthDate', 'bankingExperience', 'digitalExperience', 'assistance', 'textSize']
    value: str = Field(min_length=1, max_length=32)
    confirmed: Literal[True]


class ConfirmInput(StrictModel):
    confirmed: Literal[True]

class RequestInput(ConfirmInput):
    transactionId: str | None = Field(default=None, max_length=64)
    requestKey: str = Field(min_length=16, max_length=64, pattern=r"^[a-zA-Z0-9-]+$")
    service: Service = "general"
    reason: Literal["unknown","amount","payment","other"]
    details: str = Field(min_length=10, max_length=1000)

class ChatInput(StrictModel):
    conversationId: str | None = Field(default=None, min_length=1, max_length=64)
    transactionId: str | None = Field(default=None, min_length=1, max_length=64)
    currentPage: Destination = "home"
    message: str = Field(min_length=0, max_length=8000)
    pastedText: str = Field(default="", max_length=8000)
    locale: Locale

class ServiceRequestInput(ConfirmInput):
    requestKey: str = Field(min_length=16, max_length=64, pattern=r"^[a-zA-Z0-9-]+$")
    locale: Locale
    accountId: str | None = Field(default=None, max_length=64)
    reference: str = Field(default="", max_length=64)
    beneficiary: str = Field(default="", max_length=100)
    amountMinor: int | None = Field(default=None, ge=1, le=100000000)
    transactionId: str | None = Field(default=None, max_length=64)
    notes: str = Field(default="", max_length=1000)

class ChatFeedbackInput(StrictModel):
    metric: Literal["nps","csat","ces"]
    score: int = Field(ge=0, le=10)
    locale: Locale
    submissionId: str = Field(min_length=36, max_length=36, pattern=r"^[0-9a-fA-F-]{36}$")
    formDurationMs: int = Field(ge=0, le=86400000)
    conversationDurationMs: int = Field(ge=0, le=604800000)
