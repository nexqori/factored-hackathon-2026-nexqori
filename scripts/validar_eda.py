"""Comprobaciones del EDA: denominadores y contraste independiente CSV/SQL."""
from __future__ import annotations
import csv
import json
from pathlib import Path

import pandas as pd

from eda_problemas import CACHE, DATA, OUT, connect, save_json


def validate():
    checks = []
    def check(name, actual, expected):
        ok = bool(actual == expected)
        checks.append({"check": name, "passed": ok, "actual": int(actual), "expected": int(expected)})
        if not ok:
            raise AssertionError(f"{name}: {actual} != {expected}")
    get = lambda name: pd.read_csv(OUT / f"{name}.csv")
    coverage = get("coverage").set_index("table")
    calls = get("calls_overall").iloc[0]
    cases = get("complaints_overall").iloc[0]
    for name, column, total in [
        ("calls_by_reason", "interactions", calls.interactions),
        ("calls_by_channel", "interactions", calls.interactions),
        ("calls_by_reason", "unresolved", calls.unresolved),
        ("calls_monthly", "unresolved", calls.unresolved),
        ("complaints_by_category", "cases", cases.cases),
        ("complaints_by_status", "cases", cases.cases),
        ("complaints_by_type", "cases", cases.cases),
        ("complaints_by_category", "sla_breached", cases.sla_breached),
        ("complaints_monthly", "sla_breached", cases.sla_breached),
        ("transactions_status", "transactions", coverage.loc["transactions", "analysis_rows"]),
        ("digital_channels", "events", coverage.loc["digital_events", "analysis_rows"]),
        ("digital_categories", "error_events", get("digital_channels").error_events.sum()),
    ]:
        check(f"Conciliación {name}.{column}", get(name)[column].sum(), total)
    for table, row in coverage.iterrows():
        check(f"Balance filas {table}", row.raw_rows, row.analysis_rows+row.projected_duplicate_rows+row.null_key_rows+row.conflicting_distinct_rows)
    check("El JOIN no multiplica casos", get("complaint_call_links").iloc[0].cases, cases.cases)
    for name, num, denom, pct in [("calls_by_reason", "unresolved", "resolution_known", "unresolved_pct"), ("complaints_by_category", "sla_breached", "sla_known", "sla_breached_pct"), ("digital_channels", "error_events", "type_known", "error_pct")]:
        d = get(name)
        ok = ((d[num]/d[denom]*100-d[pct]).abs()<1e-8).all()
        check(f"Porcentajes recalculados {name}", int(ok), 1)
    # A genuinely separate CSV parser verifies two endpoint files per core table.
    plan = json.loads((CACHE / "source_selection.json").read_text(encoding="utf-8"))
    con = connect()
    try:
        for table, short, pk, flag, desired in [
            ("call_center_interactions", "calls", "interaction_id", "was_resolved", "False"),
            ("complaints", "cases", "complaint_id", "sla_breached", "True"),
        ]:
            files = plan["sources"][table]
            for item in (files[0], files[-1]):
                with (DATA / item["path"]).open(encoding="utf-8-sig", newline="") as f:
                    rows = list(csv.DictReader(f))
                ids = [r[pk] for r in rows]
                counts = con.execute(f"SELECT count(*),count(*) FILTER(WHERE {flag}=?) FROM raw_{short} WHERE {pk} IN (SELECT unnest(?))", [desired,ids]).fetchone()
                check(f"CSV independiente {table} {item['day']} filas", counts[0], len(rows))
                check(f"CSV independiente {table} {item['day']} {flag}", counts[1], sum(r[flag]==desired for r in rows))
        # Check source raw strings, not a join artefact or failed cast.
        actual = con.execute("SELECT count(*) FROM raw_cases WHERE origin_interaction_id IS NOT NULL").fetchone()[0]
        check("Enlaces declarados: nulos comprobados en texto fuente", actual, get("complaint_call_links").iloc[0].declared_links)
    finally:
        con.close()
    save_json(OUT / "validacion.json", checks)
    return pd.DataFrame(checks)


if __name__ == "__main__":
    result = validate()
    print(f"{len(result)} comprobaciones satisfactorias.")
