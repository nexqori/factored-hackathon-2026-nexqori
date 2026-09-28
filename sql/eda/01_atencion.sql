-- result: calls_overall
SELECT count(*) interactions,
 count(was_resolved) resolution_known,
 count(*) FILTER (WHERE NOT was_resolved) unresolved,
 count(*) FILTER (WHERE was_resolved IS NULL) resolution_unknown,
 100.0*count(*) FILTER (WHERE NOT was_resolved)/nullif(count(was_resolved),0) unresolved_pct,
 count(*) FILTER (WHERE was_escalated) escalated,
 count(*) FILTER (WHERE requires_followup) followup,
 count(*) FILTER (WHERE detected_sentiment IN ('Negativo','Muy Negativo')) negative_sentiment,
 count(wait_time_seconds) wait_known,
 quantile_cont(wait_time_seconds,0.5) wait_p50_s,
 quantile_cont(wait_time_seconds,0.95) wait_p95_s,
 count(*) FILTER (WHERE wait_time_seconds>180) wait_over_180,
 count(*) FILTER (WHERE has_transcript) flag_has_transcript,
 count(*) FILTER (WHERE contact_reason=reason_category) reason_equals_category,
 min(interaction_date) min_date,max(interaction_date) max_date
FROM calls;

-- result: calls_by_reason
SELECT coalesce(contact_reason,'(sin dato)') reason, count(*) interactions,
 count(was_resolved) resolution_known,
 count(*) FILTER (WHERE NOT was_resolved) unresolved,
 100.0*count(*) FILTER (WHERE NOT was_resolved)/nullif(count(was_resolved),0) unresolved_pct,
 count(*) FILTER (WHERE was_escalated) escalated,
 count(was_escalated) escalation_known,
 count(*) FILTER (WHERE requires_followup) followup,
 quantile_cont(wait_time_seconds,.5) wait_p50_s,
 quantile_cont(wait_time_seconds,.95) wait_p95_s
FROM calls GROUP BY 1 ORDER BY unresolved DESC;

-- result: calls_by_channel
SELECT coalesce(channel,'(sin dato)') channel,count(*) interactions,
 count(was_resolved) resolution_known,
 count(*) FILTER (WHERE NOT was_resolved) unresolved,
 100.0*count(*) FILTER (WHERE NOT was_resolved)/nullif(count(was_resolved),0) unresolved_pct,
 count(wait_time_seconds) wait_known,quantile_cont(wait_time_seconds,.5) wait_p50_s,
 quantile_cont(wait_time_seconds,.95) wait_p95_s,
 count(*) FILTER (WHERE wait_time_seconds>180) wait_over_180
FROM calls GROUP BY 1 ORDER BY interactions DESC;

-- result: calls_monthly
SELECT strftime(interaction_date,'%Y-%m') AS month,count(*) interactions,
 count(was_resolved) resolution_known,count(*) FILTER (WHERE NOT was_resolved) unresolved,
 100.0*count(*) FILTER (WHERE NOT was_resolved)/nullif(count(was_resolved),0) unresolved_pct
FROM calls GROUP BY 1 ORDER BY 1;

-- result: repeat_contact
WITH ordered AS (
 SELECT *, lag(interaction_date) OVER (PARTITION BY customer_id,contact_reason ORDER BY interaction_date,interaction_id) previous_contact
 FROM calls WHERE customer_id IS NOT NULL AND contact_reason IS NOT NULL AND interaction_date IS NOT NULL
), eligible AS (
 SELECT * FROM ordered
 WHERE interaction_date >= (SELECT min(interaction_date) + INTERVAL 7 DAY FROM calls)
)
SELECT count(*) eligible_interactions,
 count(*) FILTER (WHERE previous_contact IS NOT NULL AND interaction_date-previous_contact <= INTERVAL 7 DAY) repeated_within_7d,
 100.0*count(*) FILTER (WHERE previous_contact IS NOT NULL AND interaction_date-previous_contact <= INTERVAL 7 DAY)/nullif(count(*),0) repeat_pct,
 count(DISTINCT customer_id) customers_observed
FROM eligible;

