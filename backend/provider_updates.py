"""Controlled public tariff source and reader; never an authority to settle a claim.

The example endpoint and in-process transport share one document. No customer,
account or phone reference is sent to a provider. External URLs are not accepted.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import unicodedata
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select

from .models import AuditEvent, BillPayment, PhoneBill
from .security import admin, admin_write, db_session

SOURCE_ID = 'empresa-telefonica-tarifas'
SOURCE_PATH = '/api/provider-examples/phone-bill/telefono-esencial'
PROVIDER_ID = 'empresa-telefonica'
PLAN_ID = 'telefono-esencial'
SERVICE_ID = 'phone-bill'
MAX_HISTORY = 20
MAX_CACHE_BYTES = 128_000
SOURCE_LIMITATION = 'published_price_does_not_verify_customer_contract'


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                   if not unicodedata.combining(c)).strip()


class PublishExample(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    preset: Literal['usual', 'increase']
    confirmed: Literal[True]

    @field_validator('confirmed', mode='before')
    @classmethod
    def confirmation_is_boolean(cls, value):
        if value is not True:
            raise ValueError('confirmation_required')
        return value


class RefreshSource(BaseModel):
    model_config = ConfigDict(extra='forbid')


def example_document(preset, revision, published_at):
    increased = preset == 'increase'
    return {
        'schemaVersion': 1, 'sourceId': SOURCE_ID, 'sourceKind': 'controlled_example',
        'providerId': PROVIDER_ID, 'providerName': 'Empresa Telefónica',
        'serviceId': SERVICE_ID, 'planId': PLAN_ID, 'planName': 'Teléfono Esencial',
        'currency': 'MXN', 'billingPeriod': 'month', 'revision': revision,
        'priceMinor': 45900 if increased else 29900,
        'previousPriceMinor': 29900 if increased else None,
        'effectiveDate': '2026-10-01' if increased else '2026-09-01',
        'publishedAt': published_at, 'sourceUrl': SOURCE_PATH,
        'announcementType': 'price_change' if increased else 'current_price',
        'customerContractVerified': False,
    }


def parse_example_document(document, fetched_at):
    """Accept only the versioned, controlled source contract; not free-form text."""
    if not isinstance(document, dict):
        raise ValueError('provider_schema_invalid')
    preset = 'increase' if document.get('announcementType') == 'price_change' else 'usual'
    revision, published = document.get('revision'), document.get('publishedAt')
    if type(revision) is not int or not 1 <= revision <= 1_000_000:
        raise ValueError('provider_schema_invalid')
    if not isinstance(published, str) or len(published) > 40:
        raise ValueError('provider_schema_invalid')
    try:
        if datetime.fromisoformat(published).utcoffset() is None:
            raise ValueError('provider_schema_invalid')
    except (TypeError, ValueError):
        raise ValueError('provider_schema_invalid') from None
    if document != example_document(preset, revision, published):
        raise ValueError('provider_schema_invalid')
    canonical = json.dumps(document, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return {
        **deepcopy(document), 'fetchedAt': fetched_at,
        'contentHash': hashlib.sha256(canonical.encode()).hexdigest(),
        'provenance': {'adapter': 'controlled-json-v1', 'transport': 'in_process_endpoint',
                       'sourceKind': 'controlled_example'},
        'limitation': SOURCE_LIMITATION,
    }


class ProviderUpdates:
    """Single-process public-source cache. An optional file survives API restarts."""

    def __init__(self, *, enabled=False, cache_path=None, watch_seconds=0, clock=timestamp):
        self.enabled = enabled
        self.cache_path = Path(cache_path) if cache_path else None
        self.watch_seconds = max(30, min(int(watch_seconds), 86400)) if watch_seconds else 0
        self.clock = clock
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None
        self.source = example_document('usual', 1, clock())
        self.observations = []
        self.last_attempt = None
        self.last_error = None
        self.persistence_error = False
        self._load()

    @classmethod
    def from_env(cls):
        try:
            interval = int(os.getenv('PROVIDER_EXAMPLES_WATCH_SECONDS', '0'))
        except ValueError:
            interval = 0
        return cls(enabled=os.getenv('PROVIDER_EXAMPLES_ENABLED', 'false').lower() == 'true',
                   cache_path=os.getenv('PROVIDER_EXAMPLES_CACHE'), watch_seconds=interval)

    def _load(self):
        if not self.enabled or not self.cache_path or not self.cache_path.exists():
            return
        try:
            if self.cache_path.stat().st_size > MAX_CACHE_BYTES:
                raise ValueError('cache_too_large')
            saved = json.loads(self.cache_path.read_text(encoding='utf-8'))
            if set(saved) != {'source', 'observations'} or not isinstance(saved['observations'], list):
                raise ValueError('invalid_cache')
            source = saved['source']
            parse_example_document(source, self.clock())
            observations = []
            for row in saved['observations'][-MAX_HISTORY:]:
                raw = {k: row[k] for k in source}
                fetched = row['fetchedAt']
                if datetime.fromisoformat(fetched).utcoffset() is None:
                    raise ValueError('invalid_cache')
                checked = parse_example_document(raw, fetched)
                # Hash and source metadata are recomputed; cache contents cannot add instructions.
                observations.append(checked)
            self.source, self.observations = source, observations
        except (OSError, ValueError, KeyError, TypeError):
            self.persistence_error = True

    def _save(self):
        if not self.cache_path:
            return
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.cache_path.with_name(self.cache_path.name + '.tmp')
            temp.write_text(json.dumps({'source': self.source, 'observations': self.observations},
                                       ensure_ascii=False), encoding='utf-8')
            temp.replace(self.cache_path)
            self.persistence_error = False
        except OSError:
            self.persistence_error = True

    def public_document(self):
        if not self.enabled:
            raise HTTPException(404, 'not_found')
        with self.lock:
            return deepcopy(self.source)

    def publish(self, preset):
        if not self.enabled:
            raise HTTPException(409, 'provider_examples_disabled')
        if preset not in ('usual', 'increase'):
            raise ValueError('invalid_preset')
        with self.lock:
            desired_price = 45900 if preset == 'increase' else 29900
            changed = self.source['priceMinor'] != desired_price
            if changed:
                self.source = example_document(preset, self.source['revision'] + 1, self.clock())
                self._save()
            # Publishing and observing are different operations: the reader detects it later.
            return {'published': changed, 'source': deepcopy(self.source)}

    def refresh(self):
        if not self.enabled:
            raise HTTPException(409, 'provider_examples_disabled')
        with self.lock:
            self.last_attempt = self.clock()
            try:
                observation = parse_example_document(self.public_document(), self.last_attempt)
                previous = self.observations[-1] if self.observations else None
                changed = bool(previous and previous['priceMinor'] != observation['priceMinor'])
                if not previous or previous['contentHash'] != observation['contentHash']:
                    self.observations.append(observation)
                    self.observations = self.observations[-MAX_HISTORY:]
                else:
                    self.observations[-1] = observation
                self.last_error = None
                self._save()
                return {'status': 'available', 'detectedPriceChange': changed,
                        'previousObservedPriceMinor': previous['priceMinor'] if previous else None,
                        'observation': deepcopy(observation)}
            except (ValueError, KeyError, TypeError):
                self.last_error = 'provider_schema_invalid'
                return {'status': 'unavailable', 'error': self.last_error, 'observation': None}

    def view(self, query=''):
        with self.lock:
            match = not query or normalized(query) in normalized('Empresa Telefónica teléfono celular móvil phone mobile plano plan Teléfono Esencial telefono-esencial phone-bill')
            latest = self.observations[-1] if self.observations else None
            return {
                'enabled': self.enabled, 'automaticRefreshSeconds': self.watch_seconds,
                'cachePersistent': self.cache_path is not None,
                'persistenceError': self.persistence_error,
                'sources': [{
                    'id': SOURCE_ID, 'providerName': 'Empresa Telefónica', 'planName': 'Teléfono Esencial',
                    'sourceUrl': SOURCE_PATH, 'sourceKind': 'controlled_example',
                    'status': ('disabled' if not self.enabled else 'unavailable' if self.last_error
                               else 'available' if latest else 'not_checked'),
                    'lastAttemptAt': self.last_attempt, 'error': self.last_error,
                    'publishedRevision': self.source['revision'],
                    'publishedPriceMinor': self.source['priceMinor'],
                    'needsRefresh': not latest or latest['revision'] != self.source['revision'],
                    'observation': deepcopy(latest), 'history': deepcopy(list(reversed(self.observations))),
                    'customerContractVerified': False,
                }] if match else [],
            }

    def lookup(self, *, service_id, provider_id, plan_id, charge_date, currency, billing_period=None):
        """Exact plan lookup using existing server-side evidence, never fuzzy merchant matching."""
        empty = {'status': 'not_linked', 'customerContractVerified': False, 'authorizesAction': False}
        if not self.enabled:
            return {**empty, 'status': 'disabled'}
        if (service_id, provider_id, plan_id, currency) != (SERVICE_ID, PROVIDER_ID, PLAN_ID, 'MXN'):
            return empty
        try:
            day = date.fromisoformat(str(charge_date)[:10])
        except (ValueError, TypeError):
            return {**empty, 'status': 'period_required'}
        with self.lock:
            # The owned source is a local endpoint adapter, so the read is bounded and has no network.
            result = self.refresh()
            if result['status'] != 'available':
                return {**empty, 'status': 'unavailable'}
            observed = result['observation']
            active = day >= date.fromisoformat(observed['effectiveDate'])
            # A September bill paid in October must not inherit October's price.
            period_matches = None
            if billing_period is not None:
                try:
                    first_day = date.fromisoformat(str(billing_period) + '-01')
                    period_matches = first_day >= date.fromisoformat(observed['effectiveDate'])
                except ValueError:
                    return {**empty, 'status': 'period_required'}
            return {**empty, 'status': 'candidate' if active and period_matches is not False else 'not_yet_effective',
                    'matchesPublishedPlan': True, 'effectiveForChargeDate': active,
                    'billPeriod': billing_period, 'effectiveForBillMonth': period_matches,
                    'observation': observed,
                    'checksRemaining': ['customer_contract', 'billing_period', 'extras_and_discounts', 'payment_status']}

    def start(self):
        if not self.enabled or not self.watch_seconds or self.thread is not None:
            return
        def run():
            while not self.stop_event.wait(self.watch_seconds):
                self.refresh()
        self.thread = threading.Thread(target=run, name='provider-example-reader', daemon=True)
        self.thread.start()

    def shutdown(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=2)


def price_context(db, transaction):
    """Use only a plan explicitly linked to the same owner's immutable receipt."""
    reader = db.info.get('provider_updates')
    if reader is None:
        return None
    linked = db.execute(select(BillPayment, PhoneBill).join(PhoneBill,
        (PhoneBill.id == BillPayment.bill_id) & (PhoneBill.user_id == BillPayment.user_id))
        .where(BillPayment.user_id == transaction.user_id,
               BillPayment.transaction_id == transaction.id)).first()
    if not linked:
        return None
    payment, bill = linked
    receipt = payment.receipt or {}
    if not receipt.get('providerId') or not receipt.get('planId'):
        return None
    return reader.lookup(service_id=bill.service_id, provider_id=receipt['providerId'],
                         plan_id=receipt['planId'], charge_date=transaction.occurred_at,
                         currency=transaction.currency, billing_period=bill.period)


