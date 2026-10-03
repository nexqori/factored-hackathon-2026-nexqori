"""Reproduce source suitability from existing census aggregates, without exporting text."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parents[1] / "notebooks" / "resultados_integral"


def read(name):
    return list(csv.DictReader((SOURCE / name).read_text(encoding="utf-8-sig").splitlines()))


quality = read("detalle_transcript_quality.csv")[0]
metadata = read("detalle_transcript_metadata.csv")
families = read("detalle_text_families.csv")
count = int(quality["transcripts"])
assert sum(int(row["transcripts"]) for row in metadata) == count
assert sum(int(row["transcripts"]) for row in families) == count
result = {
    "basis": "existing_full_census_aggregates_2026-09-25",
    "transcripts": count,
    "distinct_texts": int(quality["distinct_customer_texts"]),
    "text_families": len(families),
    "languages": sorted({row["language"] for row in metadata}),
    "intent_metadata": metadata,
    "families": families,
    "fit_for_broad_intent_benchmark": False,
    "sources": [{"path": f"notebooks/resultados_integral/{name}", "sha256": hashlib.sha256((SOURCE / name).read_bytes()).hexdigest()} for name in ("detalle_transcript_quality.csv", "detalle_transcript_metadata.csv", "detalle_text_families.csv")],
}
complaints_source = ROOT.parents[1] / "notebooks" / "servicios_nexqori" / "complaint_needs.csv"
complaints = list(csv.DictReader(complaints_source.read_text(encoding="utf-8-sig").splitlines()))
label_map = {"Cargo no reconocido": "unrecognized-charge", "Cobro indebido": "incorrect-charge", "Problema con app": "app-support", "Atención en sucursal": "branch-support", "Calidad de servicio": "service-feedback", "(sin subcategoría)": "needs-clarification"}
assert sum(int(row["cases"]) for row in complaints) == 67095
result["problems"] = [{"source_label": row["subcategory"], "intent": label_map[row["subcategory"]], "records": int(row["cases"]), "denominator": 67095, "sla_flagged": int(row["sla_flagged"]), "unit": "complaint", "source": "notebooks/servicios_nexqori/complaint_needs.csv"} for row in complaints]
result["contact_reasons"] = [{"source_label": row["reason"], "records": int(row["interactions"]), "unresolved": int(row["unresolved"]), "denominator": 686296, "unit": "interaction"} for row in csv.DictReader((ROOT.parents[1] / "notebooks" / "servicios_nexqori" / "contact_needs.csv").read_text(encoding="utf-8-sig").splitlines())]
result["digital_errors"] = [{"action": row["action"], "events": int(row["events"]), "errors": int(row["error_events"]), "unit": "event"} for row in read("detalle_technical_actions.csv")]
for source in (complaints_source, ROOT.parents[1] / "notebooks" / "servicios_nexqori" / "contact_needs.csv", SOURCE / "detalle_technical_actions.csv"):
    result["sources"].append({"path": source.relative_to(ROOT.parents[1]).as_posix(), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
(ROOT / "evidence.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"transcripts": count, "distinct_texts": result["distinct_texts"], "text_families": len(families)}))
