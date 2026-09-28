-- result: survey_scores
SELECT survey_type,count(*) AS surveys,count(main_score) AS known_scores,
 min(main_score) AS min_score,max(main_score) AS max_score,avg(main_score) AS mean_score,
 quantile_cont(main_score,.5) AS median_score,count(open_comments) AS comments_known,
 count(DISTINCT open_comments) AS distinct_comments
FROM satisfaction_surveys GROUP BY 1 ORDER BY 1;

-- result: survey_distribution
SELECT survey_type,main_score,count(*) AS surveys
FROM satisfaction_surveys GROUP BY 1,2 ORDER BY 1,2;

-- result: survey_metrics
SELECT survey_type,count(*) AS surveys,
 count(*) FILTER(WHERE survey_type='CSAT' AND main_score BETWEEN 1 AND 5) AS csat_eligible,
 count(*) FILTER(WHERE survey_type='CSAT' AND main_score IN (4,5)) AS csat_satisfied,
 count(*) FILTER(WHERE survey_type='NPS' AND main_score BETWEEN 0 AND 10) AS nps_eligible,
 count(*) FILTER(WHERE survey_type='NPS' AND main_score>=9) AS promoters,
 count(*) FILTER(WHERE survey_type='NPS' AND main_score<=6 AND main_score>=0) AS detractors,
 count(*) FILTER(WHERE survey_type='NPS' AND nps_category IS NOT NULL AND nps_category<>CASE WHEN main_score>=9 THEN 'Promoter' WHEN main_score>=7 THEN 'Passive' ELSE 'Detractor' END) AS nps_label_disagreement
FROM satisfaction_surveys GROUP BY 1;

-- result: survey_resolution
SELECT c.contact_reason,s.survey_type,c.was_resolved,count(*) AS surveys,
 avg(s.main_score) AS mean_score,count(s.main_score) AS score_known
FROM satisfaction_surveys s JOIN calls c USING(interaction_id)
WHERE s.customer_id=c.customer_id
GROUP BY 1,2,3 ORDER BY 1,2,3;

-- result: campaigns_channel
SELECT send_channel,count(*) AS sends,count(*) FILTER(WHERE was_delivered) AS delivered,
 count(*) FILTER(WHERE was_opened) AS opened,count(*) FILTER(WHERE was_clicked) AS clicked,
 count(*) FILTER(WHERE had_conversion) AS converted,
 count(*) FILTER(WHERE send_status IN ('Failed','Bounced','Blocked')) AS failed_bounced_blocked,
 100.0*count(*) FILTER(WHERE was_delivered)/count(*) AS delivery_pct,
 100.0*count(*) FILTER(WHERE had_conversion)/count(*) AS conversion_pct_all_sends
FROM campaign_sends GROUP BY 1 ORDER BY sends DESC;

-- result: campaign_failure_reason
SELECT send_channel,send_status,coalesce(failure_reason,'Sin motivo') AS failure_reason,count(*) AS sends
FROM campaign_sends WHERE send_status IN ('Failed','Bounced','Blocked')
GROUP BY 1,2,3 ORDER BY sends DESC;

-- result: campaign_rules
SELECT 'clicked_without_delivery_flag' AS rule,count(*) FILTER(WHERE was_clicked AND NOT was_delivered) AS affected,
 count(*) FILTER(WHERE was_clicked) AS eligible FROM campaign_sends
UNION ALL SELECT 'conversion_without_delivery_flag',count(*) FILTER(WHERE had_conversion AND NOT was_delivered),count(*) FILTER(WHERE had_conversion) FROM campaign_sends
UNION ALL SELECT 'open_date_before_send',count(*) FILTER(WHERE open_date<send_date),count(open_date) FROM campaign_sends
UNION ALL SELECT 'click_date_before_send',count(*) FILTER(WHERE click_date<send_date),count(click_date) FROM campaign_sends
UNION ALL SELECT 'conversion_date_before_send',count(*) FILTER(WHERE conversion_date<send_date),count(conversion_date) FROM campaign_sends;

-- result: campaign_catalog
SELECT campaign_type,campaign_status,count(*) AS campaigns,
 min(start_date) AS first_start,max(end_date) AS last_end
FROM marketing_campaigns GROUP BY 1,2 ORDER BY campaigns DESC;

-- result: campaign_date_alignment
SELECT count(*) AS linked_sends,
 count(*) FILTER(WHERE s.send_date::DATE<m.start_date::DATE OR s.send_date::DATE>m.end_date::DATE) AS sends_outside_campaign_dates,
 count(*) FILTER(WHERE s.send_date IS NOT NULL AND m.start_date IS NOT NULL AND m.end_date IS NOT NULL) AS comparable
FROM campaign_sends s JOIN marketing_campaigns m USING(campaign_id);
