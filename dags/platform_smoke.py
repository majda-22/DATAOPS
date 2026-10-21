"""Verify that Airflow can execute a task and import our application."""

from datetime import UTC, datetime

from airflow.sdk import dag, task


@dag(
    dag_id="platform_smoke",
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    schedule=None,
    catchup=False,
    tags=["smoke"],
)
def platform_smoke():
    @task
    def check_imports():
        import boto3

        import dataops.db.models
        from dataops.observability.recording import record_csv_run

        print(f"Boto3: {boto3.__version__}")
        print(f"Models: {dataops.db.models.__name__}")
        print(f"Recording function: {record_csv_run.__name__}")

    check_imports()


platform_smoke()