def provider_context_text(result, locale):
    if not result or result.get('status') != 'candidate':
        return ''
    value = result['observation']
    price = f"{value['priceMinor'] / 100:.2f} {value['currency']}"
    old = f"{value['previousPriceMinor'] / 100:.2f} {value['currency']}" if value['previousPriceMinor'] else None
    plan, effective = value['planName'], value['effectiveDate']
    i = ('es', 'en', 'pt').index(locale)
    opening = (
        f"La fuente de tarifas registra {price} al mes para {plan}, vigente desde {effective}.",
        f"The tariff source lists {price} per month for {plan}, effective from {effective}.",
        f"A fonte de tarifas registra {price} por mês para {plan}, com vigência a partir de {effective}.",
    )[i]
    change = ((f" Antes indicaba {old}.", f" It previously listed {old}.", f" Antes indicava {old}.")[i] if old else '')
    limit = (
        ' Falta contrastar esa publicación con tu contrato, el período y los conceptos del recibo. Esto no confirma que el cargo sea correcto ni que un pago pendiente haya terminado.',
        ' We still need to compare that publication with your contract, billing period and bill items. It does not confirm that the charge is correct or that a pending payment has completed.',
        ' Ainda precisamos comparar essa publicação com seu contrato, o período e os itens da conta. Isso não confirma que a cobrança esteja correta nem que um pagamento pendente tenha sido concluído.',
    )[i]
    return opening + change + limit


def provider_updates_router():
    router = APIRouter()

    def runtime(request: Request):
        return request.app.state.provider_updates

    @router.get(SOURCE_PATH)
    def published_source(reader=Depends(runtime)):
        return reader.public_document()

    @router.get('/api/admin/provider-updates')
    def sources(q: str = Query('', max_length=100), _user=Depends(admin), reader=Depends(runtime)):
        return reader.view(q)

    @router.post('/api/admin/provider-updates/example')
    def publish(body: PublishExample, user=Depends(admin_write), reader=Depends(runtime), db=Depends(db_session)):
        result = reader.publish(body.preset)
        db.add(AuditEvent(id=str(uuid4()), user_id=user.id, actor_id=user.id, action='provider_example_published'))
        db.commit()
        return result

    @router.post('/api/admin/provider-updates/refresh')
    def refresh(_body: RefreshSource, user=Depends(admin_write), reader=Depends(runtime), db=Depends(db_session)):
        result = reader.refresh()
        db.add(AuditEvent(id=str(uuid4()), user_id=user.id, actor_id=user.id, action='provider_source_checked'))
        db.commit()
        return result

    return router
