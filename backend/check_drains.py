
import json
from pathlib import Path

file_path = Path(__file__).parent / "data" / "ward178_drains.geojson"

with file_path.open("r", encoding="utf-8") as file:
    data = json.load(file)

features = data.get("features", [])

print("File:", file_path.name)
print("GeoJSON type:", data.get("type"))
print("Total features:", len(features))

valid_lines = 0

for feature in features:
    geometry = feature.get("geometry") or {}
    properties = feature.get("properties") or {}

    if geometry.get("type") == "MultiLineString":
        valid_lines += 1
    elif geometry.get("type") == "LineString":
        valid_lines += 1

    print(
        "ID:", properties.get("objectid"),
        "| Ward:", properties.get("ward"),
        "| Zone:", properties.get("zone"),
        "| Type:", geometry.get("type"),
    )

print("Features with line geometry:", valid_lines)


print("\n--- Connectivity field inspection ---")

connectivity_fields = [
    "strt_east",
    "strt_north",
    "end_east",
    "end_north",
    "invert_sp",
    "invert_ep",
    "water_flow",
    "drain_type",
    "dlen_km",
]

for feature in features:
    properties = feature.get("properties", {})

    print(f"\nDrain ID: {properties.get('objectid')}")

    for field in connectivity_fields:
        print(f"  {field}: {properties.get(field)}")


import json
from pathlib import Path

file_path = Path(__file__).parent / "data" / "ward178_drains.geojson"

with file_path.open("r", encoding="utf-8") as file:
    data = json.load(file)

fields = [
    "strt_east",
    "strt_north",
    "end_east",
    "end_north",
    "invert_sp",
    "invert_ep",
    "water_flow",
    "drain_type",
    "dlen_km",
]

for feature in data.get("features", [])[:3]:
    props = feature.get("properties", {})
    print(f"\nDrain ID: {props.get('objectid')}")

    for field in fields:
        print(f"  {field}: {props.get(field, 'FIELD NOT IN GEOJSON')}")
