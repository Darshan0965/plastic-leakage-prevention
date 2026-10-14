
import json
from pathlib import Path

import networkx as nx

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"

DRAINS_FILE = DATA_DIR / "ward178_drains.geojson"
CANDIDATES_FILE = PROCESSED_DIR / "candidate_connections.geojson"
OUTPUT_FILE = PROCESSED_DIR / "drain_connectivity_graph.json"


def get_drain_id(properties):
    """Find the source drain identifier."""
    for key in ("objectid", "OBJECTID", "drain_id", "DrainID", "id", "ID"):
        value = properties.get(key)
        if value is not None:
            return str(value)
    return None


def main():
    for path in (DRAINS_FILE, CANDIDATES_FILE):
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")

    with DRAINS_FILE.open("r", encoding="utf-8") as file:
        drains_data = json.load(file)

    with CANDIDATES_FILE.open("r", encoding="utf-8") as file:
        candidates_data = json.load(file)

    graph = nx.Graph()
    missing_drain_ids = []

    # Add every source drain, including isolated drains.
    for feature in drains_data.get("features", []):
        properties = feature.get("properties", {})
        drain_id = get_drain_id(properties)

        if drain_id is None:
            missing_drain_ids.append(properties)
            continue

        graph.add_node(
            drain_id,
            label=f"Drain {drain_id}",
            verification_status="SOURCE_FEATURE",
        )

    # Add geometric candidates as explicitly unverified edges.
    missing_references = []
    invalid_distances = []
    duplicate_pairs = set()
    accepted_edges = 0

    for feature in candidates_data.get("features", []):
        properties = feature.get("properties", {})

        drain_a = properties.get("drain_a")
        drain_b = properties.get("drain_b")

        if drain_a is None or drain_b is None:
            missing_references.append(properties)
            continue

        drain_a = str(drain_a)
        drain_b = str(drain_b)

        if drain_a not in graph or drain_b not in graph:
            missing_references.append({
                "drain_a": drain_a,
                "drain_b": drain_b,
                "reason": "Drain ID not found in source features",
            })
            continue

        distance = properties.get("distance_m")
        if distance is None:
            distance = properties.get("exported_distance_m")

        try:
            distance = float(distance)
        except (TypeError, ValueError):
            invalid_distances.append({
                "drain_a": drain_a,
                "drain_b": drain_b,
                "distance": distance,
            })
            continue

        pair = tuple(sorted((drain_a, drain_b)))
        if pair in duplicate_pairs or graph.has_edge(drain_a, drain_b):
            duplicate_pairs.add(pair)
            continue

        category = (
            "COINCIDENT_ENDPOINTS"
            if distance <= 0.001
            else "NEARBY_ENDPOINTS"
        )

        graph.add_edge(
            drain_a,
            drain_b,
            distance_m=distance,
            review_category=category,
            connection_status="UNVERIFIED_CANDIDATE",
            flow_direction="UNKNOWN",
            verified=False,
        )
        accepted_edges += 1

    components = sorted(
        (sorted(component) for component in nx.connected_components(graph)),
        key=lambda component: (-len(component), component[0]),
    )

    node_rows = [
        {
            "drain_id": node,
            "degree": graph.degree[node],
            "candidate_component": component_index,
            "network_role": (
                "HAS_CANDIDATE_LINKS"
                if graph.degree[node] > 0
                else "ISOLATED_IN_CANDIDATE_GRAPH"
            ),
        }
        for component_index, component in enumerate(components, start=1)
        for node in component
    ]

    edge_rows = [
        {
            "drain_a": drain_a,
            "drain_b": drain_b,
            **attributes,
        }
        for drain_a, drain_b, attributes in graph.edges(data=True)
    ]

    report = {
        "analysis_type": "UNVERIFIED_DRAIN_CONNECTIVITY_GRAPH",
        "source_drain_count": graph.number_of_nodes(),
        "candidate_edge_count": graph.number_of_edges(),
        "candidate_component_count": len(components),
        "isolated_drain_count": sum(
            1 for node in graph.nodes if graph.degree[node] == 0
        ),
        "missing_drain_id_count": len(missing_drain_ids),
        "missing_source_reference_count": len(missing_references),
        "invalid_distance_count": len(invalid_distances),
        "duplicate_candidate_pair_count": len(duplicate_pairs),
        "components": [
            {
                "component_id": index,
                "drain_count": len(component),
                "drain_ids": component,
            }
            for index, component in enumerate(components, start=1)
        ],
        "nodes": node_rows,
        "edges": edge_rows,
        "validation_issues": {
            "missing_drain_ids": missing_drain_ids,
            "missing_source_references": missing_references,
            "invalid_distances": invalid_distances,
            "duplicate_pairs": [list(pair) for pair in sorted(duplicate_pairs)],
        },
        "limitations": [
            "Edges represent geometric candidates, not confirmed connections.",
            "Connected components describe this candidate graph only.",
            "Hydraulic flow direction is unknown.",
            "Source geometry and MultiLineString endpoints need appropriate review.",
        ],
    }

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print("Connectivity graph created")
    print("--------------------------")
    print(f"Drain nodes: {report['source_drain_count']}")
    print(f"Candidate edges: {report['candidate_edge_count']}")
    print(f"Candidate components: {report['candidate_component_count']}")
    print(f"Isolated drains: {report['isolated_drain_count']}")
    print(f"Missing source references: {report['missing_source_reference_count']}")
    print(f"Invalid distances: {report['invalid_distance_count']}")
    print(f"\nSaved to:\n{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
