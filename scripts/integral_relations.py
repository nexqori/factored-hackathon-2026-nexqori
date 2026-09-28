"""Integridad referencial completa, con faltantes y referencias ambiguas separadas."""
RELATIONS=[
 ('customers','registration_branch_id','branches','branch_id'),
 ('products','customer_id','customers','customer_id'),('products','opening_branch_id','branches','branch_id'),
 ('service_agents','assigned_branch_id','branches','branch_id'),
 ('call_center_interactions','customer_id','customers','customer_id'),('call_center_interactions','agent_id','service_agents','agent_id'),
 ('call_transcripts','interaction_id','call_center_interactions','interaction_id'),('call_transcripts','customer_id','customers','customer_id'),('call_transcripts','agent_id','service_agents','agent_id'),
 ('complaints','customer_id','customers','customer_id'),('complaints','affected_product_id','products','product_id'),
 ('complaints','related_branch_id','branches','branch_id'),('complaints','origin_interaction_id','call_center_interactions','interaction_id'),('complaints','assigned_agent_id','service_agents','agent_id'),
 ('satisfaction_surveys','interaction_id','call_center_interactions','interaction_id'),('satisfaction_surveys','customer_id','customers','customer_id'),('satisfaction_surveys','agent_id','service_agents','agent_id'),
 ('transactions','customer_id','customers','customer_id'),('transactions','product_id','products','product_id'),('transactions','branch_id','branches','branch_id'),
 ('digital_events','customer_id','customers','customer_id'),('digital_events','product_id','products','product_id'),
 ('campaign_sends','customer_id','customers','customer_id'),('campaign_sends','campaign_id','marketing_campaigns','campaign_id')]


def relations(con):
 rows=[]
 for child,fk,parent,pk in RELATIONS:
  values=con.execute(f'''SELECT count(*) AS rows,count(c.{fk}) AS supplied,
   count(*) FILTER(WHERE c.{fk} IS NULL) AS missing,
   count(*) FILTER(WHERE c.{fk} IS NOT NULL AND p.{pk} IS NULL) AS absent,
   count(*) FILTER(WHERE p._n>1) AS ambiguous,
   count(*) FILTER(WHERE p._n=1) AS valid
   FROM {child} c LEFT JOIN keys_{parent} p ON c.{fk}=p.{pk}''').fetchone()
  n,supplied,missing,absent,ambiguous,valid=values
  assert n==missing+absent+ambiguous+valid
  rows.append({'child':child,'foreign_key':fk,'parent':parent,'rows':n,'nonnull_reference':supplied,
               'null_reference':missing,'absent_parent':absent,'ambiguous_parent':ambiguous,'valid_reference':valid,
               'absent_pct_nonnull':100*absent/supplied if supplied else None})
  print(f'JOIN {child}.{fk}: {absent:,} sin padre / {supplied:,} referencias declaradas',flush=True)
 return rows
