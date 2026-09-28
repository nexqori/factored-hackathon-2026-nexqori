-- result: complaints_claims_only
SELECT coalesce(category,'(sin dato)') category,count(*) cases,
 count(sla_breached) sla_known,count(*) FILTER (WHERE sla_breached) sla_breached,
 100.0*count(*) FILTER (WHERE sla_breached)/nullif(count(sla_breached),0) sla_breached_pct,
 count(*) FILTER (WHERE status IN ('Open','In Process','Escalated')) active_status
FROM cases WHERE case_type IN ('Complaint','Claim') GROUP BY 1 ORDER BY sla_breached DESC;

-- result: linkage_by_case_type
SELECT c.case_type,count(*) cases,count(c.origin_interaction_id) declared_links,
 count(i.interaction_id) matched_links,
 count(*) FILTER (WHERE i.interaction_id IS NOT NULL AND c.customer_id<>i.customer_id) customer_mismatches,
 count(*) FILTER (WHERE i.interaction_id IS NOT NULL AND c.creation_date<i.interaction_date) complaint_before_interaction
FROM cases c LEFT JOIN calls i ON c.origin_interaction_id=i.interaction_id GROUP BY 1 ORDER BY 1;

-- result: statuses_and_sla
SELECT status,count(*) cases,
 count(sla_breached) sla_known,count(*) FILTER (WHERE sla_breached) sla_breached,
 100.0*count(*) FILTER (WHERE sla_breached)/nullif(count(sla_breached),0) sla_breached_pct,
 count(first_response_date) first_response_known,
 count(*) FILTER (WHERE first_response_date IS NOT NULL AND date_diff('second',creation_date,first_response_date)>172800) first_response_over_48h
FROM cases GROUP BY 1 ORDER BY cases DESC;

-- result: missingness_context
SELECT 'wait_time_seconds' AS field,channel AS segment,count(*) AS rows,
 count(*) FILTER (WHERE wait_time_seconds IS NULL) AS missing,
 100.0*count(*) FILTER (WHERE wait_time_seconds IS NULL)/count(*) AS missing_pct
FROM calls GROUP BY 1,2
UNION ALL
SELECT 'duration_seconds_calls',channel,count(*),count(*) FILTER (WHERE duration_seconds IS NULL),
 100.0*count(*) FILTER (WHERE duration_seconds IS NULL)/count(*)
FROM calls GROUP BY 1,2
UNION ALL
SELECT 'resolution_date',status,count(*),count(*) FILTER (WHERE resolution_date IS NULL),
 100.0*count(*) FILTER (WHERE resolution_date IS NULL)/count(*)
FROM cases GROUP BY 1,2
UNION ALL
SELECT 'first_response_date',status,count(*),count(*) FILTER (WHERE first_response_date IS NULL),
 100.0*count(*) FILTER (WHERE first_response_date IS NULL)/count(*)
FROM cases GROUP BY 1,2
UNION ALL
SELECT 'customer_id_events',event_type,count(*),count(*) FILTER (WHERE customer_id IS NULL),
 100.0*count(*) FILTER (WHERE customer_id IS NULL)/count(*)
FROM events GROUP BY 1,2;

-- result: digital_session_identity
WITH s AS (
 SELECT session_id,count(DISTINCT customer_id) AS distinct_customers,
 bool_or(event_type='Error') AS has_error
 FROM events WHERE session_id IS NOT NULL GROUP BY 1
)
SELECT count(*) AS sessions,
 count(*) FILTER (WHERE distinct_customers=0) AS anonymous_sessions,
 count(*) FILTER (WHERE distinct_customers>1) AS multiple_customer_sessions,
 count(*) FILTER (WHERE has_error) AS error_sessions,
 100.0*count(*) FILTER (WHERE has_error)/count(*) AS error_session_pct
FROM s;
