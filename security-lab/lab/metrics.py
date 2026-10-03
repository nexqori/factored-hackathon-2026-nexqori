from collections import Counter
from .catalog import CATALOG


def fraction(n, d):
    return {"numerator": n, "denominator": d, "value": n/d if d else None}


def summarize(results, catalog=None):
    # One assessment only. Never aggregate distinct modes into one rate.
    catalog = catalog or CATALOG
    applicable = [c for c in catalog if c["mode"] != "not_applicable"]
    executed = [r for r in results if r["evidence"].get("executed")]
    conclusive = [r for r in executed if r["verdict"] in ("passed", "failed")]
    attacks = [r for r in conclusive if not r["benign"] and r["attack_success"] is not None]
    telemetry = [r for r in executed if not r["benign"] and r["detected"] is not None]
    controls = [r for r in executed if r["benign"] and r["detected"] is not None]
    categories = {}
    for cat in sorted({c["category"] for c in catalog}):
        ids = {c["id"] for c in applicable if c["category"] == cat}
        done = {r["case_id"] for r in executed if r["case_id"] in ids}
        categories[cat] = fraction(len(done), len(ids))
    durations = sorted(r["duration_ms"] for r in executed if r["duration_ms"] is not None)
    return dict(
        coverage=fraction(len({r["case_id"] for r in executed if r["applicability"] != "not_applicable"}), len(applicable)),
        conclusive=fraction(len(conclusive), len(executed)),
        asr=fraction(sum(r["attack_success"] is True for r in attacks), len(attacks)),
        detection=fraction(sum(r["detected"] is True for r in telemetry), len(telemetry)),
        false_positives=fraction(sum(r["detected"] is True for r in controls), len(controls)),
        verdicts=dict(Counter(r["verdict"] for r in results)),
        blocked=sum(r["applicability"] == "blocked" for r in results),
        infrastructure_errors=sum(r["status"] == "error" for r in results),
        categories=categories, duration_ms=sum(durations),
        p50_ms=durations[len(durations)//2] if durations else None,
        p95_ms=durations[min(len(durations)-1, int(len(durations)*.95))] if durations else None,
        tokens=None, cost=None,
    )
