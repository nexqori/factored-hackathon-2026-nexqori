-- result: currency_usd_coverage
SELECT currency,count(*) AS transactions,count(amount) AS amount_known,count(amount_usd) AS usd_known,
 100.0*count(*) FILTER(WHERE amount_usd IS NULL)/count(*) AS usd_missing_pct
FROM transactions GROUP BY 1 ORDER BY transactions DESC;

-- result: survey_response_coverage
WITH s AS (SELECT interaction_id,count(*) AS n FROM satisfaction_surveys GROUP BY 1)
SELECT c.contact_reason,count(*) AS interactions,
 count(*) FILTER(WHERE s.interaction_id IS NOT NULL) AS interactions_with_survey,
 100.0*count(*) FILTER(WHERE s.interaction_id IS NOT NULL)/count(*) AS linked_survey_pct
FROM calls c LEFT JOIN s USING(interaction_id) GROUP BY 1 ORDER BY interactions DESC;

-- result: consent_send_flags
SELECT s.send_channel,count(*) AS linked_sends,
 count(*) FILTER(WHERE c.accepts_marketing=FALSE) AS to_customer_flag_no_marketing,
 count(*) FILTER(WHERE c.accepts_marketing IS NULL) AS marketing_flag_unknown
FROM campaign_sends s JOIN customers c USING(customer_id) GROUP BY 1 ORDER BY linked_sends DESC;

-- result: fraud_flags
SELECT is_fraud,count(*) AS transactions,count(fraud_score) AS score_known,
 avg(fraud_score) AS mean_fraud_score,
 count(*) FILTER(WHERE transaction_status='Approved') AS approved,
 count(*) FILTER(WHERE transaction_status='Declined') AS declined
FROM transactions GROUP BY 1 ORDER BY transactions DESC;
