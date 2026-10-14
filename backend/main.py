from typing import Literal

import csv

import json

import os

import tempfile

from datetime import date

from pathlib import Path

from fastapi import FastAPI, HTTPException

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field

import networkx as nx

app = FastAPI(

    title="Plastic Leakage Prevention API",

    description=(

        "API for drainage pathway analysis, cleanup hotspot ranking, "

        "GCC Ward 178 drain geometry, and field observations."

    ),

    version="0.3.0",

)

# ============================================================

# DEVELOPMENT CORS SETTINGS

# Restrict allowed origins before production deployment.

# ============================================================

app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

)

# ============================================================

# DATA FILE PATHS

# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DRAIN_GEOJSON_PATH = (

    BASE_DIR / "data" / "ward178_drains.geojson"

)

FIELD_OBSERVATIONS_CSV_PATH = (

    BASE_DIR

    / "data"

    / "processed"

    / "field_observations_template.csv"

)

# ============================================================

# REAL GCC DRAIN DATA

# ============================================================

@app.get("/api/real-drains")

def get_real_drains():

    """

    Return locally saved GCC Ward 178 drain geometry.

    This endpoint serves GeoJSON only. It does not infer

    physical flow direction or calculate hotspot scores.

    """

    if not DRAIN_GEOJSON_PATH.is_file():

        raise HTTPException(

            status_code=404,

            detail=(

                "Ward 178 GeoJSON file was not found. "

                "Expected file: backend/data/ward178_drains.geojson"

            ),

        )

    try:

        with DRAIN_GEOJSON_PATH.open(

            "r",

            encoding="utf-8",

        ) as file:

            geojson = json.load(file)

    except json.JSONDecodeError:

        raise HTTPException(

            status_code=500,

            detail="The Ward 178 GeoJSON file contains invalid JSON.",

        )

    except OSError:

        raise HTTPException(

            status_code=500,

            detail="The Ward 178 GeoJSON file could not be read.",

        )

    if geojson.get("type") != "FeatureCollection":

        raise HTTPException(

            status_code=500,

            detail="The GeoJSON file is not a FeatureCollection.",

        )

    return geojson

# ============================================================

# FIELD OBSERVATIONS

# Reads the CSV created for the 43 Ward 178 drains.

# Blank observation fields remain blank.

# These records are not used in synthetic hotspot scoring.

# ============================================================

FIELD_OBSERVATION_COLUMNS = [

    "drain_id",

    "observation_date",

    "plastic_accumulation",

    "blockage_observed",

    "rainfall_observed",

    "evidence_photo_reference",

    "inspection_notes",

    "verification_status",

]

@app.get("/api/field-observations")

def get_field_observations():

    """

    Return field-observation records from the CSV file.

    The template's blank fields are not treated as observations,

    and UNVERIFIED records are not treated as field-verified.

    """

    if not FIELD_OBSERVATIONS_CSV_PATH.is_file():

        raise HTTPException(

            status_code=404,

            detail={

                "error": "Field-observation CSV not found.",

                "expected_file": (

                    "backend/data/processed/"

                    "field_observations_template.csv"

                ),

            },

        )

    try:

        with FIELD_OBSERVATIONS_CSV_PATH.open(

            "r",

            newline="",

            encoding="utf-8-sig",

        ) as file:

            reader = csv.DictReader(file)

            if reader.fieldnames != FIELD_OBSERVATION_COLUMNS:

                raise HTTPException(

                    status_code=500,

                    detail=(

                        "Field-observation CSV has unexpected "

                        "column names or column order."

                    ),

                )

            observations = list(reader)

    except HTTPException:

        raise

    except (OSError, csv.Error) as exc:

        raise HTTPException(

            status_code=500,

            detail=f"Could not read field-observation CSV: {exc}",

        )

    # Check for missing or duplicate drain IDs.

    drain_ids = [

        row.get("drain_id", "").strip()

        for row in observations

    ]

    if any(not drain_id for drain_id in drain_ids):

        raise HTTPException(

            status_code=500,

            detail="One or more field-observation records have no drain ID.",

        )

    if len(drain_ids) != len(set(drain_ids)):

        raise HTTPException(

            status_code=500,

            detail="Duplicate drain IDs found in the observation CSV.",

        )

    verified_count = sum(

        row.get("verification_status", "").strip().upper()

        == "FIELD_VERIFIED"

        for row in observations

    )

    return {

        "count": len(observations),

        "verified_count": verified_count,

        "unverified_count": len(observations) - verified_count,

        "data_type": "field_observation_records",

        "observations": observations,

        "warning": (

            "CSV records represent entered observations only. "

            "Blank fields do not mean that pollution or blockage "

            "is absent. Verification status must reflect actual evidence."

        ),

    }


class FieldObservationUpdate(BaseModel):
    """Fields that can be entered during a drain inspection."""

    drain_id: str = Field(min_length=1, max_length=100)
    observation_date: str = ""
    plastic_accumulation: str = Field(default="", max_length=100)
    blockage_observed: str = Field(default="", max_length=100)
    rainfall_observed: str = Field(default="", max_length=100)
    evidence_photo_reference: str = Field(default="", max_length=1000)
    inspection_notes: str = Field(default="", max_length=5000)


