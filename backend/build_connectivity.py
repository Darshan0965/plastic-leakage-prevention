
import json
import math
from pathlib import Path
from itertools import combinations

DATA_FILE = Path(__file__).parent / "data" / "ward178_drains.geojson"
TOLERANCE_METRES = 5.0
EARTH_RADIUS_METRES = 6_371_000


def distance_metres(a, b):
    lon1, lat1 = a[:2]
    lon2, lat2 = b[:2]

    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    dlat = lat2 - lat1
    dlon = math.radians(lon2 - lon1)

    value = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_METRES * math.asin(
        math.sqrt(min(1.0, value))
    )


def get_parts(geometry):
    if not geometry:
        return []

    kind = geometry.get("type")
    coords = geometry.get("coordinates", [])

    if kind == "LineString":
        return [coords] if len(coords) >= 2 else []

    if kind == "MultiLineString":
        return [part for part in coords if len(part) >= 2]

    return []


def main():
    with DATA_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    features = {}

    for feature in data.get("features", []):
        props = feature.get("properties", {})
        drain_id = props.get("objectid", feature.get("id"))

        if drain_id is None:
            continue

        features[str(drain_id)] = {
            "properties": props,
            "parts": get_parts(feature.get("geometry")),
        }

    # Keep the closest endpoint match for each unique drain pair.
    pairs = {}

    for (id_a, a), (id_b, b) in combinations(features.items(), 2):
        for part_a in a["parts"]:
            for part_b in b["parts"]:
                for name_a, point_a in (
                    ("start", part_a[0]),
                    ("end", part_a[-1]),
                ):
                    for name_b, point_b in (
                        ("start", part_b[0]),
                        ("end", part_b[-1]),
                    ):
                        distance = distance_metres(point_a, point_b)

                        if distance > TOLERANCE_METRES:
                            continue

                        key = (id_a, id_b)
                        candidate = {
                            "id_a": id_a,
                            "id_b": id_b,
                            "distance": distance,
                            "endpoint_a": name_a,
                            "endpoint_b": name_b,
                        }

                        if (
                            key not in pairs
                            or distance < pairs[key]["distance"]
                        ):
                            pairs[key] = candidate

    results = sorted(
        pairs.values(),
        key=lambda item: item["distance"],
    )

    print(f"Drain features: {len(features)}")
    print(f"Unique candidate drain pairs: {len(results)}")
    print(f"Endpoint tolerance: {TOLERANCE_METRES} metres\n")

    for item in results:
        a = features[item["id_a"]]["properties"]
        b = features[item["id_b"]]["properties"]

        print(
            f"{item['id_a']} <-> {item['id_b']} | "
            f"{item['distance']:.2f} m | "
            f"endpoints: {item['endpoint_a']}/{item['endpoint_b']}"
        )
        print(
            f"  Invert levels A: start={a.get('invert_sp')}, "
            f"end={a.get('invert_ep')}"
        )
        print(
            f"  Invert levels B: start={b.get('invert_sp')}, "
            f"end={b.get('invert_ep')}"
        )

    print(
        "\nThese are candidate geometric connections, not verified "
        "hydraulic connections. Invert levels alone do not establish "
        "the direction of water flow."
    )


if __name__ == "__main__":
    main()
