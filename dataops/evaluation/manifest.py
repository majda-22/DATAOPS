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


def build_manifest(
    *,
    dataset: str,
    contract_version: int,
    contract_path: Path,
    detector_name: str,
    detector_version: str,
    scenario_names: tuple[str, ...],
    random_seed: int | None = None,
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
    )


def manifest_to_dict(manifest: ExperimentManifest) -> dict:
    return asdict(manifest)
