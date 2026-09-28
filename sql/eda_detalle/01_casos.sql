-- result: subcategories
SELECT coalesce(subcategory,'Sin subcategoría') AS subtype,count(*) AS cases,
 count(sla_breached) AS sla_known,count(*) FILTER(WHERE sla_breached) AS sla_breached,
 100.0*count(*) FILTER(WHERE sla_breached)/nullif(count(sla_breached),0) AS sla_pct,
 count(*) FILTER(WHERE status IN ('Open','In Process','Escalated')) AS active_status,
 count(*) FILTER(WHERE is_repeat_complainer) AS repeat_flag,
 count(*) FILTER(WHERE priority IN ('High','Critical')) AS high_critical,
 count(*) FILTER(WHERE status IN ('Open','In Process','Escalated') AND sla_breached) AS active_and_sla,
 quantile_cont(date_diff('second',creation_date,first_response_date)/3600.0,.5) AS response_p50_hours,
 count(first_response_date) AS response_known,
 quantile_cont(resolution_days,.5) FILTER(WHERE status IN ('Resolved','Closed')) AS resolution_p50_days,
 count(resolution_days) FILTER(WHERE status IN ('Resolved','Closed')) AS resolution_days_known
FROM cases GROUP BY 1 ORDER BY cases DESC;

-- result: sla_priority
SELECT priority,count(*) AS cases,count(sla_breached) AS sla_known,
 count(*) FILTER(WHERE sla_breached) AS sla_breached,
 100.0*count(*) FILTER(WHERE sla_breached)/nullif(count(sla_breached),0) AS sla_pct,
 count(*) FILTER(WHERE status IN ('Open','In Process','Escalated') AND sla_breached) AS active_and_sla,
 count(first_response_date) AS response_known,
 quantile_cont(date_diff('second',creation_date,first_response_date)/3600.0,.5) AS response_p50_hours,
 quantile_cont(resolution_days,.5) FILTER(WHERE status IN ('Resolved','Closed')) AS resolution_p50_days
FROM cases GROUP BY 1 ORDER BY CASE priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END;

-- result: sla_matrix
SELECT category,priority,count(*) AS cases,
 count(*) FILTER(WHERE sla_breached) AS sla_breached,avg(sla_breached::INT)*100 AS sla_pct
FROM cases GROUP BY 1,2 ORDER BY 1,2;

-- result: sla_channels
SELECT reception_channel,count(*) AS cases,
 count(*) FILTER(WHERE sla_breached) AS sla_breached,avg(sla_breached::INT)*100 AS sla_pct,
 count(*) FILTER(WHERE status IN ('Open','In Process','Escalated')) AS active_status,
 count(first_response_date) AS response_known,
 quantile_cont(date_diff('second',creation_date,first_response_date)/3600.0,.5) AS response_p50_hours
FROM cases GROUP BY 1 ORDER BY cases DESC;

-- result: sla_resolution_bins
WITH a AS (
 SELECT *,CASE WHEN resolution_days IS NULL THEN 'Sin duración'
 WHEN resolution_days<=7 THEN '01: 0-7 días' WHEN resolution_days<=15 THEN '02: 8-15 días'
 WHEN resolution_days<=22 THEN '03: 16-22 días' ELSE '04: 23+ días' END AS duration_group
 FROM cases WHERE status IN ('Resolved','Closed')
)
SELECT duration_group,count(*) AS cases,count(*) FILTER(WHERE sla_breached) AS sla_breached,
 avg(sla_breached::INT)*100 AS sla_pct,min(resolution_days) AS min_days,max(resolution_days) AS max_days
FROM a GROUP BY 1 ORDER BY 1;

-- result: sla_response_bins
WITH a AS (
 SELECT *,CASE WHEN first_response_date IS NULL THEN 'Sin respuesta registrada'
 WHEN date_diff('second',creation_date,first_response_date)<=86400 THEN '01: <=24 h'
 WHEN date_diff('second',creation_date,first_response_date)<=172800 THEN '02: 24-48 h' ELSE '03: >48 h' END AS response_group
 FROM cases
)
SELECT response_group,count(*) AS cases,count(*) FILTER(WHERE sla_breached) AS sla_breached,
 avg(sla_breached::INT)*100 AS sla_pct FROM a GROUP BY 1 ORDER BY 1;

-- result: case_text_quality
SELECT count(*) AS cases,count(t.complaint_id) AS matched_text_rows,
 count(t.description) AS descriptions_known,count(DISTINCT t.description) AS distinct_descriptions,
 count(t.resolution) AS resolutions_known,count(DISTINCT t.resolution) AS distinct_resolution_texts,
 count(*) FILTER(WHERE t.description=concat('Queja relacionada con ',lower(c.category))) AS generic_category_description,
 count(*) FILTER(WHERE c.status IN ('Resolved','Closed') AND t.resolution IS NULL) AS resolved_without_text
FROM cases c LEFT JOIN case_text t USING(complaint_id);

-- result: generic_text_by_category
SELECT c.category,count(*) AS cases,count(t.description) AS description_known,
 count(DISTINCT t.description) AS distinct_descriptions,
 count(*) FILTER(WHERE t.description=concat('Queja relacionada con ',lower(c.category))) AS generic_description,
 count(t.resolution) AS resolution_known,count(DISTINCT t.resolution) AS distinct_resolutions
FROM cases c LEFT JOIN case_text t USING(complaint_id) GROUP BY 1 ORDER BY cases DESC;
