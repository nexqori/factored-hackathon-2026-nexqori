-- result: customer_country
SELECT country,count(*) AS customers,
 count(*) FILTER(WHERE customer_status='Active') AS active,
 count(email) AS email_known,count(mobile_phone) AS mobile_known,
 count(*) FILTER(WHERE email IS NULL AND mobile_phone IS NULL) AS no_email_or_mobile,
 quantile_cont(credit_score,.5) AS credit_score_median
FROM customers GROUP BY 1 ORDER BY customers DESC;

-- result: customer_segment
SELECT coalesce(segment,'Sin segmento') AS segment,count(*) AS customers,
 count(*) FILTER(WHERE accepts_marketing) AS accepts_marketing
FROM customers GROUP BY 1 ORDER BY customers DESC;

-- result: product_health
SELECT product_type,count(*) AS products,
 count(*) FILTER(WHERE product_status IN ('Blocked','Suspended')) AS blocked_suspended,
 count(days_past_due) AS dpd_known,count(*) FILTER(WHERE days_past_due>0) AS with_arrears,
 count(*) FILTER(WHERE days_past_due>30) AS over_30_days,
 100.0*count(*) FILTER(WHERE days_past_due>30)/nullif(count(days_past_due),0) AS over_30_pct_known
FROM products GROUP BY 1 ORDER BY products DESC;

-- result: product_currency
SELECT currency,count(*) AS products,count(current_balance) AS known_balances,
 quantile_cont(current_balance,.5) AS median_balance_native_currency,
 min(current_balance) AS min_balance,max(current_balance) AS max_balance
FROM products GROUP BY 1;

-- result: branch_country
SELECT country,count(*) AS branches,count(*) FILTER(WHERE branch_status='Active') AS active_branches,
 count(*) FILTER(WHERE has_atms) AS with_atms,count(*) FILTER(WHERE has_teller_windows) AS with_tellers
FROM branches GROUP BY 1;

-- result: agent_experience
SELECT coalesce(a.experience_level,'Sin nivel') AS experience_level,count(*) AS interactions,
 count(c.was_resolved) AS resolution_known,count(*) FILTER(WHERE NOT c.was_resolved) AS unresolved,
 100.0*count(*) FILTER(WHERE NOT c.was_resolved)/nullif(count(c.was_resolved),0) AS unresolved_pct
FROM calls c JOIN service_agents a USING(agent_id) GROUP BY 1 ORDER BY interactions DESC;

-- result: owner_consistency
SELECT 'transactions.product.customer' AS relation,count(*) AS matched_rows,
 count(*) FILTER(WHERE t.customer_id IS NOT NULL AND p.customer_id IS NOT NULL) AS comparable,
 count(*) FILTER(WHERE t.customer_id<>p.customer_id) AS mismatches
FROM transactions t JOIN products p USING(product_id)
UNION ALL SELECT 'complaints.product.customer',count(*),
 count(*) FILTER(WHERE c.customer_id IS NOT NULL AND p.customer_id IS NOT NULL),
 count(*) FILTER(WHERE c.customer_id<>p.customer_id)
FROM complaints c JOIN products p ON c.affected_product_id=p.product_id
UNION ALL SELECT 'events.product.customer',count(*),
 count(*) FILTER(WHERE e.customer_id IS NOT NULL AND p.customer_id IS NOT NULL),
 count(*) FILTER(WHERE e.customer_id<>p.customer_id)
FROM digital_events e JOIN products p USING(product_id)
UNION ALL SELECT 'survey.interaction.customer',count(*),
 count(*) FILTER(WHERE s.customer_id IS NOT NULL AND c.customer_id IS NOT NULL),
 count(*) FILTER(WHERE s.customer_id<>c.customer_id)
FROM satisfaction_surveys s JOIN calls c USING(interaction_id);

-- result: date_domain_rules
SELECT 'birth_after_registration' AS rule,count(*) FILTER(WHERE date_of_birth>registration_date) AS affected,
 count(*) FILTER(WHERE date_of_birth IS NOT NULL AND registration_date IS NOT NULL) AS eligible FROM customers
UNION ALL SELECT 'product_expiration_before_opening',count(*) FILTER(WHERE expiration_date<opening_date),count(expiration_date) FROM products
UNION ALL SELECT 'campaign_end_before_start',count(*) FILTER(WHERE end_date<start_date),count(end_date) FROM marketing_campaigns
UNION ALL SELECT 'negative_exchange_rate',count(*) FILTER(WHERE exchange_rate<=0),count(exchange_rate) FROM daily_exchange_rates
UNION ALL SELECT 'exchange_buy_gt_sell',count(*) FILTER(WHERE buy_rate>sell_rate),count(*) FILTER(WHERE buy_rate IS NOT NULL AND sell_rate IS NOT NULL) FROM daily_exchange_rates
UNION ALL SELECT 'fraud_score_outside_0_100',count(*) FILTER(WHERE fraud_score<0 OR fraud_score>100),count(fraud_score) FROM transactions
UNION ALL SELECT 'survey_before_interaction',count(*) FILTER(WHERE s.survey_date<c.interaction_date),count(s.survey_date) FROM satisfaction_surveys s JOIN calls c USING(interaction_id);

-- result: exchange_pairs
SELECT source_currency,target_currency,count(*) AS rows,
 count(DISTINCT date) AS days,count(DISTINCT source) AS providers,
 min(date) AS first_date,max(date) AS last_date,
 min(exchange_rate) AS min_rate,max(exchange_rate) AS max_rate
FROM daily_exchange_rates GROUP BY 1,2 ORDER BY 1,2;
