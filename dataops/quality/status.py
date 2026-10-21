"""The single translation boundary between engine and persisted statuses."""


def quality_status(engine_status: str) -> str:
    return {"PASS": "passed", "FAIL": "failed", "WARNING": "warning", "ERROR": "error"}[
        engine_status
    ]


def pipeline_status(engine_status: str) -> str:
    return "success" if quality_status(engine_status) in {"passed", "warning"} else "failed"
