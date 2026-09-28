-- result: focus_outcomes
SELECT contact_reason,count(*) AS interactions,
 count(*) FILTER(WHERE NOT was_resolved) AS unresolved,
 count(*) FILTER(WHERE NOT was_resolved AND requires_followup) AS unresolved_with_followup,
 count(*) FILTER(WHERE NOT was_resolved AND NOT requires_followup) AS unresolved_without_followup,
 count(*) FILTER(WHERE NOT was_resolved AND was_escalated) AS unresolved_escalated,
 count(*) FILTER(WHERE NOT was_resolved AND NOT requires_followup AND NOT was_escalated) AS unresolved_without_flags,
 count(*) FILTER(WHERE NOT was_resolved AND detected_sentiment IN ('Negativo','Muy Negativo')) AS unresolved_negative,
 count(*) FILTER(WHERE has_transcript) AS transcript_flag
FROM calls WHERE contact_reason IN ('Queja','Técnico') GROUP BY 1 ORDER BY unresolved DESC;

-- result: focus_channels
SELECT contact_reason,channel,count(*) AS interactions,
 count(*) FILTER(WHERE NOT was_resolved) AS unresolved,avg((NOT was_resolved)::INT)*100 AS unresolved_pct,
 count(*) FILTER(WHERE NOT was_resolved AND NOT requires_followup AND NOT was_escalated) AS unresolved_without_flags,
 quantile_cont(wait_time_seconds,.5) AS wait_p50_s,quantile_cont(wait_time_seconds,.95) AS wait_p95_s
FROM calls WHERE contact_reason IN ('Queja','Técnico') GROUP BY 1,2 ORDER BY 1,interactions DESC;

-- result: focus_sentiment
SELECT contact_reason,detected_sentiment,count(*) AS interactions,
 count(*) FILTER(WHERE NOT was_resolved) AS unresolved,avg((NOT was_resolved)::INT)*100 AS unresolved_pct
FROM calls WHERE contact_reason IN ('Queja','Técnico') GROUP BY 1,2 ORDER BY 1,interactions DESC;

-- result: technical_actions
SELECT coalesce(action,'Sin acción') AS action,event_category,count(*) AS events,
 count(*) FILTER(WHERE event_type='Error') AS error_events,avg((event_type='Error')::INT)*100 AS error_pct
FROM events WHERE event_category IN ('Transaction','Navigation') GROUP BY 1,2 ORDER BY error_events DESC;
