import pytest

from dataops.evaluation.manifest import build_manifest


def test_manifest_records_contract_configuration(tmp_path):
    contract = tmp_path / "orders.yaml"
    contract.write_text("dataset: orders\nversion: 3\n")

    manifest = build_manifest(
        dataset="olist_orders",
        contract_version=3,
        contract_path=contract,
        detector_name="spark_quality_engine",
        detector_version="1",
        scenario_names=("clean", "invalid_status"),
    )

    assert manifest.dataset == "olist_orders"
    assert manifest.contract_version == 3
    assert len(manifest.contract_sha256) == 64
    assert manifest.scenario_names == ("clean", "invalid_status")


def test_contract_changes_produce_different_hashes(tmp_path):
    contract = tmp_path / "orders.yaml"
    contract.write_text("version: 3\n")

    arguments = {
        "dataset": "olist_orders",
        "contract_version": 3,
        "contract_path": contract,
        "detector_name": "spark_quality_engine",
        "detector_version": "1",
        "scenario_names": ("clean",),
    }

    original = build_manifest(**arguments)

    contract.write_text("version: 3\nnew_rule: true\n")

    modified = build_manifest(**arguments)

    assert original.contract_sha256 != modified.contract_sha256


def test_missing_contract_is_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_manifest(
            dataset="olist_orders",
            contract_version=3,
            contract_path=tmp_path / "missing.yaml",
            detector_name="spark_quality_engine",
            detector_version="1",
            scenario_names=("clean",),
        )


def test_duplicate_scenarios_are_rejected(tmp_path):
    contract = tmp_path / "orders.yaml"
    contract.write_text("version: 3\n")

    with pytest.raises(ValueError, match="unique"):
        build_manifest(
            dataset="olist_orders",
            contract_version=3,
            contract_path=contract,
            detector_name="spark_quality_engine",
            detector_version="1",
            scenario_names=("clean", "clean"),
        )
