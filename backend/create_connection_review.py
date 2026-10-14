
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"

DRAINS_FILE = PROCESSED_DIR / "candidate_connections.geojson"
OUTPUT_FILE = PROCESSED_DIR / "drain_connection_review.json"


def main():
    if not DRAINS_FILE.exists():
        raise FileNotFoundError(
            f"Could not find candidate file: {DRAINS_FILE}"
        )

    with DRAINS_FILE.open("r", encoding="utf-8") as file:
        geojson = json.load(file)

    features = geojson.get("features", [])
    review_rows = []

    for feature in features:
        properties = feature.get("properties", {})

        drain_a = properties.get("drain_a")
        drain_b = properties.get("drain_b")

        distance = properties.get("distance_m")
        if distance is None:
            distance = properties.get("exported_distance_m")

        if distance is None:
            category = "DISTANCE_MISSING"
        else:
            try:
                distance = float(distance)
            except (TypeError, ValueError):
                distance = None

            if distance is None:
                category = "DISTANCE_INVALID"
            elif distance <= 0.001:
                category = "COINCIDENT_ENDPOINTS"
            else:
                category = "NEARBY_ENDPOINTS"

        review_rows.append({
            "candidate_id": properties.get("candidate_id"),
            "drain_a": str(drain_a) if drain_a is not None else None,
            "drain_b": str(drain_b) if drain_b is not None else None,
            "distance_m": distance,
            "review_category": category,
            "connection_status": "UNVERIFIED_CANDIDATE",
            "flow_direction": "UNKNOWN",
            "verification_required": True,
            "notes": (
                "Geometry-based candidate only. Verify against "
                "authoritative drainage records or a site inspection."
            ),
        })

    review_rows.sort(
        key=lambda row: (
            row["distance_m"] is None,
            row["distance_m"] if row["distance_m"] is not None else 0,
            row["candidate_id"] or 0,
        )
    )

    report = {
        "analysis_type": "DRAIN_CONNECTION_REVIEW",
        "source_file": str(DRAINS_FILE),
        "candidate_count": len(review_rows),
        "coincident_endpoint_count": sum(
            row["review_category"] == "COINCIDENT_ENDPOINTS"
            for row in review_rows
        ),
        "nearby_endpoint_count": sum(
            row["review_category"] == "NEARBY_ENDPOINTS"
            for row in review_rows
        ),
        "unverified_count": len(review_rows),
        "limitations": [
            "Categories describe geometry, not physical connectivity.",
            "Flow direction is unknown.",
            "MultiLineString endpoint interpretation may require review.",
        ],
        "results": review_rows,
    }

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print("Connection review report created")
    print("--------------------------------")
    print(f"Candidates: {report['candidate_count']}")
    print(f"Coincident endpoints: {report['coincident_endpoint_count']}")
    print(f"Nearby endpoints: {report['nearby_endpoint_count']}")
    print(f"Still unverified: {report['unverified_count']}")
    print(f"\nSaved to:\n{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
