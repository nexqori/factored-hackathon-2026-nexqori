-- result: transactions_status
SELECT coalesce(transaction_status,'(sin dato)') status,count(*) transactions,
 100.0*count(*)/sum(count(*)) OVER () pct_sample
FROM tx GROUP BY 1 ORDER BY transactions DESC;

-- result: transactions_channel
SELECT coalesce(channel,'(sin dato)') channel,count(*) transactions,
 count(transaction_status) status_known,count(*) FILTER (WHERE transaction_status='Declined') declined,
 100.0*count(*) FILTER (WHERE transaction_status='Declined')/nullif(count(transaction_status),0) declined_pct,
 count(*) FILTER (WHERE transaction_status='Reversed') reversed,
 count(*) FILTER (WHERE transaction_status='Pending') pending
FROM tx GROUP BY 1 ORDER BY declined DESC;

-- result: transactions_type
SELECT coalesce(transaction_type,'(sin dato)') transaction_type,count(*) transactions,
 count(*) FILTER (WHERE transaction_status='Declined') declined,
 100.0*count(*) FILTER (WHERE transaction_status='Declined')/nullif(count(transaction_status),0) declined_pct
FROM tx GROUP BY 1 ORDER BY declined DESC;

-- result: declined_response_codes
SELECT coalesce(response_code,'(sin dato)') response_code,count(*) declined_transactions,
 100.0*count(*)/sum(count(*)) OVER () pct_declined_sample
FROM tx WHERE transaction_status='Declined' GROUP BY 1 ORDER BY declined_transactions DESC;

-- result: events_type
SELECT coalesce(event_type,'(sin dato)') event_type,count(*) events,
 100.0*count(*)/sum(count(*)) OVER () pct_sample
FROM events GROUP BY 1 ORDER BY events DESC;

-- result: digital_channels
SELECT coalesce(channel,'(sin dato)') channel,count(*) events,
 count(event_type) type_known,count(*) FILTER (WHERE event_type='Error') error_events,
 100.0*count(*) FILTER (WHERE event_type='Error')/nullif(count(event_type),0) error_pct,
 count(*) FILTER (WHERE event_type='FormSubmit') form_submit_events
FROM events GROUP BY 1 ORDER BY error_events DESC;

-- result: digital_categories
SELECT coalesce(event_category,'(sin dato)') event_category,count(*) events,
 count(event_type) type_known,count(*) FILTER (WHERE event_type='Error') error_events,
 100.0*count(*) FILTER (WHERE event_type='Error')/nullif(count(event_type),0) error_pct
FROM events GROUP BY 1 ORDER BY error_events DESC;

-- result: digital_sessions
WITH sessions AS (
 SELECT customer_id,session_id,count(*) n_events,
 bool_or(event_type='Error') has_error,
 count(DISTINCT channel) channels,
 count(DISTINCT app_version) versions,
 max(event_date)-min(event_date) duration
 FROM events WHERE customer_id IS NOT NULL AND session_id IS NOT NULL GROUP BY 1,2
)
SELECT count(*) sessions_observed,
 count(*) FILTER (WHERE has_error) sessions_with_error,
 100.0*count(*) FILTER (WHERE has_error)/nullif(count(*),0) session_error_pct,
 count(*) FILTER (WHERE channels>1) sessions_multiple_channels,
 count(*) FILTER (WHERE versions>1) sessions_multiple_versions,
 quantile_cont(n_events,.5) events_per_session_p50
FROM sessions;

-- result: digital_error_actions
SELECT coalesce(action,'(sin dato)') AS action,count(*) error_events,
 100.0*count(*)/sum(count(*)) OVER () pct_errors_sample
FROM events WHERE event_type='Error' GROUP BY 1 ORDER BY error_events DESC LIMIT 20;

-- result: monthly_samples
WITH t AS (
 SELECT strftime(process_date,'%Y-%m') AS month,count(*) transactions,
 count(transaction_status) status_known,count(*) FILTER (WHERE transaction_status='Declined') declined,
 100.0*count(*) FILTER (WHERE transaction_status='Declined')/nullif(count(transaction_status),0) declined_pct
 FROM tx GROUP BY 1
),e AS (
 SELECT strftime(process_date,'%Y-%m') AS month,count(*) events,
 count(event_type) type_known,count(*) FILTER (WHERE event_type='Error') errors,
 100.0*count(*) FILTER (WHERE event_type='Error')/nullif(count(event_type),0) error_pct
 FROM events GROUP BY 1
)
SELECT * FROM t FULL JOIN e USING (month) ORDER BY month;
