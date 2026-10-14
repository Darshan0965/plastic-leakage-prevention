
import csv
import json
import math
from pathlib import Path
from itertools import combinations

BASE_DIR = Path(__file__).parent
INPUT_FILE = BASE_DIR / "data" / "ward178_drains.geojson"
OUTPUT_DIR = BASE_DIR / "data" / "processed"

TOLERANCE_METRES = 5.0
EARTH_RADIUS_METRES = 6_371_000


def distance_metres(a, b):
    lon1, lat1 = a[:2]
    lon2, lat2 = b[:2]

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    dlat = lat2 - lat1
    dlon = math.radians(lon2 - lon1)

    value = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 2 * EARTH_RADIUS_METRES * math.asin(
        math.sqrt(min(1.0, value))
    )


def get_parts(geometry):
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


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Could not find input file: {INPUT_FILE}"
        )

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    features = {}

    for feature in data.get("features", []):
        properties = feature.get("properties", {})
        drain_id = properties.get(
            "objectid",
            feature.get("id"),
        )

        if drain_id is None:
            continue

        features[str(drain_id)] = {
            "properties": properties,
            "parts": get_parts(feature.get("geometry")),
        }

    # Keep the closest endpoint match for each pair of drain features.
    candidate_pairs = {}

    for (id_a, a), (id_b, b) in combinations(features.items(), 2):
        for part_a in a["parts"]:
            for part_b in b["parts"]:
                endpoints_a = [
                    ("start", part_a[0]),
                    ("end", part_a[-1]),
                ]
                endpoints_b = [
                    ("start", part_b[0]),
                    ("end", part_b[-1]),
                ]

                for name_a, point_a in endpoints_a:
                    for name_b, point_b in endpoints_b:
                        distance = distance_metres(point_a, point_b)

                        if distance > TOLERANCE_METRES:
                            continue

                        key = (id_a, id_b)

                        candidate = {
                            "id_a": id_a,
                            "id_b": id_b,
                            "point_a": point_a,
                            "point_b": point_b,
                            "endpoint_a": name_a,
                            "endpoint_b": name_b,
                            "distance_m": distance,
                        }

                        previous = candidate_pairs.get(key)

                        if (
                            previous is None
                            or distance < previous["distance_m"]
                        ):
                            candidate_pairs[key] = candidate

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    geojson_features = []
    csv_rows = []

    for index, item in enumerate(
        sorted(
            candidate_pairs.values(),
            key=lambda row: row["distance_m"],
        ),
        start=1,
    ):
        props_a = features[item["id_a"]]["properties"]
        props_b = features[item["id_b"]]["properties"]

        distance = round(item["distance_m"], 3)

        properties = {
            "candidate_id": index,
            "drain_a": item["id_a"],
            "drain_b": item["id_b"],
            "distance_m": distance,
            "endpoint_a": item["endpoint_a"],
            "endpoint_b": item["endpoint_b"],
            "invert_sp_a": props_a.get("invert_sp"),
            "invert_ep_a": props_a.get("invert_ep"),
            "invert_sp_b": props_b.get("invert_sp"),
            "invert_ep_b": props_b.get("invert_ep"),
            "connection_status": "UNVERIFIED_CANDIDATE",
            "flow_direction": "UNKNOWN",
        }

        # A short connector between the closest endpoints.
        connector = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    item["point_a"][:2],
                    item["point_b"][:2],
                ],
            },
            "properties": properties,
        }

        geojson_features.append(connector)
        csv_rows.append(properties)

    geojson_output = {
        "type": "FeatureCollection",
        "name": "Ward178_candidate_connections",
        "features": geojson_features,
    }

    geojson_path = OUTPUT_DIR / "candidate_connections.geojson"
    csv_path = OUTPUT_DIR / "candidate_connections.csv"

    with geojson_path.open("w", encoding="utf-8") as file:
        json.dump(geojson_output, file, indent=2)

    csv_fields = [
        "candidate_id",
        "drain_a",
        "drain_b",
        "distance_m",
        "endpoint_a",
        "endpoint_b",
        "invert_sp_a",
        "invert_ep_a",
        "invert_sp_b",
        "invert_ep_b",
        "connection_status",
        "flow_direction",
    ]

    with csv_path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"Drain features inspected: {len(features)}")
    print(f"Unique candidate pairs exported: {len(geojson_features)}")
    print(f"GeoJSON output: {geojson_path}")
    print(f"CSV output: {csv_path}")
    print(
        "\nAll exported pairs are UNVERIFIED candidates. "
        "The connector lines are visual aids, not actual drain geometry."
    )


if __name__ == "__main__":
    main()
