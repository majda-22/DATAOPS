"""Import the Olist ZIP downloaded from Kaggle into the local raw-data directory."""

import argparse
import shutil
from pathlib import Path
from zipfile import ZipFile

DESTINATION = Path(__file__).resolve().parents[1] / "data" / "raw" / "olist"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Path to the downloaded Kaggle ZIP")
    args = parser.parse_args()
    with ZipFile(args.archive) as archive:
        members = [item for item in archive.infolist() if item.filename.endswith(".csv")]
        names = [Path(item.filename).name for item in members]
        if "olist_orders_dataset.csv" not in names or len(names) != len(set(names)):
            parser.error("Expected an Olist archive containing uniquely named CSV files.")
        DESTINATION.mkdir(parents=True, exist_ok=True)
        for item, name in zip(members, names):
            with archive.open(item) as source, (DESTINATION / name).open("wb") as target:
                shutil.copyfileobj(source, target)
    print(f"Imported {len(members)} CSV files into {DESTINATION}")


if __name__ == "__main__":
    main()
