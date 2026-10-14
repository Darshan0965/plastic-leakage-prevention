
import csv
import json
from pathlib import Path

base_dir = Path(__file__).resolve().parent
geojson_path = base_dir / "data" / "ward178_drains.geojson"
output_path = base_dir / "data" / "processed" / "field_observations_template.csv"

output_path.parent.mkdir(parents=True, exist_ok=True)

with geojson_path.open("r", encoding="utf-8") as file:
    geojson = json.load(file)

columns = [
    "drain_id",
    "observation_date",
    "plastic_accumulation",
    "blockage_observed",
    "rainfall_observed",
    "evidence_photo_reference",
    "inspection_notes",
    "verification_status",
]

with output_path.open("w", newline="", encoding="utf-8-sig") as file:
    writer = csv.DictWriter(file, fieldnames=columns)
    writer.writeheader()

    for feature in geojson.get("features", []):
        properties = feature.get("properties", {})
        drain_id = properties.get("objectid", properties.get("drain_id", ""))

        writer.writerow({
            "drain_id": drain_id,
            "observation_date": "",
            "plastic_accumulation": "",
            "blockage_observed": "",
            "rainfall_observed": "",
            "evidence_photo_reference": "",
            "inspection_notes": "",
            "verification_status": "UNVERIFIED",
        })

print(f"Template created: {output_path}")
print(f"Drain records: {len(geojson.get('features', []))}")
