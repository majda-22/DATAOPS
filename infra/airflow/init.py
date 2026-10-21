"""Prepare local Airflow storage, login credentials, and database."""

import json
import os
import subprocess
from pathlib import Path

# Only this initialization container starts as root.
for directory in (Path("/opt/airflow/logs"), Path("/opt/airflow/auth")):
    directory.mkdir(parents=True, exist_ok=True)
    os.chown(directory, 50000, 0)

# Run the remaining setup as Airflow's normal user.
os.setgid(0)
os.setuid(50000)

os.environ["HOME"] = "/home/airflow"
os.environ["USER"] = "airflow"
os.environ["LOGNAME"] = "airflow"

password_file = Path("/opt/airflow/auth/passwords.json")
password_file.write_text(
    json.dumps({"admin": os.environ["AIRFLOW_ADMIN_PASSWORD"]}),
    encoding="utf-8",
)
password_file.chmod(0o600)

subprocess.run(["airflow", "db", "migrate"], check=True)
print("Airflow database and admin login initialized.")
