from pathlib import Path


def test_project_structure_exists():
    root = Path(__file__).resolve().parents[2]

    expected_paths = [
        "dataops",
        "configs",
        "sql",
        "tests",
        "docs/adr",
        "pyproject.toml",
    ]

    for relative_path in expected_paths:
        assert (root / relative_path).exists(), (
            f"Missing project component: {relative_path}"
        )