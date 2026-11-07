import json
import subprocess
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class ExperimentManifest:
    """Configuration used to identify an evaluation experiment."""

    dataset: str
    contract_version: int
    contract_sha256: str
    detector_name: str
    detector_version: str
    scenario_names: tuple[str, ...]
    random_seed: int | None = None
    git_commit: str | None = None
    input_sha256: str | None = None


def build_manifest(
    *,
    dataset: str,
    contract_version: int,
    contract_path: Path,
    detector_name: str,
    detector_version: str,
    scenario_names: tuple[str, ...],
    random_seed: int | None = None,
    git_commit: str | None = None,
    input_sha256: str | None = None,
) -> ExperimentManifest:
    """Build a manifest using the exact contract file contents."""

    if not contract_path.is_file():
        raise FileNotFoundError(contract_path)

    if not dataset.strip() or not detector_name.strip():
        raise ValueError("Dataset and detector name are required")

    if not detector_version.strip():
        raise ValueError("Detector version is required")

    if contract_version < 1:
        raise ValueError("Contract version must be positive")

    if not scenario_names or len(set(scenario_names)) != len(scenario_names):
        raise ValueError("Scenario names must be present and unique")

    contract_hash = sha256(contract_path.read_bytes()).hexdigest()

    return ExperimentManifest(
        dataset=dataset,
        contract_version=contract_version,
        contract_sha256=contract_hash,
        detector_name=detector_name,
        detector_version=detector_version,
        scenario_names=scenario_names,
        random_seed=random_seed,
        git_commit=git_commit,
        input_sha256=input_sha256,
    )


def manifest_to_dict(manifest: ExperimentManifest) -> dict:
    return asdict(manifest)


def fingerprint_records(
    records: Sequence[dict[str, str | None]],
) -> str:
    """Generate a deterministic fingerprint of ordered records."""

    serialized = json.dumps(
        list(records),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return sha256(serialized.encode("utf-8")).hexdigest()


def get_git_commit(project_root: Path) -> str:
    """Return the current Git revision."""

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )

    return result.stdout.strip()
