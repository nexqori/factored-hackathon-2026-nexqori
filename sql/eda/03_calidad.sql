-- result: process_date_lags
WITH dates AS (
 SELECT 'interactions: completo' AS scope,cast(interaction_date AS DATE) AS event_day,process_date FROM calls
 UNION ALL SELECT 'complaints: completo',cast(creation_date AS DATE),process_date FROM cases
 UNION ALL SELECT 'transactions: muestra',cast(transaction_date AS DATE),process_date FROM tx
 UNION ALL SELECT 'digital_events: muestra',cast(event_date AS DATE),process_date FROM events
)
SELECT scope,count(*) AS rows,
 count(*) FILTER (WHERE event_day IS NOT NULL AND process_date IS NOT NULL) comparable,
 count(*) FILTER (WHERE process_date<event_day) process_before_event_day,
 count(*) FILTER (WHERE process_date>event_day) process_after_event_day,
 min(date_diff('day',event_day,process_date)) min_lag_days,
 max(date_diff('day',event_day,process_date)) max_lag_days,
 quantile_cont(date_diff('day',event_day,process_date),.95) p95_lag_days
FROM dates GROUP BY 1;

-- result: quality_rules
SELECT 'call_wait_negative' AS rule,count(*) FILTER (WHERE wait_time_seconds<0) AS affected,count(wait_time_seconds) AS eligible FROM calls
UNION ALL SELECT 'call_duration_negative',count(*) FILTER (WHERE duration_seconds<0),count(duration_seconds) FROM calls
UNION ALL SELECT 'call_reason_equals_category',count(*) FILTER (WHERE contact_reason=reason_category),count(*) FILTER (WHERE contact_reason IS NOT NULL AND reason_category IS NOT NULL) FROM calls
UNION ALL SELECT 'first_response_before_creation',count(*) FILTER (WHERE first_response_date<creation_date),count(first_response_date) FROM cases
UNION ALL SELECT 'resolution_before_creation',count(*) FILTER (WHERE resolution_date<creation_date),count(resolution_date) FROM cases
UNION ALL SELECT 'closing_before_resolution',count(*) FILTER (WHERE closing_date<resolution_date),count(*) FILTER (WHERE closing_date IS NOT NULL AND resolution_date IS NOT NULL) FROM cases
UNION ALL SELECT 'resolved_closed_without_resolution_date',count(*) FILTER (WHERE status IN ('Resolved','Closed') AND resolution_date IS NULL),count(*) FILTER (WHERE status IN ('Resolved','Closed')) FROM cases
UNION ALL SELECT 'active_status_with_resolution_date',count(*) FILTER (WHERE status IN ('Open','In Process','Escalated') AND resolution_date IS NOT NULL),count(*) FILTER (WHERE status IN ('Open','In Process','Escalated')) FROM cases
UNION ALL SELECT 'resolution_days_disagree_elapsed',count(*) FILTER (WHERE abs(resolution_days-date_diff('second',creation_date,resolution_date)/86400.0)>0.01),count(*) FILTER (WHERE resolution_days IS NOT NULL AND resolution_date IS NOT NULL AND creation_date IS NOT NULL) FROM cases
UNION ALL SELECT 'outcome_after_process_day',count(*) FILTER (WHERE resolution_date::DATE>process_date),count(*) FILTER (WHERE resolution_date IS NOT NULL AND process_date IS NOT NULL) FROM cases
UNION ALL SELECT 'event_duration_negative',count(*) FILTER (WHERE duration_seconds<0),count(duration_seconds) FROM events
UNION ALL SELECT 'transaction_amount_usd_negative',count(*) FILTER (WHERE amount_usd<0),count(amount_usd) FROM tx;
