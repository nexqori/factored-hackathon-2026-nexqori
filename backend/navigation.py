"""Allowlisted navigation tool; no arbitrary URL, SQL, role or banking action."""
from typing import Literal
from pydantic import BaseModel, ConfigDict
Destination = Literal["home","products","movements","requests","services","help","accounts","cards","transfers","payments","loans","investments","insurance","cash"]
ROUTES = {
    "home":"/", "products":"/products", "movements":"/movements", "requests":"/requests",
    "services":"/services", "help":"/help", "accounts":"/products?kind=accounts", "cards":"/products?kind=cards",
    "transfers":"/services/transfers", "payments":"/services/payments", "loans":"/services/loans",
    "investments":"/services/investments", "insurance":"/services/insurance", "cash":"/services/cash"
}
class NavigateInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    destination: Destination

def navigate_in_app(destination, role):
    command=NavigateInput(destination=destination)
    if role!="customer":
        raise PermissionError("forbidden")
    return {"tool":"navigate_in_app","destination":command.destination,"route":ROUTES[command.destination]}

NAVIGATION_TOOL = {
    "name":"navigate_in_app",
    "description":"Open an authorized customer screen in Nexqori. Does not execute banking operations.",
    "parameters":NavigateInput.model_json_schema()
}
