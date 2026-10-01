-- Conteo censal; una fila por reclamo. Sin joins ni selección de titulares.
SELECT
  count(*) AS fee_cases,
  count(*) FILTER (WHERE is_repeat_complainer) AS repeat_claimant_cases,
  count(*) FILTER (WHERE is_repeat_complainer AND status IN ('Open','In Process','Escalated')) AS active_repeat_claimant_cases,
  count(*) FILTER (WHERE case_type='Claim' AND is_repeat_complainer AND status='In Process') AS in_process_repeat_claims,
  count(DISTINCT description) AS description_variants,
  count(origin_interaction_id) AS declared_interaction_links,
  min(creation_date) AS first_case,
  max(creation_date) AS last_case
FROM complaints
WHERE subcategory='Cobro indebido';
