"""Keep five exact dataset examples private; no Git outputs or external requests."""
import argparse
import json
from pathlib import Path

import duckdb

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--database", type=Path, default=root / "dataset" / "_eda_integral" / "integral.duckdb")
args = parser.parse_args()
connection = duckdb.connect(str(args.database), read_only=True)
connection.execute("SET memory_limit='1GB'")
connection.execute("SET threads=3")
rows = connection.execute("""
    WITH texts AS (
      SELECT customer_text, arg_min(agent_text, transcript_id) AS agent_text,
             min(transcript_id) AS example_id, count(*) AS occurrences
      FROM transcript_text
      WHERE customer_text IS NOT NULL
      GROUP BY customer_text
    ), ranked AS (
      SELECT *, row_number() OVER (
        PARTITION BY CASE WHEN customer_text ILIKE '%tarjeta%' THEN 'card' ELSE 'account' END
        ORDER BY occurrences DESC, customer_text
      ) AS family_rank FROM texts
    )
    SELECT customer_text, agent_text, example_id, occurrences
    FROM ranked ORDER BY family_rank, customer_text LIMIT 5
""").fetchall()
connection.close()
document = {"source": "organizer_synthetic_dataset_exact_text", "selection": "five distinct texts, interleaving card/account families ordered by frequency within family", "conversations": [{"id": row[2], "language": "es", "occurrences": row[3], "messages": [{"role": "user", "content": row[0]}, {"role": "assistant", "content": row[1]}], "contains_agent_placeholders": "{" in (row[1] or "")} for row in rows]}
destination = root / ".local" / "intent-lab" / "original-transcripts.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"selected": len(rows), "stored_locally": True, "text_exported_to_git": False}))
