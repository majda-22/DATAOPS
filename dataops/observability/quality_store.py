from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from dataops.db.models import PipelineRun, QualityResult

QUALITY_STATUS = {
    "PASS": "passed",
    "FAIL": "failed",
}


def persist_quality_report(
    session: Session,
    report: dict,
    *,
    pipeline_name: str = "olist_bronze_quality",
) -> UUID:
    """Persist a quality report in a single transaction.

    Repeated calls with the same run_id do not duplicate results.
    The caller must provide a session without an active transaction.
    """

    run_id = UUID(str(report["run_id"]))
    started_at = datetime.fromisoformat(report["started_at"])
    finished_at = datetime.fromisoformat(report["finished_at"])
    row_count = int(report["row_count"])
    checks = report["results"]

    if not checks:
        raise ValueError("Quality report must contain at least one check")

    if row_count < 0 or finished_at < started_at:
        raise ValueError("Invalid row count or timestamps")

    rule_ids = [check["rule_id"] for check in checks]
    if len(rule_ids) != len(set(rule_ids)):
        raise ValueError("Duplicate quality rule IDs")

    if any(check["status"] not in QUALITY_STATUS for check in checks):
        raise ValueError("Unsupported quality status")

    failed = any(check["status"] == "FAIL" for check in checks)
    expected_status = "FAIL" if failed else "PASS"

    if report["status"] != expected_status:
        raise ValueError("Overall status does not match check results")

    for check in checks:
        if int(check["failed_rows"]) < 0:
            raise ValueError("Negative failed_rows is not allowed")

    with session.begin():
        existing = session.get(PipelineRun, run_id)

        if existing is not None:
            if existing.pipeline_name != pipeline_name:
                raise ValueError("Run ID belongs to a different pipeline")
            return run_id

        pipeline_run = PipelineRun(
            id=run_id,
            pipeline_name=pipeline_name,
            status="failed" if failed else "success",
            started_at=started_at,
            finished_at=finished_at,
            rows_in=row_count,
        )

        session.add(pipeline_run)
        session.flush()

        for check in checks:
            result = QualityResult(
                pipeline_run_id=run_id,
                rule_id=check["rule_id"],
                status=QUALITY_STATUS[check["status"]],
                failed_rows=int(check["failed_rows"]),
                details={
                    "rule_type": check["rule_type"],
                    "checked_rows": check["checked_rows"],
                    "examples": check["examples"],
                    "dataset": report["dataset"],
                    "contract_version": report["contract_version"],
                    "source_file": report["source_file"],
                },
            )
            session.add(result)

    return run_id
