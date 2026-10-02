from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import re
from urllib.parse import quote

from jsonschema import Draft202012Validator
from dotenv import dotenv_values
from .contratos import require, digest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config'


def read_environment():
    """Root .env < chat-agente/.env < entorno del proceso; sin modificar os.environ.

    Valores vacíos no borran una configuración anterior. Sin interpolación para
    conservar literalmente contraseñas que contengan ${...}.
    """
    values = {}
    for path in (ROOT.parent / '.env', ROOT / '.env'):
        if path.is_file():
            values.update({k: v for k, v in dotenv_values(path, interpolate=False).items() if v not in (None, '')})
    values.update({k: v for k, v in os.environ.items() if v != ''})
    return values


def resolve_database_url(values, explicit=None):
    """Mismo rol/base/host que Compose, sin crear engine ni abrir conexiones."""
    if explicit is not None:
        require(isinstance(explicit, str) and bool(explicit.strip()), 'INVALID_DATABASE_URL', 'database_url explícita está vacía.')
        return explicit
    if values.get('DATABASE_URL'):
        return values['DATABASE_URL']
    password = values.get('APP_DATABASE_PASSWORD')
    require(bool(password), 'MISSING_DATABASE_URL', 'Configurar DATABASE_URL o APP_DATABASE_PASSWORD para construir la conexión.')
    host = values.get('PGHOST', 'db')
    port = values.get('PGPORT', '5432')
    require(bool(re.fullmatch(r'[A-Za-z0-9._-]+', host)), 'INVALID_DATABASE_HOST', 'PGHOST debe ser un nombre de host TCP o IPv4.')
    require(port.isdecimal() and 1 <= int(port) <= 65535, 'INVALID_DATABASE_PORT', 'PGPORT inválido.')
    user = quote(values.get('PGUSER', 'nexqori_app'), safe='')
    database = quote(values.get('PGDATABASE', 'nexqori'), safe='')
    return f'postgresql://{user}:{quote(password, safe="")}@{host}:{port}/{database}'


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
        values = read_environment()
        return cls(openai_key=values.get('OPENAI_API_KEY', ''), typesafe_key=values.get('TYPESAFE_API_KEY', ''),
                   database_url=resolve_database_url(values, database_url),
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
