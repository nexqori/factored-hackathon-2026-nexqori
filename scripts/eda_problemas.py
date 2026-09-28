"""EDA acotado: dos tablas de atención y dos muestras por partición diaria.

Los CSV originales nunca se modifican. No carga las 13 tablas ni materializa
filas personales en pandas; sólo exporta agregados. SQL auditable en sql/eda.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import random
import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import psutil

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dataset"
CACHE = DATA / "_eda_problemas"
OUT = ROOT / "notebooks" / "resultados"
SEED = 20260925
VERSION = "1.0"
TABLES = {
    "call_center_interactions": {
        "name": "calls", "pk": "interaction_id", "date": "interaction_date",
        "columns": "interaction_id interaction_date process_date customer_id channel contact_reason reason_category duration_seconds wait_time_seconds was_resolved requires_followup detected_sentiment was_escalated has_transcript",
        "timestamp": "interaction_date", "date_fields": "process_date",
        "boolean": "was_resolved requires_followup was_escalated has_transcript",
        "numeric": "duration_seconds wait_time_seconds",
    },
    "complaints": {
        "name": "cases", "pk": "complaint_id", "date": "creation_date",
        "columns": "complaint_id creation_date process_date customer_id case_type category subcategory reception_channel origin_interaction_id priority status assignment_date first_response_date resolution_date closing_date sla_breached resolution_days resolution_satisfaction is_repeat_complainer",
        "timestamp": "creation_date assignment_date first_response_date resolution_date closing_date",
        "date_fields": "process_date", "boolean": "sla_breached is_repeat_complainer",
        "numeric": "resolution_days resolution_satisfaction",
    },
    "transactions": {
        "name": "tx", "pk": "transaction_id", "date": "transaction_date",
        "columns": "transaction_id transaction_date process_date customer_id transaction_type transaction_category channel transaction_country transaction_status response_code is_fraud amount_usd",
        "timestamp": "transaction_date", "date_fields": "process_date",
        "boolean": "is_fraud", "numeric": "amount_usd",
    },
    "digital_events": {
        "name": "events", "pk": "event_id", "date": "event_date",
        "columns": "event_id event_date process_date customer_id session_id event_type event_category channel platform app_version action duration_seconds",
        "timestamp": "event_date", "date_fields": "process_date",
        "boolean": "", "numeric": "duration_seconds",
    },
}


def qid(s):
    return '"' + s.replace('"', '""') + '"'


def lit(s):
    return "'" + str(s).replace("'", "''") + "'"


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def plan_sources():
    """Deterministic two-day/month cluster sample from the common manifest dates."""
    manifest = json.loads((DATA / "_descarga" / "inventario-s3.json").read_text(encoding="utf-8"))
    grouped = defaultdict(list)
    all_bytes = 0
    for obj in manifest["objects"]:
        rel = obj["Key"].removeprefix("data/")
        all_bytes += obj["Size"]
        table = rel.split("/")[0].removesuffix(".csv")
        if table in TABLES:
            m = re.search(r"year=(\d{4})/month=(\d{2})/day=(\d{2})/", rel)
            if not m:
                raise ValueError(f"Partición diaria no reconocida: {rel}")
            grouped[table].append({"path": rel, "bytes": obj["Size"], "day": "-".join(m.groups())})
    common = set(r["day"] for r in grouped["transactions"]) & set(r["day"] for r in grouped["digital_events"])
    months = defaultdict(list)
    for day in sorted(common):
        months[day[:7]].append(day)
    rng = random.Random(SEED)
    selected_days = sorted(d for month in sorted(months) for d in rng.sample(months[month], min(2, len(months[month]))))
    chosen = set(selected_days)
    sources = {}
    for table, rows in grouped.items():
        sources[table] = sorted([r for r in rows if table not in ("transactions", "digital_events") or r["day"] in chosen], key=lambda x: x["path"])
        for row in sources[table]:
            st = (DATA / row["path"]).stat()
            if st.st_size != row["bytes"]:
                raise ValueError(f"Tamaño inesperado: {row['path']}")
            row["mtime_ns"] = st.st_mtime_ns
    fingerprint = hashlib.sha256(json.dumps({"version": VERSION, "config": TABLES, "sources": sources}, sort_keys=True).encode()).hexdigest()
    return {"seed": SEED, "sampled_days": selected_days, "sample_months": len(months), "sampling": "2 particiones diarias aleatorias por mes; conglomerados, no filas IID", "sources": sources, "inventory_bytes": all_bytes, "fingerprint": fingerprint}


def connect():
    CACHE.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(CACHE / "problemas.duckdb"))
    con.execute("SET memory_limit='1500MB'")
    con.execute("SET threads=4")
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"SET temp_directory={lit((CACHE / 'spill').as_posix())}")
    return con


def export(con, name, query):
    # Only aggregate queries are permitted here. All row-level tables stay ignored.
    df = con.execute(query).fetchdf()
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8")
    return df


def prepare(con, plan, rebuild=False):
    marker = CACHE / "cache.json"
    if marker.exists() and not rebuild:
        old = json.loads(marker.read_text(encoding="utf-8"))
        if old["fingerprint"] == plan["fingerprint"] and all((OUT / f"{n}.csv").exists() for n in ("coverage", "missingness", "invalid_types", "schemas")):
            print("Cache local compatible: se reutilizan exclusivamente las cuatro selecciones.", flush=True)
            return old["load_metrics"], True
    profile, missing, invalid, headers, load_metrics = [], [], [], [], []
    for table, cfg in TABLES.items():
        start = time.perf_counter()
        name, pk, cols = cfg["name"], cfg["pk"], cfg["columns"].split()
        files = plan["sources"][table]
        schemas = defaultdict(int)
        for item in files:
            with (DATA / item["path"]).open(encoding="utf-8-sig", newline="") as f:
                header = tuple(next(csv.reader(f)))
            absent = set(cols) - set(header)
            if absent:
                raise ValueError(f"Faltan campos de análisis en {item['path']}: {absent}")
            schemas[header] += 1
        for header, n in schemas.items():
            headers.append({"table": table, "schema_files": n, "columns_in_file": len(header), "columns_selected": len(cols), "schema_variants": len(schemas)})
        paths = "[" + ",".join(lit((DATA / r["path"]).as_posix()) for r in files) + "]"
        selected = ",".join(f"nullif(trim({qid(c)}), '') AS {qid(c)}" for c in cols)
        con.execute(f"CREATE OR REPLACE TABLE raw_{name} AS SELECT {selected} FROM read_csv({paths}, header=true, all_varchar=true, union_by_name=true, hive_partitioning=false, parallel=false, strict_mode=true)")
        total = con.execute(f"SELECT count(*) FROM raw_{name}").fetchone()[0]
        exprs = ",".join(f"count(*) FILTER(WHERE {qid(c)} IS NULL)" for c in cols)
        nulls = con.execute(f"SELECT {exprs} FROM raw_{name}").fetchone()
        for c, n in zip(cols, nulls):
            missing.append({"table": table, "column": c, "null_rows": n, "rows": total, "null_pct": 100*n/total})
        for kind, cast in (("timestamp", "TIMESTAMP"), ("date_fields", "DATE"), ("boolean", "BOOLEAN"), ("numeric", "DOUBLE")):
            for c in cfg[kind].split():
                n, known = con.execute(f"SELECT count(*) FILTER(WHERE {qid(c)} IS NOT NULL AND try_cast({qid(c)} AS {cast}) IS NULL), count({qid(c)}) FROM raw_{name}").fetchone()
                invalid.append({"table": table, "column": c, "cast": cast, "invalid_rows": n, "non_null_rows": known})
        # Equality only on selected columns, not on entire original CSV rows.
        con.execute(f"CREATE OR REPLACE TABLE unique_{name} AS SELECT DISTINCT * FROM raw_{name}")
        distinct = con.execute(f"SELECT count(*) FROM unique_{name}").fetchone()[0]
        keys, null_keys = con.execute(f"SELECT count(DISTINCT {qid(pk)}), count(*) FILTER(WHERE {qid(pk)} IS NULL) FROM unique_{name}").fetchone()
        con.execute(f"CREATE OR REPLACE TABLE conflict_{name} AS SELECT {qid(pk)} FROM unique_{name} WHERE {qid(pk)} IS NOT NULL GROUP BY 1 HAVING count(*)>1")
        conflicts = con.execute(f"SELECT count(*) FROM conflict_{name}").fetchone()[0]
        conflict_rows = con.execute(f"SELECT count(*) FROM unique_{name} WHERE {qid(pk)} IN (SELECT {qid(pk)} FROM conflict_{name})").fetchone()[0]
        typed = []
        for c in cols:
            cast = next((t for key, t in [("timestamp", "TIMESTAMP"), ("date_fields", "DATE"), ("boolean", "BOOLEAN"), ("numeric", "DOUBLE")] if c in cfg[key].split()), None)
            typed.append(f"try_cast({qid(c)} AS {cast}) AS {qid(c)}" if cast else qid(c))
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT {','.join(typed)} FROM unique_{name} WHERE {qid(pk)} IS NOT NULL AND {qid(pk)} NOT IN (SELECT {qid(pk)} FROM conflict_{name})")
        analysis_rows, dmin, dmax = con.execute(f"SELECT count(*), min({qid(cfg['date'])}), max({qid(cfg['date'])}) FROM {name}").fetchone()
        assert total == (total-distinct)+null_keys+conflict_rows+analysis_rows, "No concilian filas leídas y exclusiones"
        profile.append({"table": table, "scope": "todas las particiones" if name in ("calls", "cases") else "muestra: 2 días/mes", "files": len(files), "source_MB": sum(r["bytes"] for r in files)/1e6, "selected_columns": len(cols), "raw_rows": total, "distinct_keys": keys, "projected_duplicate_rows": total-distinct, "null_key_rows": null_keys, "conflicting_keys": conflicts, "conflicting_distinct_rows": conflict_rows, "analysis_rows": analysis_rows, "min_event_date": dmin, "max_event_date": dmax})
        elapsed = time.perf_counter()-start
        load_metrics.append({"table": table, "seconds_scan_clean": elapsed, "raw_rows": total, "columns_retained": len(cols)})
        print(f"{table}: {total:,} filas leídas, {analysis_rows:,} utilizables; {elapsed:.1f} s", flush=True)
    import pandas as pd
    for name, rows in [("coverage", profile), ("missingness", missing), ("invalid_types", invalid), ("schemas", headers)]:
        pd.DataFrame(rows).to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8")
    con.execute("CHECKPOINT")
    save_json(marker, {"fingerprint": plan["fingerprint"], "load_metrics": load_metrics})
    return load_metrics, False


def analyses(con):
    metrics = []
    for path in sorted((ROOT / "sql" / "eda").glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        for block in text.split("-- result: ")[1:]:
            name, query = block.split("\n", 1)
            start = time.perf_counter()
            df = export(con, name.strip(), query.strip())
            metrics.append({"query": name.strip(), "seconds": time.perf_counter()-start, "aggregate_rows": len(df)})
            print(f"{name.strip()}: {len(df)} agregados", flush=True)
    return metrics


def run(rebuild=False):
    OUT.mkdir(parents=True, exist_ok=True)
    plan = plan_sources()
    save_json(CACHE / "source_selection.json", plan)
    start = time.perf_counter()
    proc = psutil.Process()
    cpu_before = proc.cpu_times()
    peak = [proc.memory_info().rss]
    stop = threading.Event()
    def monitor():
        while not stop.wait(.1):
            peak[0] = max(peak[0], proc.memory_info().rss)
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    con = connect()
    try:
        loads, reused = prepare(con, plan, rebuild=rebuild)
        metrics = analyses(con)
    finally:
        con.close()
        stop.set()
        thread.join()
    cpu_after = proc.cpu_times()
    summary = {
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_fingerprint": plan["fingerprint"], "fingerprint_definition": "SHA256 de rutas, tamaños, mtimes y configuración; NO hash del contenido",
        "engine": "DuckDB", "duckdb_version": duckdb.__version__, "python": platform.python_version(),
        "memory_limit": "1500 MB de DuckDB; no es límite estricto del RSS total", "threads": 4,
        "cache_reused": reused, "wall_seconds": time.perf_counter()-start,
        "process_cpu_seconds": (cpu_after.user+cpu_after.system)-(cpu_before.user+cpu_before.system),
        "peak_process_rss_MiB_observed": peak[0]/1024**2,
        "rss_sampling_interval_s": .1, "logical_cpus": os.cpu_count(),
        "seed": SEED, "sample_months": plan["sample_months"], "sampled_days": plan["sampled_days"],
        "selected_files": sum(len(v) for v in plan["sources"].values()),
        "selected_source_bytes": sum(r["bytes"] for rows in plan["sources"].values() for r in rows),
        "inventory_source_bytes": plan["inventory_bytes"], "load_metrics": loads, "query_metrics": metrics,
        "sampling_limitations": "Muestreo por particiones de process_date, dos días por mes sin ponderar. Los porcentajes de muestras describen sólo esos días; no se extrapolan a 3 años. Posible sesión incompleta en bordes.",
        "dedup_rule": "Quitar repetición exacta en columnas seleccionadas; excluir todas las versiones de IDs con conflicto y claves nulas. No certifica igualdad del resto de columnas.",
        "source_scope": "Sólo interacciones y reclamos completos (columnas seleccionadas); transacciones y eventos digitales con dos particiones diarias por mes. Otras 9 tablas no examinadas.",
    }
    if not reused:
        save_json(CACHE / "first_run_metrics.json", summary)
        save_json(OUT / "medicion_primera_lectura.json", summary)
    save_json(OUT / "ejecucion.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true", help="Releer sólo las selecciones acotadas")
    args = parser.parse_args()
    print(json.dumps(run(rebuild=args.rebuild), ensure_ascii=True, indent=2))
