"""Allowlisted navigation tool; no arbitrary URL, SQL, role or banking action."""
from typing import Literal
from pydantic import BaseModel, ConfigDict
from datetime import date
from urllib.parse import urlencode
import re
from .catalog import SERVICES
Destination = Literal["home","products","movements","requests","complaints","documents","services","help","accounts","cards","transfers","payments","loans","investments","insurance","cash","settings"]
ROUTES = {
    "home":"/", "products":"/products", "movements":"/movements", "requests":"/requests", "complaints":"/complaints", "documents":"/documents",
    "services":"/services", "help":"/help", "accounts":"/products?kind=accounts", "cards":"/cards",
    "transfers":"/services/transfers", "payments":"/services/payments", "loans":"/services/loans",
    "investments":"/services/investments", "insurance":"/services/insurance", "cash":"/services/cash", "settings":"/settings"
}
class NavigateInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    destination: Destination
    serviceId: str | None = None

def navigate_in_app(destination, role, service_id=None, *, filters=None):
    command=NavigateInput(destination=destination,serviceId=service_id)
    if role!="customer":
        raise PermissionError("forbidden")
    if filters is not None:
        if destination!='movements' or service_id or not filters or set(filters)-{'start','end','product'}:raise ValueError('Invalid filters')
        if bool(filters.get('start'))!=bool(filters.get('end')):raise ValueError('Incomplete period')
        if filters.get('start'):
            start,end=date.fromisoformat(filters['start']),date.fromisoformat(filters['end'])
            if start.isoformat()!=filters['start'] or end.isoformat()!=filters['end'] or start>end or (end-start).days>366:raise ValueError('Invalid period')
        if 'product' in filters and not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',filters['product']):raise ValueError('Invalid product')
        ordered={key:filters[key] for key in ('start','end','product') if key in filters}
        return {'tool':'navigate_in_app','destination':'movements','filters':ordered,'route':'/movements?'+urlencode(ordered)}
    if service_id is not None:
        if destination!="services" or service_id not in SERVICES: raise ValueError("Unknown service destination")
        return {"tool":"navigate_in_app","destination":"services","serviceId":service_id,"route":"/services/catalog/"+service_id}
    return {"tool":"navigate_in_app","destination":command.destination,"route":ROUTES[command.destination]}

NAVIGATION_TOOL = {
    "name":"navigate_in_app",
    "description":"Open an authorized customer screen in Nexqori. Does not execute banking operations.",
    "parameters":NavigateInput.model_json_schema()
}
