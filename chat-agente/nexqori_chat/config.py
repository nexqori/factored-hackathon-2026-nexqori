from dataclasses import dataclass, field
from pathlib import Path
import json
import os

from jsonschema import Draft202012Validator
from .contratos import require, digest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config'


@dataclass(frozen=True)
class Settings:
    openai_key: str = field(default='', repr=False)
    typesafe_key: str = field(default='', repr=False)
    database_url: str = field(default='', repr=False)
    allow_api: bool = False
    allow_external_data: bool = False
    jev_model: str = 'jev-1.13.0'
    llm_model: str = 'gpt-6-luna'
    timeout_s: float = 90
    max_calls_per_turn: int = 10
    max_rows: int = 20
    max_messages: int = 40
    max_payload_bytes: int = 120000
    max_clarification_rounds: int = 8

    @classmethod
    def from_env(cls, *, allow_api=False, allow_external_data=False, database_url=None):
        # No carga .env ni abre conexiones implícitamente. CLI carga .env explícitamente.
        return cls(openai_key=os.getenv('OPENAI_API_KEY', ''), typesafe_key=os.getenv('TYPESAFE_API_KEY', ''),
                   database_url=database_url or os.getenv('DATABASE_URL', ''),
                   allow_api=allow_api, allow_external_data=allow_external_data)


def load_contracts():
    taxonomy = json.loads((CONFIG / 'intent-taxonomy.json').read_text(encoding='utf-8'))
    rules = json.loads((CONFIG / 'reglas_resolucion.json').read_text(encoding='utf-8'))
    schema = json.loads((CONFIG / 'reglas_resolucion.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator(schema).validate(rules)
    require({i['id'] for i in taxonomy['intents']} == set(rules['rules']), 'CONTRACT_MISMATCH', 'Taxonomía y reglas no coinciden.')
    require('report' not in rules['rules'], 'COMPLAINT_IN_CONTRACT', 'El contrato no admite tramitar reclamos.')
    return taxonomy, rules, {'taxonomy': taxonomy['version'], 'rules': rules['version'],
                            'rules_sha256': digest((CONFIG / 'reglas_resolucion.json').read_text(encoding='utf-8'))}
