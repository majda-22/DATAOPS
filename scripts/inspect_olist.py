
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "olist"


def inspect_csv(path: Path) -> None:
    print(f"\nFile: {path.name}")
    print(f"Size: {path.stat().st_size:,} bytes")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        print("Columns:")
        print(reader.fieldnames)

        row_count = 0
        first_rows = []

        for row in reader:
            row_count += 1

            if len(first_rows) < 5:
                first_rows.append(row)

    print(f"Data rows: {row_count:,}")
    print("\nFirst five rows:")

    for row in first_rows:
        print(row)


def main() -> None:
    orders_file = DATA_DIR / "olist_orders_dataset.csv"

    if not orders_file.exists():
        raise FileNotFoundError(
            f"Orders file not found: {orders_file}\n"
            "Check that the CSV files are directly inside data/raw/olist/."
        )

    inspect_csv(orders_file)


if __name__ == "__main__":
    main()
