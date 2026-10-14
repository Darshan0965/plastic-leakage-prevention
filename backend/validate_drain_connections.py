
import json
import math
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DRAIN_FILE = BASE_DIR / "data" / "ward178_drains.geojson"
CONNECTION_FILE = (
    BASE_DIR / "data" / "processed" / "candidate_connections.geojson"
)
OUTPUT_FILE = (
    BASE_DIR / "data" / "processed" / "connection_validation.json"
)

# Allow a small difference due to rounding in exported coordinates/distances.
DISTANCE_TOLERANCE_M = 0.25


def haversine_m(a, b):
    """Calculate approximate distance in metres between lon/lat points."""
    lon1, lat1 = map(math.radians, a[:2])
    lon2, lat2 = map(math.radians, b[:2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 2 * 6371000 * math.asin(math.sqrt(min(1.0, h)))


def get_line_endpoints(geometry):
    """Return approximate first and last coordinates of a line feature."""
    if not geometry:
        return None

    kind = geometry.get("type")
    coords = geometry.get("coordinates", [])

    if kind == "LineString" and len(coords) >= 2:
        return coords[0], coords[-1]

    if kind == "MultiLineString" and coords:
        first_line = next(
            (line for line in coords if len(line) >= 2), None
        )
        last_line = next(
            (line for line in reversed(coords) if len(line) >= 2), None
        )

        if first_line and last_line:
            return first_line[0], last_line[-1]

    return None


def main():
    for path in (DRAIN_FILE, CONNECTION_FILE):
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")

    with DRAIN_FILE.open("r", encoding="utf-8") as file:
        drain_data = json.load(file)

    with CONNECTION_FILE.open("r", encoding="utf-8") as file:
        connection_data = json.load(file)

    drains = drain_data.get("features", [])
    connections = connection_data.get("features", [])

    # Index source drain geometry by its objectid.
    drain_by_id = {}
    for feature in drains:
        props = feature.get("properties") or {}
        drain_id = props.get("objectid")
        if drain_id is not None:
            drain_by_id[str(drain_id)] = feature

    # Track repeated unordered drain pairs.
    pair_counts = Counter()
    results = []

    zero_length_count = 0
    distance_mismatch_count = 0
    missing_drain_count = 0
    candidate_ids = set()

    for feature in connections:
        props = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates", [])

        candidate_id = props.get("candidate_id")
        drain_a = str(props.get("drain_a", ""))
        drain_b = str(props.get("drain_b", ""))

        pair_key = tuple(sorted((drain_a, drain_b)))
        pair_counts[pair_key] += 1

        duplicate_candidate_id = (
            candidate_id in candidate_ids if candidate_id is not None else False
        )
        if candidate_id is not None:
            candidate_ids.add(candidate_id)

        issues = []

        if drain_a == drain_b:
            issues.append("SAME_DRAIN_ID_ON_BOTH_SIDES")

        if drain_a not in drain_by_id or drain_b not in drain_by_id:
            issues.append("SOURCE_DRAIN_NOT_FOUND")
            missing_drain_count += 1

        if duplicate_candidate_id:
            issues.append("DUPLICATE_CANDIDATE_ID")

        if (
            geometry.get("type") != "LineString"
            or len(coords) < 2
        ):
            issues.append("INVALID_OR_UNSUPPORTED_CONNECTOR_GEOMETRY")
            results.append({
                "candidate_id": candidate_id,
                "drain_a": drain_a,
                "drain_b": drain_b,
                "issues": issues,
                "recalculated_distance_m": None,
                "exported_distance_m": props.get("distance_m"),
                "connection_status": "UNVERIFIED_CANDIDATE",
                "flow_direction": "UNKNOWN",
            })
            continue

        point_a = coords[0]
        point_b = coords[-1]
        recalculated = haversine_m(point_a, point_b)
        exported = props.get("distance_m")

        if recalculated < 0.01:
            issues.append("ZERO_LENGTH_CONNECTOR")
            zero_length_count += 1

        if exported is not None:
            try:
                if abs(recalculated - float(exported)) > DISTANCE_TOLERANCE_M:
                    issues.append("CONNECTOR_DISTANCE_MISMATCH")
                    distance_mismatch_count += 1
            except (TypeError, ValueError):
                issues.append("INVALID_EXPORTED_DISTANCE")

        # Check whether each connector endpoint is near the endpoint
        # of its corresponding source drain.
        for drain_id, connector_point, endpoint_name in (
            (drain_a, point_a, "A"),
            (drain_b, point_b, "B"),
        ):
            source_feature = drain_by_id.get(drain_id)
            if not source_feature:
                continue

            endpoints = get_line_endpoints(source_feature.get("geometry"))
            if not endpoints:
                issues.append(f"SOURCE_DRAIN_{endpoint_name}_HAS_NO_ENDPOINTS")
                continue

            nearest_distance = min(
                haversine_m(connector_point, endpoints[0]),
                haversine_m(connector_point, endpoints[1]),
            )

            if nearest_distance > 1.0:
                issues.append(
                    f"CONNECTOR_ENDPOINT_{endpoint_name}_NOT_NEAR_SOURCE_ENDPOINT"
                )

        results.append({
            "candidate_id": candidate_id,
            "drain_a": drain_a,
            "drain_b": drain_b,
            "exported_distance_m": exported,
            "recalculated_connector_length_m": round(recalculated, 3),
            "issues": issues,
            "connection_status": "UNVERIFIED_CANDIDATE",
            "flow_direction": "UNKNOWN",
        })

    duplicate_pairs = [
        {
            "drain_a": pair[0],
            "drain_b": pair[1],
            "count": count,
        }
        for pair, count in pair_counts.items()
        if count > 1
    ]

    report = {
        "analysis_type": "CANDIDATE_CONNECTION_VALIDATION",
        "drain_feature_count": len(drains),
        "candidate_feature_count": len(connections),
        "unique_unordered_drain_pairs": len(pair_counts),
        "duplicate_unordered_pairs": duplicate_pairs,
        "zero_length_connector_count": zero_length_count,
        "distance_mismatch_count": distance_mismatch_count,
        "missing_source_drain_count": missing_drain_count,
        "distance_tolerance_m": DISTANCE_TOLERANCE_M,
        "results": results,
        "limitations": [
            "This script validates geometry and metadata consistency only.",
            "It does not confirm physical pipe connections.",
            "It does not infer hydraulic flow direction.",
            "MultiLineString endpoint handling is approximate.",
            "Zero-length connectors may be valid when endpoints coincide.",
        ],
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print("Connection validation completed")
    print("--------------------------------")
    print(f"Drain features: {len(drains)}")
    print(f"Candidate features: {len(connections)}")
    print(f"Unique unordered drain pairs: {len(pair_counts)}")
    print(f"Repeated unordered pairs: {len(duplicate_pairs)}")
    print(f"Zero-length connectors: {zero_length_count}")
    print(f"Distance mismatches: {distance_mismatch_count}")
    print(f"Missing source drain references: {missing_drain_count}")
    print(f"\nReport saved to:\n{OUTPUT_FILE}")
    print("\nAll candidate links remain UNVERIFIED.")


if __name__ == "__main__":
    main()