@app.put("/api/field-observations/{drain_id}")
def update_field_observation(
    drain_id: str,
    request: FieldObservationUpdate,
):
    """
    Save an inspection form to the CSV.

    Saving an observation does not make it FIELD_VERIFIED. Verification
    status is preserved from the CSV, or set to UNVERIFIED for new rows.
    """
    requested_id = drain_id.strip()
    payload_id = request.drain_id.strip()

    if not requested_id or requested_id != payload_id:
        raise HTTPException(
            status_code=400,
            detail="The drain ID in the URL and request body must match.",
        )

    observation_date = request.observation_date.strip()
    if observation_date:
        try:
            date.fromisoformat(observation_date)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="observation_date must be a valid YYYY-MM-DD date.",
            )

    if not FIELD_OBSERVATIONS_CSV_PATH.is_file():
        raise HTTPException(
            status_code=404,
            detail="Field-observation CSV was not found.",
        )

    try:
        with FIELD_OBSERVATIONS_CSV_PATH.open(
            "r", newline="", encoding="utf-8-sig"
        ) as file:
            reader = csv.DictReader(file)
            if reader.fieldnames != FIELD_OBSERVATION_COLUMNS:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        "Field-observation CSV has unexpected column "
                        "names or column order."
                    ),
                )
            observations = list(reader)
    except HTTPException:
        raise
    except (OSError, csv.Error) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read field-observation CSV: {exc}",
        )

    matching_rows = [
        row for row in observations
        if row.get("drain_id", "").strip() == requested_id
    ]
    if len(matching_rows) > 1:
        raise HTTPException(
            status_code=500,
            detail="Duplicate drain IDs found in the observation CSV.",
        )

    if matching_rows:
        row = matching_rows[0]
        row.update(
            {
                "observation_date": observation_date,
                "plastic_accumulation": request.plastic_accumulation.strip(),
                "blockage_observed": request.blockage_observed.strip(),
                "rainfall_observed": request.rainfall_observed.strip(),
                "evidence_photo_reference": request.evidence_photo_reference.strip(),
                "inspection_notes": request.inspection_notes.strip(),
            }
        )
        # Deliberately preserve the existing verification status.
        row["verification_status"] = (
            row.get("verification_status", "").strip() or "UNVERIFIED"
        )
    else:
        row = {
            "drain_id": requested_id,
            "observation_date": observation_date,
            "plastic_accumulation": request.plastic_accumulation.strip(),
            "blockage_observed": request.blockage_observed.strip(),
            "rainfall_observed": request.rainfall_observed.strip(),
            "evidence_photo_reference": request.evidence_photo_reference.strip(),
            "inspection_notes": request.inspection_notes.strip(),
            "verification_status": "UNVERIFIED",
        }
        observations.append(row)

    temp_path = None
    try:
        FIELD_OBSERVATIONS_CSV_PATH.parent.mkdir(
            parents=True, exist_ok=True
        )
        with tempfile.NamedTemporaryFile(
            mode="w",
            newline="",
            encoding="utf-8",
            dir=FIELD_OBSERVATIONS_CSV_PATH.parent,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            writer = csv.DictWriter(
                temp_file,
                fieldnames=FIELD_OBSERVATION_COLUMNS,
            )
            writer.writeheader()
            writer.writerows(observations)

        os.replace(temp_path, FIELD_OBSERVATIONS_CSV_PATH)
    except (OSError, csv.Error) as exc:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise HTTPException(
            status_code=500,
            detail=f"Could not save field-observation CSV: {exc}",
        )

    return {
        "message": "Field observation saved.",
        "drain_id": requested_id,
        "verification_status": row["verification_status"],
        "data_type": "field_observation_records",
        "warning": (
            "Saving a record does not verify it. Verification status "
            "must reflect actual evidence."
        ),
    }


# ============================================================

# SYNTHETIC DEMONSTRATION NETWORK

# The following data is NOT real GCC network data.

# ============================================================

DRAINS = {

    "market_drain": {

        "name": "Market Road Drain",

        "litter_kg": 42,

        "confidence": 0.90,

        "feasibility": 0.90,

    },

    "residential_drain": {

        "name": "Residential Drain",

        "litter_kg": 24,

        "confidence": 0.80,

        "feasibility": 0.75,

    },

    "park_drain": {

        "name": "Park Drain",

        "litter_kg": 10,

        "confidence": 0.95,

        "feasibility": 0.95,

    },

    "main_channel": {

        "name": "Main Drainage Channel",

        "litter_kg": 8,

        "confidence": 0.85,

        "feasibility": 0.60,

    },

    "river_outlet": {

        "name": "River Outlet",

        "litter_kg": 5,

        "confidence": 0.90,

        "feasibility": 0.50,

    },

}

# Assumed connections for the synthetic demo only.

EDGES = [

    ("market_drain", "main_channel"),

    ("residential_drain", "main_channel"),

    ("park_drain", "main_channel"),

    ("main_channel", "river_outlet"),

]

GRAPH = nx.DiGraph()

for node_id, details in DRAINS.items():

    GRAPH.add_node(node_id, **details)

GRAPH.add_edges_from(EDGES)

# ============================================================

# HOTSPOT SCORING CONFIGURATION

# ============================================================

RainScenario = Literal["light", "moderate", "heavy"]

SCENARIO_FACTORS = {

    "light": 0.60,

    "moderate": 1.00,

    "heavy": 1.50,

}

class HotspotRequest(BaseModel):

    rainfall: RainScenario = "moderate"

    top_k: int = Field(default=5, ge=1, le=20)

def downstream_nodes(node_id: str) -> list[str]:

    """Return reachable downstream nodes in the demo graph."""

    return list(nx.descendants(GRAPH, node_id))

def estimate_score(

    node_id: str,

    rainfall: RainScenario,

) -> dict:

    """

    Calculate an illustrative score using synthetic demo values.

    This heuristic is not calibrated or validated for real-world

    environmental or public-safety decisions.

    """

    data = DRAINS[node_id]

    downstream = downstream_nodes(node_id)

    factor = SCENARIO_FACTORS[rainfall]

    litter_component = min(

        data["litter_kg"] / 50.0,

        1.0,

    )

    connectivity_component = min(

        len(downstream) / 3.0,

        1.0,

    )

    scenario_component = min(

        (factor * data["litter_kg"]) / 60.0,

        1.0,

    )

    feasibility_component = data["feasibility"]

    raw_score = (

        0.30 * litter_component

        + 0.25 * connectivity_component

        + 0.25 * scenario_component

        + 0.20 * feasibility_component

    ) * 100

    confidence_adjusted_score = (

        raw_score * data["confidence"]

    )

    estimated_leakage_kg = round(

        data["litter_kg"] * factor * 0.35,

        2,

    )

    return {

        "id": node_id,

        "name": data["name"],

        "observed_litter_kg": data["litter_kg"],

        "confidence": data["confidence"],

        "downstream_locations": downstream,

        "downstream_connection_count": len(downstream),

        "estimated_leakage_kg": estimated_leakage_kg,

        "priority_score": round(

            confidence_adjusted_score,

            2,

        ),

        "rainfall_scenario": rainfall,

        "note": (

            "Illustrative estimate using synthetic data; "

            "not validated for real-world decisions."

        ),

    }

# ============================================================

# API ENDPOINTS

# ============================================================

@app.get("/")

def root():

    return {

        "message": "Plastic Leakage Prevention API is running.",

        "docs": "/docs",

        "real_drain_data": "/api/real-drains",

        "field_observations": "/api/field-observations",

        "demo_network": "/api/network",

        "demo_hotspots": "/api/hotspots",

        "warning": (

            "The real-drains endpoint serves GCC GeoJSON. "

            "Field observations are read from a separate CSV. "

            "The network and hotspot scoring endpoints still "

            "use synthetic demonstration data."

        ),

    }

@app.get("/api/network")

def get_network():

    """Return the synthetic demonstration network."""

    return {

        "nodes": [

            {"id": node_id, **details}

            for node_id, details in DRAINS.items()

        ],

        "edges": [

            {"from": source, "to": target}

            for source, target in EDGES

        ],

        "data_type": "synthetic_demo",

    }

@app.post("/api/hotspots")

def rank_hotspots(request: HotspotRequest):

    """Rank synthetic demonstration hotspots."""

    candidates = [

        estimate_score(node_id, request.rainfall)

        for node_id in DRAINS

        if node_id != "river_outlet"

    ]

    candidates.sort(

        key=lambda item: item["priority_score"],

        reverse=True,

    )

    for index, item in enumerate(candidates, start=1):

        item["rank"] = index

    return {

        "rainfall_scenario": request.rainfall,

        "hotspots": candidates[:request.top_k],

        "data_type": "synthetic_demo",

        "method": (

            "Transparent baseline heuristic; "

            "requires measured field data and validation."

        ),

    }

@app.get("/api/path/{node_id}")

def trace_path(node_id: str):

    """Trace paths through the synthetic demonstration graph."""

    if node_id not in GRAPH:

        raise HTTPException(

            status_code=404,

            detail={

                "error": "Unknown demo node ID",

                "valid_ids": list(GRAPH.nodes),

            },

        )

    paths = []

    for target in GRAPH.nodes:

        if (

            target != node_id

            and nx.has_path(GRAPH, node_id, target)

        ):

            paths.extend(

                list(

                    nx.all_simple_paths(

                        GRAPH,

                        node_id,

                        target,

                    )

                )

            )

    return {

        "start": node_id,

        "paths": paths,

        "data_type": "synthetic_demo",

        "warning": (

            "Paths represent assumed demo connectivity, "

            "not verified physical flow."

        ),

    }
