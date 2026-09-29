"""Allowlisted navigation tool; no arbitrary URL, SQL, role or banking action."""
from typing import Literal
from pydantic import BaseModel, ConfigDict
from .catalog import SERVICES
Destination = Literal["home","products","movements","requests","services","help","accounts","cards","transfers","payments","loans","investments","insurance","cash","settings"]
ROUTES = {
    "home":"/", "products":"/products", "movements":"/movements", "requests":"/requests",
    "services":"/services", "help":"/help", "accounts":"/products?kind=accounts", "cards":"/products?kind=cards",
    "transfers":"/services/transfers", "payments":"/services/payments", "loans":"/services/loans",
    "investments":"/services/investments", "insurance":"/services/insurance", "cash":"/services/cash", "settings":"/settings"
}
class NavigateInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    destination: Destination
    serviceId: str | None = None

def navigate_in_app(destination, role, service_id=None):
    command=NavigateInput(destination=destination,serviceId=service_id)
    if role!="customer":
        raise PermissionError("forbidden")
    if service_id is not None:
        if destination!="services" or service_id not in SERVICES: raise ValueError("Unknown service destination")
        return {"tool":"navigate_in_app","destination":"services","serviceId":service_id,"route":"/services/catalog/"+service_id}
    return {"tool":"navigate_in_app","destination":command.destination,"route":ROUTES[command.destination]}

NAVIGATION_TOOL = {
    "name":"navigate_in_app",
    "description":"Open an authorized customer screen in Nexqori. Does not execute banking operations.",
    "parameters":NavigateInput.model_json_schema()
}
