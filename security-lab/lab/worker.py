"""One PostgreSQL advisory-lock worker, hard-cancellable child per case.

No interrupted case is replayed. A restart closes running executions as inconclusive.
Queued executions are retained. Child processes inherit only the lab environment.
"""
import multiprocessing as mp
import time
from queue import Empty
from sqlalchemy import select, text
from .db import Run, Result, Target, sessions, engine_for, audit, now
from .catalog import BY_ID
from .adapters import child_execute
from .security import redact
from .findings import record_finding


def recover(factory):
    with factory() as db:
        for run in db.scalars(select(Run).where(Run.status=="running")):
            run.status="error"; run.ended=now()
            for r in db.scalars(select(Result).where(Result.run_id==run.id, Result.status.in_(["pending","running"]))):
                r.status="error"; r.verdict="inconclusive"; r.evidence={"executed":False,"error":"worker_restart_no_replay"}
            audit(db,"worker","interrupted_no_replay",run.id)
        db.commit()


def execute_run(factory, run_id):
    with factory() as db:
        run=db.get(Run,run_id)
        spec, mode, locale=run.spec,run.mode,run.locale
        ids=list(db.scalars(select(Result.id).where(Result.run_id==run_id).order_by(Result.case_id)))
    start=time.monotonic()
    for rid in ids:
        with factory() as db:
            run=db.get(Run,run_id); result=db.get(Result,rid)
            target=db.get(Target,run.target_id)
            if run.cancelled or not target.enabled or time.monotonic()-start >= spec["run_seconds"]:
                reason="cancelled" if run.cancelled else "target_disabled" if not target.enabled else "run_timeout"
                run.status="cancelled" if run.cancelled else "error"; run.ended=now()
                for pending in db.scalars(select(Result).where(Result.run_id==run_id,Result.status.in_(["pending","running"]))):
                    pending.status=run.status; pending.verdict="inconclusive"; pending.evidence={"executed":False,"error":reason}
                db.commit(); return
            case=next((c for c in spec.get("_catalog",[]) if c["id"]==result.case_id),BY_ID[result.case_id])
            if case["mode"] != "automated":
                result.status="completed"
                result.verdict={"blocked":"inconclusive","not_applicable":"not_applicable","manual":"pending_review"}[case["mode"]]
                result.evidence={"executed":False,"reason":case["reason"],"procedure_version":case["version"]}
                db.commit(); continue
            result.status="running"; db.commit()
        context=mp.get_context("spawn")
        queue=context.Queue()
        process=context.Process(target=child_execute,args=(queue,case["executor"],spec["requests_per_case"],locale,mode=="demo"))
        process.start(); deadline=min(start+spec["run_seconds"],time.monotonic()+spec["case_seconds"])
        answer=None
        try:
            while True:
                with factory() as db:
                    run=db.get(Run,run_id); target=db.get(Target,run.target_id)
                    cancelled=run.cancelled; enabled=target.enabled
                if cancelled or not enabled or time.monotonic()>deadline:
                    answer=dict(status="cancelled" if cancelled else "error",verdict="inconclusive",evidence={"executed":False,"error":"cancelled" if cancelled else "target_disabled" if not enabled else "case_timeout"})
                    break
                try:
                    answer=queue.get(timeout=.2); break
                except Empty:
                    if not process.is_alive():
                        answer=dict(status="error",verdict="inconclusive",evidence={"executed":False,"error":"executor_exited"}); break
        finally:
            if process.is_alive(): process.terminate()
            process.join(timeout=2)
            if process.is_alive(): process.kill(); process.join()
            queue.close()
        with factory() as db:
            result=db.get(Result,rid); run=db.get(Run,run_id)
            for key,value in answer.items(): setattr(result,key,redact(value))
            record_finding(db,run,result,"worker")
            audit(db,"worker","case_finished",rid,status=result.status,verdict=result.verdict)
            db.commit()
    with factory() as db:
        run=db.get(Run,run_id)
        errors=db.scalar(select(Result.id).where(Result.run_id==run_id,Result.status=="error").limit(1))
        run.status="cancelled" if run.cancelled else "error" if errors else "completed"; run.ended=now()
        audit(db,"worker","run_finished",run_id,status=run.status); db.commit()


def main():
    engine=engine_for(); factory=sessions(engine)
    # Dedicated connection holds lock for lifetime. Additional workers exit safely.
    with engine.connect() as lock:
        if not lock.scalar(text("SELECT pg_try_advisory_lock(519001)")):
            raise RuntimeError("Only one laboratory worker may run")
        recover(factory)
        while True:
            with factory() as db:
                run=db.scalar(select(Run).where(Run.status=="pending").order_by(Run.created).with_for_update(skip_locked=True))
                run_id=run.id if run else None
                if run:
                    run.status="running";run.started=now();db.commit()
            if run_id:
                execute_run(factory,run_id)
            else:
                time.sleep(.5)


if __name__ == "__main__":
    main()
