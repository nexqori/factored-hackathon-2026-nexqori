"""Versioned local request procedures. Classification never executes them."""
import json
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_name("workflow_catalog.json").read_text(encoding="utf-8"))
WORKFLOWS = {item["id"]: item for item in CATALOG["items"]}

def workflow_view(service_id, locale):
    workflow = WORKFLOWS.get(service_id)
    if not workflow:
        return None
    return {"id": service_id, "version": CATALOG["version"], "steps": workflow["steps"][locale],
            "requiredFields": workflow["requiredFields"], "family": "problem", "availableActions": workflow.get("availableActions", []), "executesFinancialOperation": False}
