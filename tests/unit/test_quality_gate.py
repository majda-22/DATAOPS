import pytest

from dataops.pipelines.quality_gate import (
    QualityGateError,
    publish_if_quality_passed,
)


def test_passing_quality_report_allows_publication():
    report = {
        "status": "PASS",
        "results": [{"status": "PASS"}],
    }

    published = []

    def publish():
        published.append("silver_written")
        return 99441

    result = publish_if_quality_passed(report, publish)

    assert result == 99441
    assert published == ["silver_written"]


def test_failing_quality_report_blocks_publication():
    report = {
        "status": "FAIL",
        "results": [{"status": "FAIL"}],
    }

    silver_data = ["existing_valid_data"]

    def publish():
        silver_data.clear()
        silver_data.append("corrupted_data")

    with pytest.raises(QualityGateError):
        publish_if_quality_passed(report, publish)

    assert silver_data == ["existing_valid_data"]


def test_inconsistent_quality_report_blocks_publication():
    report = {
        "status": "PASS",
        "results": [
            {"status": "PASS"},
            {"status": "FAIL"},
        ],
    }

    published = []

    with pytest.raises(QualityGateError):
        publish_if_quality_passed(
            report,
            lambda: published.append("written"),
        )

    assert published == []


def test_missing_checks_blocks_publication():
    report = {
        "status": "PASS",
        "results": [],
    }

    with pytest.raises(QualityGateError):
        publish_if_quality_passed(report, lambda: None)
