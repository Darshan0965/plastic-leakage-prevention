import { useEffect, useMemo, useState } from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Polyline,
  GeoJSON,
  Tooltip,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./App.css";
const API = "http://127.0.0.1:8000";
const CONNECTIONS_URL = "/candidate_connections.geojson";
const PRIORITY_MAP_URL = "/drain_priority_map.geojson";
// Fictional demo locations only. These are not GCC drain coordinates.
const POSITIONS = {
  market_drain: [13.045, 80.205],
  residential_drain: [13.035, 80.225],
  park_drain: [13.020, 80.190],
  main_channel: [13.010, 80.215],
  river_outlet: [12.995, 80.225],
};
function scoreColor(score) {
  if (score >= 60) return "#e34b4b";
  if (score >= 35) return "#e7a33e";
  return "#2d9b75";
}
function FitDrainBounds({ data }) {
  const map = useMap();
  useEffect(() => {
    if (!data?.features?.length) return;
    const layer = L.geoJSON(data);
    const bounds = layer.getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds, {
        padding: [24, 24],
        maxZoom: 17,
      });
    }
  }, [data, map]);
  return null;
}
function FlyToCandidate({ feature }) {
  const map = useMap();
  useEffect(() => {
    if (!feature?.geometry?.coordinates?.length) return;
    const coords = feature.geometry.coordinates;
    const first = coords[0];
    const last = coords[coords.length - 1];
    const center = [(first[1] + last[1]) / 2, (first[0] + last[0]) / 2];
    map.flyTo(center, Math.max(map.getZoom(), 17), { duration: 0.6 });
  }, [feature, map]);
  return null;
}
function formatLength(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(3) : "—";
}
export default function App() {
  const [rainfall, setRainfall] = useState("moderate");
  const [network, setNetwork] = useState({
    nodes: [],
    edges: [],
  });
  const [hotspots, setHotspots] = useState([]);
  const [realDrains, setRealDrains] = useState(null);
  const [candidateConnections, setCandidateConnections] = useState(null);
  const [priorityMap, setPriorityMap] = useState(null);
  const [showPriorityMap, setShowPriorityMap] = useState(true);
  const [priorityError, setPriorityError] = useState("");
  const [showCandidateConnections, setShowCandidateConnections] = useState(true);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [drainError, setDrainError] = useState("");
  const [connectionError, setConnectionError] = useState("");
  const [drainSearch, setDrainSearch] = useState("");
  const [selectedDrain, setSelectedDrain] = useState(null);
  const [fieldObservations, setFieldObservations] = useState([]);
  const [observationError, setObservationError] = useState("");
  const [observationsLoading, setObservationsLoading] = useState(true);
  const [observationSearch, setObservationSearch] = useState("");

  async function loadFieldObservations() {
    setObservationsLoading(true);
    setObservationError("");

    try {
      const response = await fetch(`${API}/api/field-observations`);
      if (!response.ok) {
        throw new Error(
          `Field-observations API returned HTTP ${response.status}.`
        );
      }
      const data = await response.json();
      setFieldObservations(data.observations || []);
    } catch (err) {
      console.error("Field-observations loading error:", err);
      setObservationError(
        err.message || "Could not load field observations."
      );
    } finally {
      setObservationsLoading(false);
    }
  }

  const filteredObservations = fieldObservations.filter((item) =>
    String(item.drain_id ?? "")
      .toLowerCase()
      .includes(observationSearch.trim().toLowerCase())
  );

  const verifiedObservationCount = fieldObservations.filter(
    (item) =>
      String(item.verification_status ?? "").toUpperCase() ===
      "FIELD_VERIFIED"
  ).length;
  async function loadDashboard(scenario = rainfall) {
    setLoading(true);
    setError("");
    try {
      const [networkResponse, hotspotResponse] = await Promise.all([
        fetch(`${API}/api/network`),
        fetch(`${API}/api/hotspots`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ rainfall: scenario, top_k: 5 }),
        }),
      ]);
      if (!networkResponse.ok || !hotspotResponse.ok) {
        throw new Error("The dashboard API returned an error.");
      }
      const networkData = await networkResponse.json();
      const hotspotData = await hotspotResponse.json();
      setNetwork(networkData);
      setHotspots(hotspotData.hotspots || []);
    } catch (err) {
      console.error("Dashboard API error:", err);
      setError("Cannot connect to FastAPI. Check that the backend is running.");
    } finally {
      setLoading(false);
    }
  }
  async function loadRealDrains() {
    setDrainError("");
    try {
      const response = await fetch(`${API}/api/real-drains`);
      if (!response.ok) {
        throw new Error(`Real-drain endpoint returned HTTP ${response.status}.`);
      }
      const data = await response.json();
      if (
        data.type !== "FeatureCollection" ||
        !Array.isArray(data.features)
      ) {
        throw new Error("The real drain data is not a valid GeoJSON FeatureCollection.");
      }
      setRealDrains(data);
    } catch (err) {
      console.error("Real drain loading error:", err);
      setDrainError(err.message || "Could not load real drain data.");
    }
  }
  async function loadPriorityMap() {
    setPriorityError("");
    try {
      const response = await fetch(PRIORITY_MAP_URL);
      if (!response.ok) {
        throw new Error(`Priority map returned HTTP ${response.status}.`);
      }
      const data = await response.json();
      if (data.type !== "FeatureCollection" || !Array.isArray(data.features)) {
        throw new Error("Priority map is not a valid GeoJSON FeatureCollection.");
      }
      setPriorityMap(data);
    } catch (err) {
      console.error("Priority map loading error:", err);
      setPriorityError(err.message || "Could not load the drain priority map.");
    }
  }
  async function loadCandidateConnections() {
    setConnectionError("");
    try {
      const response = await fetch(CONNECTIONS_URL);
      if (!response.ok) {
        throw new Error(
          `Candidate connection file returned HTTP ${response.status}.`
        );
      }
      const data = await response.json();
      if (
        data.type !== "FeatureCollection" ||
        !Array.isArray(data.features)
      ) {
        throw new Error("Candidate connections are not a valid GeoJSON FeatureCollection.");
      }
      setCandidateConnections(data);
    } catch (err) {
      console.error("Candidate connection loading error:", err);
      setConnectionError(
        err.message ||
          "Could not load candidate connections. Check the frontend public folder."
      );
    }
  }
  useEffect(() => {
    loadDashboard("moderate");
    loadRealDrains();
    loadCandidateConnections();
    loadPriorityMap();
    loadFieldObservations();
  }, []);
  const ranked = useMemo(
    () =>
      [...hotspots].sort(
        (a, b) => b.priority_score - a.priority_score
      ),
    [hotspots]
  );
  const drainFeatures = realDrains?.features ?? [];
  const filteredDrains = useMemo(() => {
    const search = drainSearch.trim().toLowerCase();
    if (!search) return drainFeatures;
    return drainFeatures.filter((feature) => {
      const p = feature.properties ?? {};
      return [
        p.objectid,
        p.zone,
        p.ward,
        p.location,
        p.drain_type,
        p.water_flow,
        p.status,
        p.obstacles,
      ].some((value) =>
        String(value ?? "").toLowerCase().includes(search)
      );
    });
  }, [drainFeatures, drainSearch]);
  const totalDrainLengthKm = drainFeatures.reduce((sum, feature) => {
    const value = feature.properties?.dlen_km;
    const length = Number(value);
    return value !== null &&
      value !== undefined &&
      value !== "" &&
      Number.isFinite(length)
      ? sum + length
      : sum;
  }, 0);
  const reportedFlowCount = drainFeatures.filter(
    (feature) =>
      String(feature.properties?.water_flow ?? "")
        .trim()
        .toLowerCase() === "yes"
  ).length;
  function selectDrain(feature) {
    const p = feature?.properties ?? {};
    setSelectedDrain({
      ...p,
      geometryType: feature?.geometry?.type ?? "Unknown",
    });
  }
  const realDrainStyle = () => ({
    color: "#9635a3",
    weight: 4,
    opacity: 0.9,
  });
  const connectionStyle = () => ({
    color: "#f28c28",
    weight: 3,
    opacity: 0.95,
    dashArray: "5 7",
  });
  const priorityDrainStyle = (feature) => {
    const priority = String(feature?.properties?.review_priority ?? "");
    if (priority === "HIGH_REVIEW_PRIORITY") {
      return { color: "#dc2626", weight: 7, opacity: 1 };
    }
    if (priority === "MEDIUM_REVIEW_PRIORITY") {
      return { color: "#d97706", weight: 6, opacity: 0.95 };
    }
    if (priority === "LOW_REVIEW_PRIORITY") {
      return { color: "#2563eb", weight: 4, opacity: 0.85 };
    }
    return { color: "#94a3b8", weight: 2, opacity: 0.45 };
  };
  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-mark">PL</div>
        <div className="brand-copy">
          <div className="eyebrow">ENVIRONMENTAL INTELLIGENCE</div>
          <h1>Plastic Leakage Prevention</h1>
        </div>
        <div className="status-pill">
          <span />
          API dashboard
        </div>
      </header>
      <section className="intro">
        <div>
          <p className="eyebrow">DRAINAGE NETWORK ANALYTICS</p>
          <h2>Explore drains and inspect possible connections.</h2>
          <p className="intro-text">
            Review GCC Ward 178 drain geometry, attributes, and
            unverified endpoint connection candidates.
          </p>
        </div>
        <label className="scenario-control">
          <span>Demo rainfall scenario</span>
          <select
            value={rainfall}
            onChange={(event) => {
              const next = event.target.value;
              setRainfall(next);
              loadDashboard(next);
            }}
          >
            <option value="light">Light rainfall</option>
            <option value="moderate">Moderate rainfall</option>
            <option value="heavy">Heavy rainfall</option>
          </select>
        </label>
      </section>
      {error && <div className="error-banner">{error}</div>}
      {drainError && <div className="error-banner">{drainError}</div>}
      {connectionError && (
        <div className="error-banner">
          Candidate connections: {connectionError}
        </div>
      )}
      {priorityError && (
        <div className="error-banner">
          Drain review-priority layer: {priorityError}
        </div>
      )}
            <section className="stats-grid">
        <article className="stat-card">
          <span className="stat-label">Real drain features</span>
          <strong>{realDrains ? drainFeatures.length : "—"}</strong>
          <span className="stat-foot">GCC Ward 178 GeoJSON records</span>
        </article>
        <article className="stat-card">
          <span className="stat-label">Connection candidates</span>
          <strong>
            {candidateConnections
              ? candidateConnections.features.length
              : "—"}
          </strong>
          <span className="stat-foot">Unverified geometric candidates</span>
        </article>
        <article className="stat-card">
          <span className="stat-label">Field observations</span>
          <strong>
            {observationsLoading ? "…" : fieldObservations.length}
          </strong>
          <span className="stat-foot">
            {verifiedObservationCount} verified ·{" "}
            {fieldObservations.length - verifiedObservationCount} unverified
          </span>
        </article>
        <article className="stat-card">
          <span className="stat-label">Reported total length</span>
          <strong>{totalDrainLengthKm.toFixed(2)} km</strong>
          <span className="stat-foot">Sum of supplied drain lengths</span>
        </article>
        <article className="stat-card">
          <span className="stat-label">API status</span>
          <strong className={error ? "bad-status" : loading ? "" : "good-status"}>
            {error ? "Offline" : loading ? "Loading" : "Connected"}
          </strong>
          <span className="stat-foot">Local FastAPI service</span>
        </article>
      </section>
      <section className="content-grid">
        <article className="panel map-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">SPATIAL VIEW</p>
              <h3>Ward 178 stormwater drains</h3>
            </div>
            <span className="demo-tag">
              {realDrains ? "GCC DRAIN GEOMETRY" : "LOADING REAL DATA"}
            </span>
          </div>
          <div className="map-wrap">
            <MapContainer
              center={[12.9775, 80.232]}
              zoom={15}
              scrollWheelZoom={true}
              className="drain-map"
            >
              <TileLayer
                attribution='&copy; <a href="https://www\\.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {/* Real GCC drain geometry: purple solid lines. */}
              {realDrains && (
                <>
                  <GeoJSON
                    key="gcc-ward178-drains"
                    data={realDrains}
                    style={realDrainStyle}
                    onEachFeature={(feature, layer) => {
                      const p = feature.properties ?? {};
                      layer.bindPopup(`
                        <strong>GCC Stormwater Drain</strong><br/>
                        ID: ${p.objectid ?? "Unknown"}<br/>
                        Ward: ${p.ward ?? "Unknown"}<br/>
                        Zone: ${p.zone ?? "Unknown"}<br/>
                        Location: ${p.location ?? "Unknown"}<br/>
                        Type: ${p.drain_type ?? "Unknown"}<br/>
                        Reported flow: ${p.water_flow ?? "Unknown"}<br/>
                        Status: ${p.status ?? "Unknown"}<br/>
                        Length: ${p.dlen_km ?? "Unknown"} km
                      `);
                      layer.on("click", () => selectDrain(feature));
                    }}
                  />
                  <FitDrainBounds data={priorityMap || realDrains} />
                </>
              )}
              {/* Drain review-priority layer: based on geometric candidate links only. */}
              {showPriorityMap && priorityMap && (
                <GeoJSON
                  key="drain-review-priority"
                  data={priorityMap}
                  style={priorityDrainStyle}
                  onEachFeature={(feature, layer) => {
                    const p = feature.properties ?? {};
                    layer.bindPopup(`
                      <strong>Drain connection-review priority</strong><br/>
                      Drain ID: ${p.objectid ?? "Unknown"}<br/>
                      Review rank: ${p.review_rank ?? "—"}<br/>
                      Review priority: ${p.review_priority ?? "Not ranked"}<br/>
                      Candidate links: ${p.candidate_degree ?? 0}<br/>
                      Coincident endpoints: ${p.coincident_links ?? 0}<br/>
                      Nearby endpoints: ${p.nearby_links ?? 0}<br/>
                      Connection status: ${p.connection_status ?? "UNVERIFIED_CANDIDATE"}<br/>
                      Flow direction: ${p.flow_direction ?? "UNKNOWN"}<br/>
                      <em>Geometry-based review aid only; not verified hydraulic connectivity or flood risk.</em>
                    `);
                  }}
                />
              )}
              {selectedCandidate && <FlyToCandidate feature={selectedCandidate} />}
              {/* Candidate endpoint connectors: orange dashed lines.
                  Coincident endpoints are displayed as orange circles because
                  a zero-length LineString cannot be seen on the map. */}
              {showCandidateConnections && candidateConnections && (
                <>
                  <GeoJSON
                    key="candidate-connections-lines"
                    data={{
                      ...candidateConnections,
                      features: candidateConnections.features.filter((feature) => {
                        const coords = feature.geometry?.coordinates;
                        if (feature.geometry?.type !== "LineString" || !coords || coords.length < 2) return false;
                        const first = coords[0];
                        const last = coords[coords.length - 1];
                        return first[0] !== last[0] || first[1] !== last[1];
                      }),
                    }}
                    style={connectionStyle}
                    onEachFeature={(feature, layer) => {
                      const p = feature.properties ?? {};
                      layer.bindPopup(`
                        <strong>Unverified connection candidate</strong><br/>
                        Candidate: ${p.candidate_id ?? "Unknown"}<br/>
                        Drain A: ${p.drain_a ?? "Unknown"}<br/>
                        Drain B: ${p.drain_b ?? "Unknown"}<br/>
                        Endpoint distance: ${p.distance_m ?? "Unknown"} m<br/>
                        Status: ${p.connection_status ?? "Unverified"}<br/>
                        Flow direction: ${p.flow_direction ?? "Unknown"}
                      `);
                    }}
                  />
                  {candidateConnections.features
                    .filter((feature) => {
                      const coords = feature.geometry?.coordinates;
                      if (feature.geometry?.type !== "LineString" || !coords || coords.length < 2) return false;
                      const first = coords[0];
                      const last = coords[coords.length - 1];
                      return first[0] === last[0] && first[1] === last[1];
                    })
                    .map((feature) => {
                      const coords = feature.geometry.coordinates;
                      const p = feature.properties ?? {};
                      return (
                        <CircleMarker
                          key={`candidate-point-${p.candidate_id ?? `${p.drain_a}-${p.drain_b}`}`}
                          center={[coords[0][1], coords[0][0]]}
                          radius={6}
                          pathOptions={{
                            color: "#f28c28",
                            weight: 2,
                            fillColor: "#fff7ed",
                            fillOpacity: 1,
                          }}
                          eventHandlers={{
                            click: (event) => {
                              L.popup()
                                .setLatLng(event.latlng)
                                .setContent(`
                                  <strong>Unverified connection candidate</strong><br/>
                                  Candidate: ${p.candidate_id ?? "Unknown"}<br/>
                                  Drain A: ${p.drain_a ?? "Unknown"}<br/>
                                  Drain B: ${p.drain_b ?? "Unknown"}<br/>
                                  Endpoint distance: ${p.distance_m ?? "Unknown"} m<br/>
                                  Status: ${p.connection_status ?? "Unverified"}<br/>
                                  Flow direction: ${p.flow_direction ?? "Unknown"}
                                `)
                                .openOn(event.target._map);
                            },
                          }}
                        />
                      );
                    })}
                </>
              )}
              {/* Fictional demonstration network only. */}
              {network.edges.map((edge) => {
                const start = POSITIONS[edge.from];
                const end = POSITIONS[edge.to];
                if (!start || !end) return null;
                return (
                  <Polyline
                    key={`${edge.from}-${edge.to}`}
                    positions={[start, end]}
                    pathOptions={{
                      color: "#317f70",
                      weight: 3,
                      opacity: 0.45,
                      dashArray: "6 6",
                    }}
                  />
                );
              })}
              {network.nodes.map((node) => {
                const position = POSITIONS[node.id];
                if (!position) return null;
                const result = ranked.find((item) => item.id === node.id);
                const score = result?.priority_score ?? 20;
                return (
                  <CircleMarker
                    key={node.id}
                    center={position}
                    radius={result ? 8 : 5}
                    pathOptions={{
                      color: "#ffffff",
                      weight: 2,
                      fillColor: scoreColor(score),
                      fillOpacity: 0.85,
                    }}
                  >
                    <Tooltip>
                      <strong>{node.name}</strong>
                      <br />
                      {result
                        ? `Demo priority score: ${result.priority_score}`
                        : "Fictional demo location"}
                    </Tooltip>
                  </CircleMarker>
                );
              })}
            </MapContainer>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", marginTop: 12 }}>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 14, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={showPriorityMap}
                onChange={(event) => setShowPriorityMap(event.target.checked)}
              />
              Show drain review-priority layer
            </label>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 14, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={showCandidateConnections}
                onChange={(event) => setShowCandidateConnections(event.target.checked)}
              />
              Show candidate connections ({candidateConnections?.features?.length ?? 0})
            </label>
            <span style={{ fontSize: 12, color: "#64748b" }}>All candidates remain unverified</span>
          </div>
          <div className="map-legend">
            <span><i className="legend-line" /> GCC drain geometry</span>
            <span style={{ color: "#dc2626" }}>━ High review priority</span>
            <span style={{ color: "#d97706" }}>━ Medium review priority</span>
            <span style={{ color: "#2563eb" }}>━ Lower review priority</span>
            <span><i className="legend-connection" /> Candidate connection (unverified)</span>
            <span><i className="legend-dot high" /> High demo priority</span>
            <span><i className="legend-dot medium" /> Medium demo priority</span>
            <span><i className="legend-dot low" /> Lower demo priority</span>
          </div>
          <p className="map-note">
            Purple lines are GCC drain geometry. Orange dashed connectors
            represent endpoint proximity only. Green dashed lines and
            colored circles are fictional demo features. These layers do
            not establish verified hydraulic connectivity or flow direction.
          </p>
        </article>
        <article className="panel ranking-panel">

          <div className="panel-heading">

            <div>

              <p className="eyebrow">GCC DRAIN REVIEW</p>

              <h3>Drain connection-review priority</h3>

            </div>

            <span className="count-badge">

              {priorityMap?.features?.length ?? 0} drains

            </span>

          </div>
          {!priorityMap ? (

            <div className="empty-state">

              {priorityError || "Loading drain review-priority data…"}

            </div>

          ) : (

            <>

              <p className="panel-footnote">

                Sorted using candidate-link counts from geometric endpoint proximity.

                This is a review queue, not a measured pollution or flood-risk ranking.

              </p>

              <div className="ranking-list">

                {[...priorityMap.features]

                  .sort((a, b) =>

                    Number(a.properties?.review_rank ?? 9999) -

                    Number(b.properties?.review_rank ?? 9999)

                  )

                  .slice(0, 10)

                  .map((feature, index) => {

                    const p = feature.properties ?? {};

                    const color =

                      p.review_priority === "HIGH_REVIEW_PRIORITY"

                        ? "#dc2626"

                        : p.review_priority === "MEDIUM_REVIEW_PRIORITY"

                        ? "#d97706"

                        : "#2563eb";

                    return (

                      <div className="rank-item" key={p.objectid ?? index}>

                        <div className="rank-number">{p.review_rank ?? index + 1}</div>

                        <div className="rank-details">

                          <div className="rank-title-row">

                            <strong>Drain ID {p.objectid ?? "Unknown"}</strong>

                            <span className="score" style={{ color }}>

                              {String(p.review_priority ?? "NOT RANKED").replaceAll("_", " ")}

                            </span>

                          </div>

                          <div className="rank-meta">

                            <span>{p.candidate_degree ?? 0} candidate links</span>

                            <span>{p.coincident_links ?? 0} coincident endpoints</span>

                          </div>

                          <div className="rank-foot">

                            <span>{p.nearby_links ?? 0} nearby endpoints</span>

                            <span>Hydraulic connection unverified</span>

                          </div>

                        </div>

                      </div>

                    );

                  })}

              </div>

            </>

          )}

          <p className="panel-footnote">

            Candidate geometry does not establish physical connectivity, flow direction,

            leakage quantity, or flood risk.

          </p>

        </article>
      </section>
      {/* Candidate connection inventory */}
      <section className="panel drain-inventory" style={{ marginTop: 20 }}>
        <div className="panel-heading">
          <div>
            <p className="eyebrow">GEOMETRIC CANDIDATES</p>
            <h3>Candidate connections</h3>
          </div>
          <span className="count-badge">{candidateConnections?.features?.length ?? 0} candidates</span>
        </div>
        <p className="panel-footnote">
          Select a row to zoom to its approximate location. These are endpoint-proximity candidates, not confirmed physical or hydraulic connections.
        </p>
        {!candidateConnections ? (
          <div className="empty-state">Loading candidate connections…</div>
        ) : (
          <div className="inventory-table-wrap">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Drain A</th>
                  <th>Drain B</th>
                  <th>Endpoint A</th>
                  <th>Endpoint B</th>
                  <th>Distance (m)</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {candidateConnections.features.map((feature, index) => {
                  const p = feature.properties ?? {};
                  const selected = selectedCandidate?.properties?.candidate_id === p.candidate_id;
                  return (
                    <tr
                      key={p.candidate_id ?? `${p.drain_a}-${p.drain_b}-${index}`}
                      className={selected ? "selected-row" : ""}
                      onClick={() => {
                        setSelectedCandidate(feature);
                        setShowCandidateConnections(true);
                      }}
                      tabIndex={0}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          setSelectedCandidate(feature);
                          setShowCandidateConnections(true);
                        }
                      }}
                      style={{ cursor: "pointer" }}
                    >
                      <td>{p.candidate_id ?? index + 1}</td>
                      <td>{p.drain_a ?? "—"}</td>
                      <td>{p.drain_b ?? "—"}</td>
                      <td>{p.endpoint_a ?? "—"}</td>
                      <td>{p.endpoint_b ?? "—"}</td>
                      <td>{Number.isFinite(Number(p.distance_m)) ? Number(p.distance_m).toFixed(3) : "—"}</td>
                      <td>{p.connection_status ?? "UNVERIFIED_CANDIDATE"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {/* Real drain inventory */}
      <section className="panel drain-inventory">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">GCC WARD 178 · ZONE N13</p>
            <h3>Real drain inventory</h3>
          </div>
          <span className="count-badge">
            {filteredDrains.length} of {drainFeatures.length} records
          </span>
        </div>
        <div className="drain-summary">
          <article className="stat-card">
            <span className="stat-label">Drain features</span>
            <strong>{drainFeatures.length}</strong>
          </article>
          <article className="stat-card">
            <span className="stat-label">Reported total length</span>
            <strong>{totalDrainLengthKm.toFixed(2)} km</strong>
          </article>
          <article className="stat-card">
            <span className="stat-label">Reported flow: Yes</span>
            <strong>{reportedFlowCount}</strong>
          </article>
        </div>
        <label className="drain-search">
          <span>Search drains</span>
          <input
            type="search"
            value={drainSearch}
            onChange={(event) => setDrainSearch(event.target.value)}
            placeholder="Search ID, location, type, status..."
          />
        </label>
        {selectedDrain && (
          <div className="selected-drain">
            <div className="selected-drain-heading">
              <h4>Selected drain · ID {selectedDrain.objectid}</h4>
              <button
                type="button"
                className="secondary-button"
                onClick={() => setSelectedDrain(null)}
              >
                Clear selection
              </button>
            </div>
            <div className="selected-drain-grid">
              <p><strong>Ward:</strong> {selectedDrain.ward ?? "—"}</p>
              <p><strong>Zone:</strong> {selectedDrain.zone ?? "—"}</p>
              <p><strong>Location:</strong> {selectedDrain.location ?? "—"}</p>
              <p><strong>Type:</strong> {selectedDrain.drain_type ?? "—"}</p>
              <p><strong>Reported flow:</strong> {selectedDrain.water_flow ?? "—"}</p>
              <p><strong>Status:</strong> {selectedDrain.status ?? "—"}</p>
              <p>
                <strong>Length:</strong>{" "}
                {selectedDrain.dlen_km != null
                  ? `${selectedDrain.dlen_km} km`
                  : "—"}
              </p>
              <p><strong>Geometry:</strong> {selectedDrain.geometryType ?? "—"}</p>
            </div>
          </div>
        )}
        <div className="inventory-table-wrap">
          <table className="inventory-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Location</th>
                <th>Type</th>
                <th>Reported flow</th>
                <th>Status</th>
                <th>Length (km)</th>
              </tr>
            </thead>
            <tbody>
              {filteredDrains.map((feature) => {
                const p = feature.properties ?? {};
                const isSelected =
                  String(selectedDrain?.objectid) === String(p.objectid);
                return (
                  <tr
                    key={p.objectid}
                    className={isSelected ? "selected-row" : ""}
                    onClick={() => selectDrain(feature)}
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") selectDrain(feature);
                    }}
                  >
                    <td>{p.objectid ?? "—"}</td>
                    <td>{p.location ?? "—"}</td>
                    <td>{p.drain_type ?? "—"}</td>
                    <td>{p.water_flow ?? "—"}</td>
                    <td>{p.status ?? "—"}</td>
                    <td>{formatLength(p.dlen_km)}</td>
                  </tr>
                );
              })}
              {filteredDrains.length === 0 && (
                <tr>
                  <td colSpan={6} className="no-results">
                    No matching drain records found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <p className="panel-footnote">
          Inventory attributes are shown as supplied by the GCC GIS service.
          Reported flow and status are not independent field verification.
        </p>
      </section>
      {/* Field observation inventory */}
      <section className="panel drain-inventory" style={{ marginTop: 20 }}>
        <div className="panel-heading">
          <div>
            <p className="eyebrow">FIELD INSPECTION DATA</p>
            <h3>Drain observations</h3>
          </div>
          <span className="count-badge">
            {fieldObservations.length} records
          </span>
        </div>

        <p className="panel-footnote">
          Observation records come from the field-observation CSV. Blank values
          mean not recorded or not assessed, not that a drain is clear.
        </p>

        <input
          type="search"
          value={observationSearch}
          onChange={(event) => setObservationSearch(event.target.value)}
          placeholder="Search by drain ID..."
          aria-label="Search field observations by drain ID"
          style={{
            width: "100%",
            maxWidth: 360,
            padding: "10px 12px",
            marginBottom: 16,
            border: "1px solid #cbd5e1",
            borderRadius: 8,
            boxSizing: "border-box",
          }}
        />

        {observationsLoading ? (
          <div className="empty-state">Loading field observations…</div>
        ) : observationError ? (
          <div className="error-banner">
            {observationError}
            <button
              type="button"
              className="secondary-button"
              onClick={loadFieldObservations}
              style={{ marginLeft: 12 }}
            >
              Retry
            </button>
          </div>
        ) : (
          <div className="inventory-table-wrap">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>Drain ID</th>
                  <th>Observation date</th>
                  <th>Plastic accumulation</th>
                  <th>Blockage</th>
                  <th>Rainfall</th>
                  <th>Verification</th>
                  <th>Inspection notes</th>
                </tr>
              </thead>
              <tbody>
                {filteredObservations.map((item) => {
                  const verified =
                    String(item.verification_status ?? "").toUpperCase() ===
                    "FIELD_VERIFIED";

                  return (
                    <tr key={item.drain_id}>
                      <td><strong>{item.drain_id}</strong></td>
                      <td>{item.observation_date || "Not recorded"}</td>
                      <td>{item.plastic_accumulation || "Not assessed"}</td>
                      <td>{item.blockage_observed || "Not assessed"}</td>
                      <td>{item.rainfall_observed || "Not recorded"}</td>
                      <td>
                        <span
                          className="score"
                          style={{ color: verified ? "#15803d" : "#b45309" }}
                        >
                          {verified ? "FIELD VERIFIED" : "UNVERIFIED"}
                        </span>
                      </td>
                      <td>{item.inspection_notes || "—"}</td>
                    </tr>
                  );
                })}
                {filteredObservations.length === 0 && (
                  <tr>
                    <td colSpan={7}>No matching drain records found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
        <p className="panel-footnote">
          This table displays entered field records only. Missing values do not
          indicate absence of plastic or blockage. Synthetic demo hotspot scores
          are separate from these observations.
        </p>
      </section>

      <footer className="footer">
        <span>Plastic Leakage Intelligence · Prototype v0.3</span>
        <button
          type="button"
          className="refresh-button"
          onClick={() => {
            loadDashboard(rainfall);
            loadRealDrains();
            loadCandidateConnections();
              loadPriorityMap();
            loadFieldObservations();
          }}
        >
          ↻ Refresh results
        </button>
      </footer>
    </main>
  );
}
