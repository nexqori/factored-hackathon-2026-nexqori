"""Read-only, aggregate evidence for the service registry. No customer rows exported."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import duckdb

ROOT = Path(__file__).resolve().parents[1]
QUERIES = {
    "service_merchants": """SELECT merchant_name, transaction_type, count(*) records,
    count(*) FILTER(WHERE merchant_category='Services') category_services,
    min(transaction_date) first_seen, max(transaction_date) last_seen
    FROM transactions WHERE merchant_name IN ('Empresa Telefónica','Internet Plus','Cable TV','Servicios Públicos')
    GROUP BY 1,2 ORDER BY 1,2""",
    "payment_coverage": """SELECT count(*) records, count(merchant_name) merchant_names,
    count(*) FILTER(WHERE transaction_category='Services') service_category
    FROM transactions WHERE transaction_type='Payment'""",
    "transaction_types": "SELECT transaction_type, count(*) records FROM transactions GROUP BY 1 ORDER BY 1",
    "transaction_states": "SELECT transaction_status, count(*) records FROM transactions GROUP BY 1 ORDER BY 1",
    "product_types": "SELECT product_type, count(*) records FROM products GROUP BY 1 ORDER BY 1",
    "complaint_subcategories": "SELECT subcategory, count(*) records FROM complaints GROUP BY 1 ORDER BY 1",
}


def run():
    con = duckdb.connect(str(ROOT / 'dataset/_eda_integral/integral.duckdb'), read_only=True)
    con.execute("SET memory_limit='1GB'")
    con.execute("SET threads=3")
    evidence = {}
    for name, query in QUERIES.items():
        cursor = con.execute(query)
        rows = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
        evidence[name] = {"sql": query, "sha256": hashlib.sha256(query.encode()).hexdigest(), "rows": rows}
    con.close()
    registry = json.loads((ROOT / 'backend/service_catalog.json').read_text(encoding='utf-8'))
    for service in registry['items']:
        ref = service['evidence']
        rows = evidence[ref['query']]['rows']
        observed = {str(value) for row in rows for value in row.values()}
        assert all(value in observed for value in ref['sourceValue'].split('|')), service['id']
    assert sum(row['records'] for row in evidence['transaction_types']['rows']) == 4425008
    assert evidence['payment_coverage']['rows'][0]['merchant_names'] == 0
    assert all(row['transaction_type'] == 'Purchase' for row in evidence['service_merchants']['rows'])
    output = ROOT / 'notebooks/servicios_nexqori/catalog_evidence.json'
    output.write_text(json.dumps({"generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "dataset/_eda_integral/integral.duckdb", "scope": "Full historical tables; all transaction states; no timezone declared by source.",
        "interpretation": "Merchant names support discovery labels, not collection agreements. Mapping phone/mobile and public utility synonyms is a product decision, not a dataset breakdown.",
        "catalogServices": len(registry['items']), "checks": "Every source value exists; transaction counts reconcile; payment merchant names absent; four named merchants observed only in Purchase.",
        "queries": evidence}, ensure_ascii=False, indent=2, default=str)+'\n', encoding='utf-8')
    print(f'{len(QUERIES)} aggregate queries; {len(registry["items"])} service mappings verified; {output.relative_to(ROOT)}')


if __name__ == '__main__':
    run()
