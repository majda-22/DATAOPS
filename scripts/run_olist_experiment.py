import json
import os
from dataclasses import asdict
from pathlib import Path

import yaml
from pyspark.sql import SparkSession
from pyspark.sql.types import StringType, StructField, StructType
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from dataops.contracts.models import DatasetContract
from dataops.evaluation.manifest import (
    build_manifest,
    manifest_to_dict,
)
from dataops.evaluation.metrics import calculate_metrics
from dataops.evaluation.runner import ExperimentScenario, run_experiment
from dataops.evaluation.store import persist_experiment
from dataops.faults.injector import inject_fault
from dataops.faults.models import FaultSpec
from dataops.quality.spark_engine import evaluate_spark

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "configs/datasets/olist_orders.yaml"
REPORT_DIR = ROOT / "data/reports"

COLUMNS = [
    "order_id",
    "customer_id",
    "order_status",
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]

SCHEMA = StructType([StructField(name, StringType(), True) for name in COLUMNS])


def valid_orders():
    return [
        {
            "order_id": "order_001",
            "customer_id": "customer_001",
            "order_status": "delivered",
            "order_purchase_timestamp": "2018-08-07 05:42:46",
            "order_approved_at": "2018-08-07 05:50:08",
            "order_delivered_carrier_date": "2018-08-13 09:24:00",
            "order_delivered_customer_date": "2018-08-27 15:28:22",
            "order_estimated_delivery_date": "2018-09-18 00:00:00",
        },
        {
            "order_id": "order_002",
            "customer_id": "customer_002",
            "order_status": "shipped",
            "order_purchase_timestamp": "2018-08-08 10:00:00",
            "order_approved_at": "2018-08-08 11:00:00",
            "order_delivered_carrier_date": None,
            "order_delivered_customer_date": None,
            "order_estimated_delivery_date": "2018-09-20 00:00:00",
        },
    ]


FAULTS = [
    FaultSpec(
        fault_type="duplicate_key",
        column="order_id",
        row_indices=(1,),
        source_row_index=0,
        expected_rule="order_id_unique",
    ),
    FaultSpec(
        fault_type="invalid_value",
        column="order_status",
        row_indices=(1,),
        value="INVALID_STATUS",
        expected_rule="order_status_allowed",
    ),
    FaultSpec(
        fault_type="null_value",
        column="order_id",
        row_indices=(1,),
        expected_rule="order_id_not_null",
    ),
    FaultSpec(
        fault_type="foreign_key_violation",
        column="customer_id",
        row_indices=(1,),
        value="UNKNOWN_CUSTOMER",
        expected_rule="orders_customer_fk",
    ),
]


def main():
    with CONTRACT_PATH.open(encoding="utf-8") as file:
        contract = DatasetContract.model_validate(yaml.safe_load(file))

    spark = (
        SparkSession.builder.master("local[2]").appName("dataops-olist-evaluation").getOrCreate()
    )

    try:
        customers_df = spark.createDataFrame(
            [("customer_001",), ("customer_002",)],
            ["customer_id"],
        )

        scenarios = [
            ExperimentScenario(
                name="clean_control",
                data=valid_orders(),
            )
        ]

        for spec in FAULTS:
            corrupted, ground_truth = inject_fault(
                valid_orders(),
                spec,
            )

            scenarios.append(
                ExperimentScenario(
                    name=spec.fault_type,
                    data=corrupted,
                    ground_truth=ground_truth,
                )
            )

        def detector(records):
            df = spark.createDataFrame(records, schema=SCHEMA)

            return evaluate_spark(
                df,
                contract,
                source="olist_evaluation_experiment",
                reference_data={"olist_customers": customers_df},
            )

        experiment = run_experiment(scenarios, detector)
        metrics = calculate_metrics(experiment)
        manifest = build_manifest(
            dataset=contract.dataset,
            contract_version=contract.version,
            contract_path=CONTRACT_PATH,
            detector_name="spark_quality_engine",
            detector_version="1",
            scenario_names=tuple(s.name for s in scenarios),
        )
        # Persist experiment results to PostgreSQL.
        database_url = os.environ.get("DATABASE_URL")

        if not database_url:
            raise RuntimeError("DATABASE_URL is not configured")

        engine = create_engine(database_url)

        try:
            with Session(engine) as session:
                experiment_id = persist_experiment(
                    session,
                    experiment,
                    metrics,
                )

            print(f"Persisted experiment: {experiment_id}")

        finally:
            engine.dispose()

        REPORT_DIR.mkdir(parents=True, exist_ok=True)

        output = {
            "experiment_id": str(experiment.experiment_id),
            "manifest": manifest_to_dict(manifest),
            "metrics": asdict(metrics),
            "scenarios": [
                {
                    "name": result.name,
                    "duration_seconds": result.duration_seconds,
                    "evaluation": asdict(result.evaluation),
                }
                for result in experiment.scenarios
            ],
        }

        output_path = REPORT_DIR / "olist_detection_experiment.json"

        output_path.write_text(
            json.dumps(output, indent=2),
            encoding="utf-8",
        )

        print(json.dumps(output, indent=2))
        print(f"\nReport saved to: {output_path}")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
