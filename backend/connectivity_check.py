
import json
import math
from pathlib import Path
from itertools import combinations

# Read the saved GCC Ward 178 GeoJSON.
DATA_FILE = (
    Path(__file__).parent
    / "data"
    / "ward178_drains.geojson"
)

# Starting tolerance for identifying nearby endpoints.
# This finds candidates; it does NOT prove a physical connection.
TOLERANCE_METRES = 5.0
EARTH_RADIUS_METRES = 6_371_000


def distance_metres(point_a, point_b):
    """Calculate approximate distance between two lon/lat points."""
    lon1, lat1 = point_a[:2]
    lon2, lat2 = point_b[:2]

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    delta_lat = lat2 - lat1
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    return 2 * EARTH_RADIUS_METRES * math.asin(
        math.sqrt(min(1.0, a))
    )


def get_line_parts(geometry):
    """Return individual coordinate sequences from line geometry."""
    if not geometry:
        return []

    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates", [])

    if geometry_type == "LineString":
        return [coordinates] if len(coordinates) >= 2 else []

    if geometry_type == "MultiLineString":
        return [
            part for part in coordinates
            if len(part) >= 2
        ]

    return []


def get_endpoints(feature):
    """Extract the endpoints of each line part."""
    geometry = feature.get("geometry")
    endpoints = []

    for part_number, coordinates in enumerate(
        get_line_parts(geometry), start=1
    ):
        endpoints.append({
            "part": part_number,
            "end": "start",
            "coordinate": coordinates[0],
        })
        endpoints.append({
            "part": part_number,
            "end": "end",
            "coordinate": coordinates[-1],
        })

    return endpoints


def main():
    if not DATA_FILE.exists():
        print(f"ERROR: GeoJSON file not found: {DATA_FILE}")
        return

    with DATA_FILE.open("r", encoding="utf-8") as file:
        geojson = json.load(file)

    features = geojson.get("features", [])
    print(f"Loaded {len(features)} drain features.")
    print(f"Endpoint tolerance: {TOLERANCE_METRES:.1f} metres")
    print("Checking endpoints of different drain features...\n")

    endpoints_by_feature = []

    for feature in features:
        properties = feature.get("properties", {})
        drain_id = properties.get("objectid")

        if drain_id is None:
            drain_id = feature.get("id", "unknown")

        endpoints = get_endpoints(feature)

        if endpoints:
            endpoints_by_feature.append({
                "id": drain_id,
                "endpoints": endpoints,
            })

    candidates = []

    # Compare endpoints belonging to different drain features.
    for first, second in combinations(endpoints_by_feature, 2):
        for endpoint_a in first["endpoints"]:
            for endpoint_b in second["endpoints"]:
                distance = distance_metres(
                    endpoint_a["coordinate"],
                    endpoint_b["coordinate"],
                )

                if distance <= TOLERANCE_METRES:
                    candidates.append({
                        "drain_a": first["id"],
                        "endpoint_a": endpoint_a,
                        "drain_b": second["id"],
                        "endpoint_b": endpoint_b,
                        "distance_m": distance,
                    })

    candidates.sort(key=lambda item: item["distance_m"])

    print(f"Endpoint pairs within tolerance: {len(candidates)}")

    if not candidates:
        print(
            "\nNo endpoint pairs found within the chosen tolerance."
        )
        print(
            "This does not mean the drains are disconnected; "
            "they may meet along line interiors or need a different "
            "tolerance."
        )
    else:
        for item in candidates:
            a = item["endpoint_a"]
            b = item["endpoint_b"]

            print(
                f"Drain {item['drain_a']} ({a['part']}:{a['end']}) "
                f"<-> Drain {item['drain_b']} ({b['part']}:{b['end']}) "
                f"| distance = {item['distance_m']:.2f} m"
            )

    print(
        "\nIMPORTANT: These are geometric proximity candidates only. "
        "They do not confirm hydraulic connections or flow direction."
    )


if __name__ == "__main__":
    main()