-- result: complaints_overall
SELECT count(*) cases,count(sla_breached) sla_known,
 count(*) FILTER (WHERE sla_breached) sla_breached,
 100.0*count(*) FILTER (WHERE sla_breached)/nullif(count(sla_breached),0) sla_breached_pct,
 count(*) FILTER (WHERE status IN ('Open','In Process','Escalated')) active_status,
 count(*) FILTER (WHERE status IN ('Resolved','Closed')) resolved_closed,
 count(*) FILTER (WHERE is_repeat_complainer) repeat_flag,
 count(is_repeat_complainer) repeat_known,
 count(first_response_date) first_response_known,
 quantile_cont(date_diff('second',creation_date,first_response_date)/3600.0,.5) first_response_p50_hours,
 quantile_cont(date_diff('second',creation_date,first_response_date)/3600.0,.95) first_response_p95_hours,
 count(*) FILTER (WHERE status IN ('Resolved','Closed') AND resolution_days IS NOT NULL) resolution_days_known_closed,
 quantile_cont(resolution_days,.5) FILTER (WHERE status IN ('Resolved','Closed')) resolution_days_p50_closed,
 quantile_cont(resolution_days,.95) FILTER (WHERE status IN ('Resolved','Closed')) resolution_days_p95_closed,
 min(creation_date) min_date,max(creation_date) max_date
FROM cases;

-- result: complaints_by_category
SELECT coalesce(category,'(sin dato)') category,count(*) cases,
 count(sla_breached) sla_known,count(*) FILTER (WHERE sla_breached) sla_breached,
 100.0*count(*) FILTER (WHERE sla_breached)/nullif(count(sla_breached),0) sla_breached_pct,
 count(*) FILTER (WHERE status IN ('Open','In Process','Escalated')) active_status,
 count(*) FILTER (WHERE is_repeat_complainer) repeat_flag,
 quantile_cont(resolution_days,.5) FILTER (WHERE status IN ('Resolved','Closed')) resolution_days_p50_closed
FROM cases GROUP BY 1 ORDER BY sla_breached DESC;

-- result: complaints_by_type
SELECT coalesce(case_type,'(sin dato)') case_type, count(*) cases,
 count(sla_breached) sla_known,count(*) FILTER (WHERE sla_breached) sla_breached,
 100.0*count(*) FILTER (WHERE sla_breached)/nullif(count(sla_breached),0) sla_breached_pct
FROM cases GROUP BY 1 ORDER BY cases DESC;

-- result: complaints_by_status
SELECT coalesce(status,'(sin dato)') status,count(*) cases,
 count(*) FILTER (WHERE resolution_date IS NOT NULL) with_resolution_date,
 count(*) FILTER (WHERE closing_date IS NOT NULL) with_closing_date,
 count(*) FILTER (WHERE sla_breached) sla_breached
FROM cases GROUP BY 1 ORDER BY cases DESC;

-- result: complaints_monthly
SELECT strftime(creation_date,'%Y-%m') AS month,count(*) cases,
 count(sla_breached) sla_known,count(*) FILTER (WHERE sla_breached) sla_breached,
 100.0*count(*) FILTER (WHERE sla_breached)/nullif(count(sla_breached),0) sla_breached_pct
FROM cases GROUP BY 1 ORDER BY 1;

-- result: complaint_call_links
SELECT count(*) cases,
 count(*) FILTER (WHERE c.origin_interaction_id IS NOT NULL) declared_links,
 count(*) FILTER (WHERE i.interaction_id IS NOT NULL) matched_links,
 count(*) FILTER (WHERE c.origin_interaction_id IS NOT NULL AND i.interaction_id IS NULL) unmatched_links,
 count(*) FILTER (WHERE i.interaction_id IS NOT NULL AND c.customer_id IS NOT NULL AND i.customer_id IS NOT NULL) comparable_customers,
 count(*) FILTER (WHERE i.interaction_id IS NOT NULL AND c.customer_id<>i.customer_id) customer_mismatches,
 count(*) FILTER (WHERE i.interaction_id IS NOT NULL AND c.creation_date<i.interaction_date) complaint_before_interaction,
 count(*) FILTER (WHERE i.interaction_id IS NOT NULL AND c.customer_id=i.customer_id AND c.creation_date>=i.interaction_date) same_customer_ordered,
 quantile_cont(date_diff('day',i.interaction_date,c.creation_date),.5) FILTER (WHERE i.interaction_id IS NOT NULL) days_from_interaction_p50
FROM cases c LEFT JOIN calls i ON c.origin_interaction_id=i.interaction_id;
