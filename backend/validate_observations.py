
import csv
from pathlib import Path

csv_path = (
    Path(__file__).resolve().parent
    / "data"
    / "processed"
    / "field_observations_template.csv"
)

expected_columns = [
    "drain_id",
    "observation_date",
    "plastic_accumulation",
    "blockage_observed",
    "rainfall_observed",
    "evidence_photo_reference",
    "inspection_notes",
    "verification_status",
]

with csv_path.open("r", newline="", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)
    rows = list(reader)

errors = []

if reader.fieldnames != expected_columns:
    errors.append("Column names or order do not match the expected template.")

ids = [row["drain_id"] for row in rows]

if len(rows) != 43:
    errors.append(f"Expected 43 rows; found {len(rows)}.")

if len(ids) != len(set(ids)):
    errors.append("Duplicate drain IDs found.")

for row in rows:
    if row["verification_status"] != "UNVERIFIED":
        errors.append(
            f"Drain {row['drain_id']} has an unexpected verification status."
        )

if errors:
    print("VALIDATION FAILED")
    for error in errors:
        print("-", error)
else:
    print("VALIDATION PASSED")
    print(f"Rows checked: {len(rows)}")
    print("Unique drain IDs:", len(set(ids)))
    print("All records remain UNVERIFIED.")
