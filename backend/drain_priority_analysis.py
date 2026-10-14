
import json
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"

INPUT_FILE = PROCESSED_DIR / "drain_connectivity_graph.json"
OUTPUT_FILE = PROCESSED_DIR / "drain_priority_analysis.json"


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input graph not found: {INPUT_FILE}\n"
            "Run build_connectivity_graph.py first."
        )

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        graph_data = json.load(file)

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    stats = defaultdict(
        lambda: {
            "candidate_degree": 0,
            "coincident_links": 0,
            "nearby_links": 0,
            "neighbor_ids": [],
            "candidate_distances_m": [],
        }
    )

    drain_ids = set()

    for node in nodes:
        drain_id = str(node["drain_id"])
        drain_ids.add(drain_id)
        stats[drain_id]["candidate_degree"] = int(node.get("degree", 0))

    for edge in edges:
        drain_a = str(edge["drain_a"])
        drain_b = str(edge["drain_b"])
        distance = float(edge["distance_m"])
        category = edge.get("review_category", "UNKNOWN")

        for drain_id, neighbor_id in (
            (drain_a, drain_b),
            (drain_b, drain_a),
        ):
            stats[drain_id]["neighbor_ids"].append(neighbor_id)
            stats[drain_id]["candidate_distances_m"].append(distance)

            if category == "COINCIDENT_ENDPOINTS":
                stats[drain_id]["coincident_links"] += 1
            elif category == "NEARBY_ENDPOINTS":
                stats[drain_id]["nearby_links"] += 1

    results = []

    for drain_id in drain_ids:
        item = stats[drain_id]
        degree = item["candidate_degree"]

        if degree >= 3:
            review_priority = "HIGH_REVIEW_PRIORITY"
        elif degree == 2:
            review_priority = "MEDIUM_REVIEW_PRIORITY"
        elif degree == 1:
            review_priority = "LOW_REVIEW_PRIORITY"
        else:
            review_priority = "NO_CANDIDATE_LINKS_FOUND"

        distances = item["candidate_distances_m"]

        results.append({
            "drain_id": drain_id,
            "candidate_degree": degree,
            "coincident_links": item["coincident_links"],
            "nearby_links": item["nearby_links"],
            "neighbor_drain_ids": sorted(item["neighbor_ids"]),
            "minimum_candidate_distance_m": (
                round(min(distances), 3) if distances else None
            ),
            "maximum_candidate_distance_m": (
                round(max(distances), 3) if distances else None
            ),
            "review_priority": review_priority,
            "connection_status": (
                "UNVERIFIED_CANDIDATE"
                if degree > 0
                else "NO_CANDIDATE_LINK_FOUND"
            ),
            "flow_direction": "UNKNOWN",
            "priority_basis": (
                "Number of geometric candidate links; "
                "not a hydraulic or leakage-risk score."
            ),
        })

    results.sort(
        key=lambda row: (
            -row["candidate_degree"],
            -row["coincident_links"],
            row["drain_id"],
        )
    )

    for rank, result in enumerate(results, start=1):
        result["review_rank"] = rank

    report = {
        "analysis_type": "GEOMETRIC_DRAIN_REVIEW_PRIORITY",
        "source_file": str(INPUT_FILE),
        "drain_count": len(results),
        "drains_with_candidate_links": sum(
            row["candidate_degree"] > 0 for row in results
        ),
        "drains_without_candidate_links": sum(
            row["candidate_degree"] == 0 for row in results
        ),
        "high_review_priority_count": sum(
            row["review_priority"] == "HIGH_REVIEW_PRIORITY"
            for row in results
        ),
        "limitations": [
            "Ranks geometric review priority only.",
            "Candidate links are not confirmed physical connections.",
            "This is not a plastic leakage or flood-risk prediction.",
            "No hydraulic flow direction is inferred.",
            "No rainfall, waste, blockage, or field-inspection data is used.",
        ],
        "results": results,
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print("Drain priority analysis completed")
    print("---------------------------------")
    print(f"Drains analyzed: {report['drain_count']}")
    print(
        "Drains with candidate links: "
        f"{report['drains_with_candidate_links']}"
    )
    print(
        "Drains without candidate links: "
        f"{report['drains_without_candidate_links']}"
    )
    print(
        "High review priority: "
        f"{report['high_review_priority_count']}"
    )

    print("\nTop 5 drains for connection review:")
    for row in results[:5]:
        print(
            f"Drain {row['drain_id']}: "
            f"{row['candidate_degree']} candidate links, "
            f"{row['coincident_links']} coincident, "
            f"{row['nearby_links']} nearby"
        )

    print(f"\nReport saved to:\n{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
