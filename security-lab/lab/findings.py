from sqlalchemy import select
from .db import Finding, Result, now, audit


def record_finding(db, run, result, actor, detail=None):
    finding=db.scalar(select(Finding).where(Finding.target_id==run.target_id,Finding.case_id==result.case_id,Finding.mode==run.mode).with_for_update())
    if result.verdict == "failed":
        data=detail or dict(description="Contract assertion failed",impact="A server boundary or benign control differed from its expectation; review evidence.",recommendation="Inspect the failed assertion and validate a correction with a linked retest.",justification="Provisional severity; HTTP evidence requires contextual review.")
        if not finding:
            finding=Finding(target_id=run.target_id,case_id=result.case_id,mode=run.mode,severity=data.get("severity","medium"),data={**data,"occurrences":[],"regressions":0})
            db.add(finding); db.flush()
        updated=dict(finding.data)
        occurrences=list(updated.get("occurrences",[]))
        if result.id not in occurrences: occurrences.append(result.id)
        if finding.status in ("fixed","verified") and run.parent_id:
            updated["regressions"]=updated.get("regressions",0)+1
            finding.status="open"; finding.verified_at=None
        finding.data={**updated,**data,"occurrences":occurrences}
        if detail: finding.severity=detail.get("severity",finding.severity)
        audit(db,actor,"finding_observed",finding.id,result_id=result.id)
    elif result.verdict == "passed" and finding and finding.status == "fixed" and run.parent_id:
        # A reviewer marking the old result passed never closes the finding.
        parent_results=set(db.scalars(select(Result.id).where(Result.run_id==run.parent_id)))
        if not parent_results.intersection(finding.data.get("occurrences",[])):
            return
        if not run.started or not finding.fixed_at or run.started < finding.fixed_at:
            return
        finding.status="verified"; finding.verified_at=now()
        finding.data={**finding.data,"verified_result":result.id}
        audit(db,actor,"finding_verified",finding.id,result_id=result.id)
