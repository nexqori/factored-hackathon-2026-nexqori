"""Census-based service discovery for Nexqori; read-only cache, aggregate outputs."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import csv, hashlib, json, time
import duckdb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks/servicios_nexqori"
DB = ROOT / "dataset/_eda_integral/integral.duckdb"
QUERIES = {
"product_adoption": """SELECT product_type, count(*) products, count(DISTINCT customer_id) customers,
count(*) FILTER(WHERE product_status='Active') active_products,
count(*) FILTER(WHERE has_linked_app=true) linked_app_products,
100.0*count(*)/sum(count(*)) over() product_share_pct,
100.0*count(DISTINCT customer_id)/(SELECT count(*) FROM customers) customer_reach_pct
FROM products GROUP BY 1 ORDER BY products DESC""",
"transaction_usage": """SELECT transaction_type, count(*) transactions, count(DISTINCT customer_id) customers,
count(*) FILTER(WHERE transaction_status='Approved') approved,
count(*) FILTER(WHERE transaction_status='Declined') declined,
count(*) FILTER(WHERE transaction_status='Pending') pending,
count(*) FILTER(WHERE transaction_status='Reversed') reversed,
100.0*count(*)/sum(count(*)) over() share_pct,
100.0*count(*) FILTER(WHERE transaction_status='Declined')/count(*) declined_pct
FROM transactions GROUP BY 1 ORDER BY transactions DESC""",
"transaction_product": """SELECT p.product_type,t.transaction_type,count(*) transactions,count(DISTINCT t.customer_id) customers
FROM transactions t JOIN products p ON t.product_id=p.product_id AND t.customer_id=p.customer_id
GROUP BY 1,2 ORDER BY 1,transactions DESC""",
"transaction_channel": """SELECT channel,transaction_type,count(*) transactions,count(DISTINCT customer_id) customers,
count(*) FILTER(WHERE transaction_status='Declined') declined FROM transactions
GROUP BY 1,2 ORDER BY 1,transactions DESC""",
"transaction_country": """SELECT c.country,t.transaction_type,count(*) transactions,count(DISTINCT t.customer_id) customers,
100.0*count(*)/sum(count(*)) over(partition by c.country) country_share_pct,
count(*) FILTER(WHERE t.transaction_status='Declined') declined
FROM transactions t JOIN customers c ON t.customer_id=c.customer_id GROUP BY 1,2 ORDER BY 1,transactions DESC""",
"transaction_monthly": """SELECT date_trunc('month',transaction_date)::DATE AS month_start,transaction_type,count(*) transactions,
count(DISTINCT customer_id) customers,count(*) FILTER(WHERE transaction_status='Declined') declined
FROM transactions GROUP BY 1,2 ORDER BY 1,2""",
"transaction_recent": """SELECT transaction_type,count(*) transactions,count(DISTINCT customer_id) customers,
100.0*count(*)/sum(count(*)) over() share_pct FROM transactions
WHERE transaction_date >= TIMESTAMP '2026-03-01' AND transaction_date < TIMESTAMP '2026-06-01'
GROUP BY 1 ORDER BY transactions DESC""",
"digital_action": """SELECT coalesce(action,'(sin acción)') AS action_name,count(*) events,
count(DISTINCT customer_id) identified_customers,count(DISTINCT session_id) sessions,
count(*) FILTER(WHERE customer_id IS NULL) anonymous_events,
count(*) FILTER(WHERE event_type='Error') errors,
100.0*count(*)/sum(count(*)) over() share_pct
FROM digital_events GROUP BY 1 ORDER BY events DESC""",
"digital_action_type": """SELECT coalesce(action,'(sin acción)') AS action_name,event_type,count(*) events
FROM digital_events GROUP BY 1,2 ORDER BY 1,events DESC""",
"digital_channel": """SELECT channel,count(*) events,count(DISTINCT customer_id) identified_customers,
count(*) FILTER(WHERE customer_id IS NULL) anonymous_events,
count(*) FILTER(WHERE event_type='Error') errors FROM digital_events GROUP BY 1 ORDER BY events DESC""",
"digital_monthly": """SELECT date_trunc('month',event_date)::DATE AS month_start,coalesce(action,'(sin acción)') AS action_name,count(*) events,
count(DISTINCT customer_id) identified_customers FROM digital_events GROUP BY 1,2 ORDER BY 1,2""",
"digital_pages": """SELECT coalesce(page_title,'(sin página)') page_title,count(*) events,
count(DISTINCT customer_id) identified_customers FROM digital_events GROUP BY 1 ORDER BY events DESC""",
"contact_needs": """SELECT coalesce(contact_reason,'(sin motivo)') reason,count(*) interactions,count(DISTINCT customer_id) customers,
count(*) FILTER(WHERE was_resolved=false) unresolved,count(*) FILTER(WHERE was_resolved IS NOT NULL) resolution_known,
100.0*count(*) FILTER(WHERE was_resolved=false)/nullif(count(*) FILTER(WHERE was_resolved IS NOT NULL),0) unresolved_pct,
count(*) FILTER(WHERE requires_followup=true) followups FROM call_center_interactions GROUP BY 1 ORDER BY interactions DESC""",
"contact_channels": """SELECT channel,count(*) interactions,count(DISTINCT customer_id) customers
FROM call_center_interactions GROUP BY 1 ORDER BY interactions DESC""",
"complaint_needs": """SELECT coalesce(subcategory,'(sin subcategoría)') subcategory,count(*) cases,
count(DISTINCT customer_id) customers,count(*) FILTER(WHERE sla_breached=true) sla_flagged,
count(*) FILTER(WHERE sla_breached IS NOT NULL) sla_known FROM complaints GROUP BY 1 ORDER BY cases DESC""",
"campaign_products": """SELECT coalesce(promoted_product,'(sin producto)') promoted_product,count(*) campaigns FROM marketing_campaigns GROUP BY 1 ORDER BY campaigns DESC""",
"quality": """SELECT
(SELECT count(*) FROM customers) customers,
(SELECT count(*) FROM products) products,
(SELECT count(DISTINCT customer_id) FROM products) product_owners,
(SELECT count(*) FROM transactions) transactions,
(SELECT count(*) FROM digital_events) digital_events,
(SELECT count(*) FROM call_center_interactions) interactions,
(SELECT count(*) FROM complaints) complaints,
(SELECT count(*) FROM digital_events WHERE customer_id IS NULL) anonymous_events,
(SELECT count(*) FROM digital_events WHERE action IS NULL) missing_actions,
(SELECT count(*) FROM transactions t JOIN products p ON t.product_id=p.product_id WHERE t.customer_id<>p.customer_id) transaction_owner_mismatches,
(SELECT count(*) FROM complaints c JOIN products p ON c.affected_product_id=p.product_id WHERE c.customer_id<>p.customer_id) complaint_owner_mismatches,
(SELECT count(*) FROM complaints WHERE affected_product_id IS NOT NULL) complaint_product_links,
(SELECT count(*) FROM digital_events e JOIN products p ON e.product_id=p.product_id WHERE e.customer_id IS NOT NULL) event_product_comparable,
(SELECT count(*) FROM digital_events e JOIN products p ON e.product_id=p.product_id WHERE e.customer_id<>p.customer_id) event_product_mismatches,
(SELECT min(transaction_date) FROM transactions) tx_first,
(SELECT max(transaction_date) FROM transactions) tx_last,
(SELECT min(event_date) FROM digital_events) event_first,
(SELECT max(event_date) FROM digital_events) event_last""",
"status_domains": """SELECT 'products' AS source_table,product_status AS status_label,count(*) records FROM products GROUP BY 2
UNION ALL SELECT 'transactions',transaction_status,count(*) FROM transactions GROUP BY 2""",
}
def run():
    started=time.perf_counter()
    OUT.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect(str(DB),read_only=True)
    con.execute("SET memory_limit='1GB'")
    con.execute("SET threads=3")
    results={}
    for name,sql in QUERIES.items():
        frame=con.execute(sql).fetchdf()
        frame.to_csv(OUT/(name+'.csv'),index=False,lineterminator='\n')
        results[name]=json.loads(frame.to_json(orient="records",date_format="iso"))
        print(name,len(frame),flush=True)
    con.close()
    q=results["quality"][0]
    checks={
        "product_total":sum(r["products"] for r in results["product_adoption"])==q["products"],
        "transactions_total":sum(r["transactions"] for r in results["transaction_usage"])==q["transactions"],
        "digital_total":sum(r["events"] for r in results["digital_action"])==q["digital_events"],
        "contacts_total":sum(r["interactions"] for r in results["contact_needs"])==q["interactions"],
        "complaints_total":sum(r["cases"] for r in results["complaint_needs"])==q["complaints"],
        "country_join":sum(r["transactions"] for r in results["transaction_country"])==q["transactions"],
        "product_join":sum(r["transactions"] for r in results["transaction_product"])==q["transactions"],
        "monthly_transactions":sum(r["transactions"] for r in results["transaction_monthly"])==q["transactions"],
        "monthly_events":sum(r["events"] for r in results["digital_monthly"])==q["digital_events"],
        "valid_owner_join":q["transaction_owner_mismatches"]==0,
        "status_totals":all(r["approved"]+r["declined"]+r["pending"]+r["reversed"]==r["transactions"] for r in results["transaction_usage"]),
    }
    raw=ROOT/"dataset/products.csv"
    with raw.open(encoding="utf-8-sig",newline="") as handle:
        independent=Counter(row["product_type"] for row in csv.DictReader(handle))
    checks["independent_raw_product_counts"]=dict(independent)=={r["product_type"]:r["products"] for r in results["product_adoption"]}
    baseline=list(csv.DictReader((ROOT/"notebooks/resultados_integral/transactions_type.csv").open(encoding="utf-8-sig")))
    checks["previous_census_reconciled"]={r["transaction_type"]:int(r["transactions"]) for r in baseline}=={r["transaction_type"]:r["transactions"] for r in results["transaction_usage"]}
    metadata={
        "executed_at_utc":datetime.now(timezone.utc).isoformat(),
        "source":"dataset/_eda_integral/integral.duckdb",
        "raw_source":"dataset/ — censo previo de 7671 archivos y 23495188 filas",
        "read_only":True,"engine":"DuckDB "+duckdb.__version__,"seconds":round(time.perf_counter()-started,2),
        "unit_note":"Products are a snapshot; transactions and events are historical records, not unique services. Distinct customers overlap across groups.",
        "queries":QUERIES,"checks":checks,
        "result_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob("*.csv")}
    }
    (OUT/"analysis.json").write_text(json.dumps({"metadata":metadata,"results":results},ensure_ascii=False,indent=2),encoding="utf-8")
    assert all(checks.values()),checks
    print(json.dumps({"checks":checks,"seconds":metadata["seconds"],"quality":q},ensure_ascii=True))
    return results
if __name__=="__main__":
    run()
