-- result: transcript_quality
SELECT count(*) AS transcripts,count(DISTINCT transcript_id) AS distinct_transcript_ids,
 count(DISTINCT interaction_id) AS distinct_interaction_ids,
 count(matched_interaction_id) AS matched_interactions,
 count(*) FILTER(WHERE matched_interaction_id IS NOT NULL AND NOT same_customer) AS customer_mismatches,
 count(*) FILTER(WHERE same_customer) AS same_customer,
 count(*) FILTER(WHERE matched_interaction_id IS NOT NULL AND NOT topic_matches_reason) AS topic_reason_mismatches,
 count(*) FILTER(WHERE matched_interaction_id IS NOT NULL AND NOT has_transcript) AS linked_but_flag_false,
 count(customer_text) AS customer_text_known,count(DISTINCT customer_text) AS distinct_customer_texts,
 count(*) FILTER(WHERE mentions_balance) AS balance_mentions,
 count(*) FILTER(WHERE agent_has_placeholder) AS agent_placeholders,
 count(*) FILTER(WHERE complaint_keyword) AS complaint_keyword,
 count(*) FILTER(WHERE technical_keyword) AS technical_keyword
FROM transcript_enriched;

-- result: transcript_topics
SELECT coalesce(main_topics,'Sin tema') AS declared_topic,count(*) AS transcripts,
 count(*) FILTER(WHERE mentions_balance) AS balance_mentions,
 count(*) FILTER(WHERE complaint_keyword) AS complaint_keyword,
 count(*) FILTER(WHERE technical_keyword) AS technical_keyword,
 count(*) FILTER(WHERE agent_has_placeholder) AS agent_placeholders,
 count(*) FILTER(WHERE matched_interaction_id IS NOT NULL) AS matched_interactions,
 count(*) FILTER(WHERE same_customer) AS same_customer
FROM transcript_enriched GROUP BY 1 ORDER BY transcripts DESC;

-- result: transcript_reason_text
SELECT coalesce(contact_reason,'Sin interacción vinculada') AS linked_reason,count(*) AS transcripts,
 count(*) FILTER(WHERE same_customer) AS same_customer,
 count(*) FILTER(WHERE mentions_balance) AS balance_mentions,
 count(*) FILTER(WHERE complaint_keyword) AS complaint_keyword,
 count(*) FILTER(WHERE technical_keyword) AS technical_keyword
FROM transcript_enriched GROUP BY 1 ORDER BY transcripts DESC;

-- result: transcript_metadata
SELECT coalesce(detected_intents,'Sin intención') AS intent,coalesce(detected_language,'Sin idioma') AS language,
 count(*) AS transcripts FROM transcript_text GROUP BY 1,2 ORDER BY transcripts DESC;

-- result: text_families
SELECT CASE
 WHEN customer_text LIKE 'Hola, buenos días. Quisiera saber cuál es mi saldo actual en mi cuenta de ahorros.%' THEN 'Plantilla: saldo de cuenta de ahorros'
 WHEN customer_text LIKE 'Buenas tardes, necesito consultar el saldo de mi tarjeta de crédito.%' THEN 'Plantilla: saldo de tarjeta de crédito'
 WHEN customer_text IS NULL THEN 'Texto ausente' ELSE 'Otros textos por revisar' END AS text_family,
 count(*) AS transcripts,count(DISTINCT customer_text) AS distinct_exact_texts
FROM transcript_text GROUP BY 1 ORDER BY transcripts DESC;

-- result: transcript_top_concentration
WITH freqs AS (SELECT customer_text,count(*) AS n FROM transcript_text GROUP BY 1),
 ranked AS (SELECT n,row_number() OVER(ORDER BY n DESC) AS rank FROM freqs)
SELECT sum(n) AS transcripts,count(*) AS distinct_texts,max(n) AS most_repeated_count,
 sum(n) FILTER(WHERE rank<=2) AS top2_count,sum(n) FILTER(WHERE rank<=10) AS top10_count
FROM ranked;
