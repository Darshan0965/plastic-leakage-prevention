
import json
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"

DRAINS_FILE = DATA_DIR / "ward178_drains.geojson"
PRIORITY_FILE = PROCESSED_DIR / "drain_priority_analysis.json"
OUTPUT_FILE = PROCESSED_DIR / "drain_priority_map.geojson"


def get_drain_id(properties):
    for key in ("objectid", "OBJECTID", "drain_id", "DrainID", "id", "ID"):
        value = properties.get(key)
        if value is not None:
            return str(value)
    return None


def main():
    for path in (DRAINS_FILE, PRIORITY_FILE):
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

    with DRAINS_FILE.open("r", encoding="utf-8") as file:
        drains = json.load(file)

    with PRIORITY_FILE.open("r", encoding="utf-8") as file:
        priority_report = json.load(file)

    priority_by_id = {}
    for row in priority_report.get("results", []):
        drain_id = str(row["drain_id"])
        if drain_id in priority_by_id:
            raise ValueError(f"Duplicate drain ID in priority report: {drain_id}")
        priority_by_id[drain_id] = row

    output_features = []
    missing_source_ids = []
    unmatched_drains = []
    id_counts = Counter()

    for source_feature in drains.get("features", []):
        feature = json.loads(json.dumps(source_feature))
        properties = feature.setdefault("properties", {})
        drain_id = get_drain_id(properties)

        if drain_id is None:
            missing_source_ids.append("Feature has no recognized drain ID")
            continue

        id_counts[drain_id] += 1
        priority = priority_by_id.get(drain_id)

        if priority is None:
            unmatched_drains.append(drain_id)
            properties["review_rank"] = None
            properties["candidate_degree"] = 0
            properties["coincident_links"] = 0
            properties["nearby_links"] = 0
            properties["review_priority"] = "NOT_IN_PRIORITY_REPORT"
            properties["connection_status"] = "UNVERIFIED"
        else:
            properties["review_rank"] = priority["review_rank"]
            properties["candidate_degree"] = priority["candidate_degree"]
            properties["coincident_links"] = priority["coincident_links"]
            properties["nearby_links"] = priority["nearby_links"]
            properties["review_priority"] = priority["review_priority"]
            properties["connection_status"] = priority["connection_status"]

        properties["flow_direction"] = "UNKNOWN"
        properties["priority_interpretation"] = (
            "Geometric connection-review priority only; "
            "not a confirmed leakage or flood-risk score."
        )

        output_features.append(feature)

    duplicate_source_ids = sorted(
        drain_id for drain_id, count in id_counts.items() if count > 1
    )

    result = {
        "type": "FeatureCollection",
        "name": "Ward 178 Drain Review Priority",
        "features": output_features,
        "metadata": {
            "analysis_type": "GEOMETRIC_DRAIN_REVIEW_PRIORITY_MAP",
            "source_drain_file": str(DRAINS_FILE),
            "priority_file": str(PRIORITY_FILE),
            "source_feature_count": len(drains.get("features", [])),
            "exported_feature_count": len(output_features),
            "missing_source_id_count": len(missing_source_ids),
            "unmatched_drain_ids": unmatched_drains,
            "duplicate_source_drain_ids": duplicate_source_ids,
            "limitations": [
                "Review priorities are based on geometric candidate links.",
                "No candidate links does not prove a drain is physically isolated.",
                "Connections and flow direction remain unverified.",
                "This is not a plastic leakage or flood-risk prediction.",
            ],
        },
    }

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=2)

    print("Priority map GeoJSON created")
    print("----------------------------")
    print(f"Source features: {result['metadata']['source_feature_count']}")
    print(f"Exported features: {result['metadata']['exported_feature_count']}")
    print(f"Missing source IDs: {len(missing_source_ids)}")
    print(f"Unmatched drain IDs: {len(unmatched_drains)}")
    print(f"Duplicate source IDs: {len(duplicate_source_ids)}")
    print(f"\nSaved to:\n{OUTPUT_FILE}")

    if missing_source_ids:
        print("\nWARNING: Some features were skipped because they had no drain ID.")


if __name__ == "__main__":
    main()
