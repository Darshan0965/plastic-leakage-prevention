
import json
import math
from collections import Counter, defaultdict, deque
from pathlib import Path

# --------------------------------------------------
# Plastic Leakage Prevention System
# Drainage network geometry analysis
#
# This script does NOT modify your source GeoJSON.
# Candidate links remain unverified.
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DRAIN_FILE = BASE_DIR / "data" / "ward178_drains.geojson"
CONNECTION_FILE = (
    BASE_DIR / "data" / "processed" / "candidate_connections.geojson"
)
OUTPUT_DIR = BASE_DIR / "data" / "processed"

# Geometry-based proximity is only a screening heuristic.
ENDPOINT_TOLERANCE_M = 5.0


def haversine_m(a, b):
    """Distance in metres between [longitude, latitude] coordinates."""
    lon1, lat1 = map(math.radians, a[:2])
    lon2, lat2 = map(math.radians, b[:2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 2 * 6371000 * math.asin(math.sqrt(min(1, h)))


def get_endpoints(geometry):
    """Return first and last coordinates of a line geometry."""
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
    if not DRAIN_FILE.exists():
        raise FileNotFoundError(f"Drain GeoJSON not found: {DRAIN_FILE}")

    with DRAIN_FILE.open("r", encoding="utf-8") as file:
        drains = json.load(file)

    features = drains.get("features", [])
    print(f"Drain features loaded: {len(features)}")

    # Give each feature a stable ID from its objectid property.
    endpoints = {}
    for index, feature in enumerate(features, start=1):
        properties = feature.get("properties") or {}
        drain_id = str(properties.get("objectid", index))
        result = get_endpoints(feature.get("geometry"))

        if result:
            endpoints[drain_id] = result
        else:
            print(f"WARNING: Drain {drain_id} has no usable line endpoints.")

    # Find geometric endpoint proximity candidates.
    # This does not prove that the drains are physically connected.
    pair_distances = {}
    ids = list(endpoints)

    for i, drain_a in enumerate(ids):
        a_start, a_end = endpoints[drain_a]

        for drain_b in ids[i + 1:]:
            b_start, b_end = endpoints[drain_b]

            options = [
                (haversine_m(a_start, b_start), "start", "start"),
                (haversine_m(a_start, b_end), "start", "end"),
                (haversine_m(a_end, b_start), "end", "start"),
                (haversine_m(a_end, b_end), "end", "end"),
            ]

            distance, endpoint_a, endpoint_b = min(
                options, key=lambda item: item[0]
            )

            if distance <= ENDPOINT_TOLERANCE_M:
                pair_distances[(drain_a, drain_b)] = {
                    "distance_m": round(distance, 3),
                    "endpoint_a": endpoint_a,
                    "endpoint_b": endpoint_b,
                }

    print(
        f"Geometric endpoint pairs within "
        f"{ENDPOINT_TOLERANCE_M:.1f} m: {len(pair_distances)}"
    )

    # Build a separate candidate graph, not a confirmed drainage graph.
    graph = defaultdict(set)

    for drain_id in endpoints:
        graph[drain_id]  # ensure isolated drains are included

    for (drain_a, drain_b), details in pair_distances.items():
        graph[drain_a].add(drain_b)
        graph[drain_b].add(drain_a)

    # Calculate connected groups in the candidate graph.
    visited = set()
    components = []

    for drain_id in graph:
        if drain_id in visited:
            continue

        component = []
        queue = deque([drain_id])
        visited.add(drain_id)

        while queue:
            current = queue.popleft()
            component.append(current)

            for neighbor in graph[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        components.append(sorted(component))

    components.sort(key=len, reverse=True)

    # Load previously exported candidate connections if available.
    exported_count = None
    if CONNECTION_FILE.exists():
        with CONNECTION_FILE.open("r", encoding="utf-8") as file:
            candidate_data = json.load(file)

        exported_count = len(candidate_data.get("features", []))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    report = {
        "analysis_type": "GEOMETRIC_ENDPOINT_PROXIMITY",
        "drain_feature_count": len(features),
        "usable_line_count": len(endpoints),
        "endpoint_tolerance_m": ENDPOINT_TOLERANCE_M,
        "unique_geometric_candidate_pairs": len(pair_distances),
        "exported_candidate_connection_count": exported_count,
        "connected_component_count": len(components),
        "components": [
            {
                "component_number": index,
                "drain_count": len(component),
                "drain_ids": component,
            }
            for index, component in enumerate(components, start=1)
        ],
        "candidate_pairs": [
            {
                "drain_a": drain_a,
                "drain_b": drain_b,
                **details,
                "status": "UNVERIFIED_CANDIDATE",
                "flow_direction": "UNKNOWN",
            }
            for (drain_a, drain_b), details in sorted(
                pair_distances.items(),
                key=lambda item: item[1]["distance_m"],
            )
        ],
        "limitations": [
            "Endpoint proximity does not prove a physical connection.",
            "Connected components are based on candidate proximity only.",
            "No hydraulic flow direction has been inferred.",
            "MultiLineString endpoint handling is approximate.",
        ],
    }

    output_file = OUTPUT_DIR / "drain_network_analysis.json"
    with output_file.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print("\nCandidate-graph summary")
    print("-----------------------")
    print(f"Usable drain lines: {len(endpoints)}")
    print(f"Candidate pairs: {len(pair_distances)}")
    print(f"Connected components: {len(components)}")

    for index, component in enumerate(components, start=1):
        print(
            f"  Component {index}: {len(component)} drain(s) "
            f"-> {', '.join(component)}"
        )

    print(f"\nReport saved to:\n{output_file}")
    print("\nIMPORTANT: These are geometric candidates, not confirmed pipes.")


if __name__ == "__main__":
    main()
