/**
 * AegisAI Digital Twin Live Map Component
 * Built on React-Leaflet with dynamic layer toggles, smooth entity rendering,
 * real-time road congestion/blockades, building damage, and citizen agent overlays.
 */

import React, { useState, useMemo } from "react";
import {
    MapContainer,
    TileLayer,
    Marker,
    Popup,
    Polyline,
    Circle,
    CircleMarker,
    useMap
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix default leaflet icons
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
    iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
    shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// Map effects component to handle flyToBounds
function MapEffects({ activeRoute }) {
    const map = useMap();
    
    React.useEffect(() => {
        if (activeRoute && activeRoute.geometry && activeRoute.geometry.coordinates.length > 0) {
            const positions = activeRoute.geometry.coordinates.map(([lon, lat]) => [lat, lon]);
            const bounds = L.latLngBounds(positions);
            map.flyToBounds(bounds, { padding: [50, 50], duration: 1.5 });
        }
    }, [activeRoute, map]);
    
    return null;
}

// Custom DivIcons for high visual appeal
const createCustomIcon = (emoji, bgClass = "bg-default") => {
    return L.divIcon({
        className: "custom-leaflet-marker",
        html: `<div class="marker-pin ${bgClass}"><span class="marker-emoji">${emoji}</span></div>`,
        iconSize: [34, 34],
        iconAnchor: [17, 34],
        popupAnchor: [0, -34],
    });
};

const createCitizenDot = (status) => {
    let color = "#22c55e"; // SAFE
    if (status === "ENDANGERED") color = "#eab308";
    if (status === "EVACUATING") color = "#f97316";
    if (status === "INJURED") color = "#ef4444";
    if (status === "RESCUED") color = "#38bdf8";

    return L.divIcon({
        className: "citizen-dot-marker",
        html: `<div style="width: 8px; height: 8px; border-radius: 50%; background: ${color}; border: 1px solid white; box-shadow: 0 0 4px ${color};"></div>`,
        iconSize: [8, 8],
        iconAnchor: [4, 4],
    });
};

const icons = {
    disaster: (severity) => {
        const bg = severity === "CRITICAL" ? "bg-critical" : severity === "HIGH" ? "bg-danger" : "bg-warning";
        return createCustomIcon("🚨", bg);
    },
    hospital: createCustomIcon("🏥", "bg-hospital"),
    shelter: createCustomIcon("⛺", "bg-shelter"),
    ambulance: createCustomIcon("🚑", "bg-rescue"),
    fireTruck: createCustomIcon("🚒", "bg-fire"),
    police: createCustomIcon("🚓", "bg-police"),
    rescue: createCustomIcon("🛟", "bg-rescue"),
    buildingNormal: createCustomIcon("🏢", "bg-building"),
    buildingDamaged: createCustomIcon("🏚️", "bg-damaged"),
};

function RouteLine({ geometry, color = "#2563eb" }) {
    if (!geometry || !geometry.coordinates || geometry.coordinates.length === 0) {
        return null;
    }

    const positions = geometry.coordinates.map(([longitude, latitude]) => [
        latitude,
        longitude
    ]);

    return (
        <Polyline
            positions={positions}
            pathOptions={{
                color: color,
                weight: 6,
                opacity: 0.9,
                dashArray: null
            }}
        />
    );
}

export function DisasterMap({
    disasters = [],
    hospitals = [],
    shelters = [],
    rescueTeams = [],
    assignments = [],
    activeRoute = null,
    buildings = [],
    roads = [],
    citizens = [],
    forecastData = null,
    onSelectIncident,
    onSelectResource
}) {
    const defaultPosition = [30.7333, 76.7794]; // Chandigarh Center

    // Layer Visibility Toggles
    const [layers, setLayers] = useState({
        disasters: true,
        zones: true,
        forecasts: true,
        rescueTeams: true,
        hospitals: true,
        shelters: true,
        buildings: true,
        roads: true,
        citizens: true,
        satellite: false
    });

    const toggleLayer = (layerName) => {
        setLayers((prev) => ({ ...prev, [layerName]: !prev[layerName] }));
    };

    const getDisasterZoneColor = (severity) => {
        switch (severity) {
            case "CRITICAL": return "#dc2626";
            case "HIGH": return "#ea580c";
            case "MEDIUM": return "#eab308";
            default: return "#3b82f6";
        }
    };

    return (
        <div className="disaster-map-container" style={{ position: "relative", height: "100%", width: "100%" }}>
            {/* MAP LAYER CONTROLS FLOATING BAR */}
            <div className="map-layer-toolbar">
                <div className="layer-bar-title">🛰️ LAYERS</div>
                <button
                    className={`layer-btn ${layers.disasters ? "active" : ""}`}
                    onClick={() => toggleLayer("disasters")}
                >
                    🚨 Incidents ({disasters.length})
                </button>
                <button
                    className={`layer-btn ${layers.rescueTeams ? "active" : ""}`}
                    onClick={() => toggleLayer("rescueTeams")}
                >
                    🚑 Fleet ({rescueTeams.length})
                </button>
                <button
                    className={`layer-btn ${layers.hospitals ? "active" : ""}`}
                    onClick={() => toggleLayer("hospitals")}
                >
                    🏥 Hospitals ({hospitals.length})
                </button>
                <button
                    className={`layer-btn ${layers.shelters ? "active" : ""}`}
                    onClick={() => toggleLayer("shelters")}
                >
                    ⛺ Shelters ({shelters.length})
                </button>
                <button
                    className={`layer-btn ${layers.buildings ? "active" : ""}`}
                    onClick={() => toggleLayer("buildings")}
                >
                    🏢 Buildings ({buildings.length})
                </button>
                <button
                    className={`layer-btn ${layers.roads ? "active" : ""}`}
                    onClick={() => toggleLayer("roads")}
                >
                    🛣️ Roads ({roads.length})
                </button>
                <button
                    className={`layer-btn ${layers.citizens ? "active" : ""}`}
                    onClick={() => toggleLayer("citizens")}
                >
                    👥 Agents ({citizens.length})
                </button>
                <button
                    className={`layer-btn ${layers.forecasts ? "active" : ""}`}
                    onClick={() => toggleLayer("forecasts")}
                >
                    🔮 Forecast Envelopes
                </button>
                <button
                    className={`layer-btn ${layers.satellite ? "active" : ""}`}
                    onClick={() => toggleLayer("satellite")}
                >
                    🛰️ Satellite
                </button>
            </div>

            <MapContainer
                center={defaultPosition}
                zoom={12}
                style={{ height: "100%", width: "100%" }}
                preferCanvas={true} // ENABLES CANVAS RENDERING FOR VECTOR LAYERS
            >
                <MapEffects activeRoute={activeRoute} />
                <TileLayer
                    attribution="&copy; OpenStreetMap contributors"
                    url={
                        layers.satellite
                            ? "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                            : "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    }
                />

                {/* ================================================= */}
                {/* ACTIVE DISPATCH ROUTE POLYLINE */}
                {/* ================================================= */}
                {activeRoute && <RouteLine geometry={activeRoute.geometry} color="#38bdf8" />}

                {/* ================================================= */}
                {/* ROAD NETWORK & TRAFFIC SEGMENTS */}
                {/* ================================================= */}
                {layers.roads && roads.map((road) => {
                    const isBlocked = road.is_blocked;
                    const isCongested = road.congestion_factor > 1.5;
                    const roadColor = isBlocked ? "#ef4444" : isCongested ? "#f59e0b" : "#64748b";

                    return (
                        <Polyline
                            key={`road-${road.id}`}
                            positions={[
                                [road.start_latitude, road.start_longitude],
                                [road.end_latitude, road.end_longitude]
                            ]}
                            pathOptions={{
                                color: roadColor,
                                weight: isBlocked ? 6 : isCongested ? 5 : 3,
                                dashArray: isBlocked ? "8, 8" : null,
                                opacity: 0.85
                            }}
                        >
                            <Popup>
                                <div className="map-popup-card">
                                    <h4>🛣️ {road.name}</h4>
                                    <p><strong>Length:</strong> {road.length_km} km</p>
                                    <p><strong>Congestion:</strong> {road.congestion_factor}x</p>
                                    <p><strong>Status:</strong> {isBlocked ? `⛔ BLOCKED (${road.blocked_reason || 'Hazard'})` : "🟢 PASSABLE"}</p>
                                </div>
                            </Popup>
                        </Polyline>
                    );
                })}

                {/* ================================================= */}
                {/* PREDICTIVE FORECAST ENVELOPES (+5m, +15m, +30m, +60m) */}
                {/* ================================================= */}
                {layers.forecasts && forecastData?.fire_spread && forecastData.fire_spread.map((fire) => (
                    <React.Fragment key={`forecast-fire-${fire.incident_id}`}>
                        {fire.zones && fire.zones.map((zone) => {
                            const horizonColor =
                                zone.horizon_minutes === 5 ? "#eab308" :
                                zone.horizon_minutes === 15 ? "#f97316" :
                                zone.horizon_minutes === 30 ? "#ef4444" : "#b91c1c";
                            const opacity = Math.max(0.08, 0.25 - (zone.horizon_minutes * 0.002));

                            return (
                                <Circle
                                    key={`fire-zone-${fire.incident_id}-${zone.horizon_minutes}`}
                                    center={[fire.center_latitude, fire.center_longitude]}
                                    radius={zone.radius_meters}
                                    pathOptions={{
                                        color: horizonColor,
                                        fillColor: horizonColor,
                                        fillOpacity: opacity,
                                        weight: 2,
                                        dashArray: "6, 6"
                                    }}
                                >
                                    <Popup>
                                        <div className="map-popup-card">
                                            <h4>🔥 Fire Spread Forecast (+{zone.horizon_minutes}m)</h4>
                                            <p><strong>Projected Radius:</strong> {(zone.radius_meters / 1000).toFixed(2)} km</p>
                                            <p><strong>Risk Level:</strong> <span className={`badge-mini ${zone.risk_level?.toLowerCase() || 'high'}`}>{zone.risk_level}</span></p>
                                            <p><strong>Population Impact:</strong> ~{zone.estimated_population_impact} citizens</p>
                                            <p><strong>Propagation Speed:</strong> {fire.spread_velocity_kmh} km/h (dir: {fire.spread_direction_degrees}°)</p>
                                            <p><strong>Source:</strong> SIMULATION + ML</p>
                                        </div>
                                    </Popup>
                                </Circle>
                            );
                        })}
                    </React.Fragment>
                ))}

                {/* ================================================= */}
                {/* DISASTER ZONES & RADIUS CIRCLES */}
                {/* ================================================= */}
                {layers.zones && disasters.map((disaster) => {
                    if (!disaster.affected_radius_meters && !disaster.latitude) return null;
                    const radius = disaster.affected_radius_meters || 1000;
                    const color = getDisasterZoneColor(disaster.severity);

                    return (
                        <Circle
                            key={`zone-${disaster.id}`}
                            center={[disaster.latitude, disaster.longitude]}
                            radius={radius}
                            pathOptions={{
                                color: color,
                                fillColor: color,
                                fillOpacity: 0.18,
                                weight: 2,
                                dashArray: "4, 4"
                            }}
                        />
                    );
                })}

                {/* ================================================= */}
                {/* DISASTERS / INCIDENTS (Canvas Layer via CircleMarker) */}
                {/* ================================================= */}
                {layers.disasters && disasters.map((disaster) => (
                    <CircleMarker
                        key={`disaster-${disaster.id}`}
                        center={[disaster.latitude, disaster.longitude]}
                        radius={12}
                        pathOptions={{
                            color: disaster.severity === 'CRITICAL' ? '#dc2626' : '#ea580c',
                            fillColor: disaster.severity === 'CRITICAL' ? '#dc2626' : '#ea580c',
                            fillOpacity: 0.9,
                            weight: 2
                        }}
                        eventHandlers={{
                            click: () => onSelectIncident && onSelectIncident(disaster)
                        }}
                    >
                        <Popup>
                            <div className="map-popup-card">
                                <h3>🚨 {disaster.title}</h3>
                                <p><strong>Type:</strong> {disaster.disaster_type}</p>
                                <p><strong>Severity:</strong> <span className={`badge-mini ${disaster.severity?.toLowerCase()}`}>{disaster.severity}</span></p>
                                <p><strong>Status:</strong> {disaster.status}</p>
                                {disaster.affected_radius_meters && (
                                    <p><strong>Radius:</strong> {(disaster.affected_radius_meters / 1000).toFixed(1)} km</p>
                                )}
                            </div>
                        </Popup>
                    </CircleMarker>
                ))}

                {/* ================================================= */}
                {/* BUILDINGS & INFRASTRUCTURE */}
                {/* ================================================= */}
                {layers.buildings && buildings.map((bldg) => {
                    const isDamaged = bldg.is_damaged || bldg.damage_percent > 15;
                    const icon = isDamaged ? icons.buildingDamaged : icons.buildingNormal;

                    return (
                        <Marker
                            key={`building-${bldg.id}`}
                            position={[bldg.latitude, bldg.longitude]}
                            icon={icon}
                        >
                            <Popup>
                                <div className="map-popup-card">
                                    <h4>🏢 {bldg.name}</h4>
                                    <p><strong>Type:</strong> {bldg.building_type}</p>
                                    <p><strong>Occupancy:</strong> {bldg.occupancy} / {bldg.capacity}</p>
                                    <p>
                                        <strong>Damage:</strong>{" "}
                                        <span className={isDamaged ? "text-danger" : "text-success"}>
                                            {bldg.damage_percent?.toFixed(0)}% {isDamaged ? "(DAMAGED)" : "(SECURE)"}
                                        </span>
                                    </p>
                                </div>
                            </Popup>
                        </Marker>
                    );
                })}

                {/* ================================================= */}
                {/* CITIZEN AGENTS OVERLAY (Canvas Layer via CircleMarker) */}
                {/* ================================================= */}
                {layers.citizens && citizens.map((citizen) => {
                    let color = "#22c55e"; // SAFE
                    if (citizen.status === "ENDANGERED") color = "#eab308";
                    if (citizen.status === "EVACUATING") color = "#f97316";
                    if (citizen.status === "INJURED") color = "#ef4444";
                    if (citizen.status === "RESCUED") color = "#38bdf8";

                    return (
                        <CircleMarker
                            key={`citizen-${citizen.id}`}
                            center={[citizen.latitude, citizen.longitude]}
                            radius={4}
                            pathOptions={{
                                color: "#ffffff",
                                fillColor: color,
                                fillOpacity: 1,
                                weight: 1
                            }}
                        >
                            <Popup>
                                <div className="map-popup-card" style={{ minWidth: 160 }}>
                                    <h4>👤 Citizen Agent #{citizen.id}</h4>
                                    <p><strong>Age:</strong> {citizen.age}</p>
                                    <p><strong>Status:</strong> {citizen.status}</p>
                                    {citizen.needs_medical && (
                                        <p><strong className="text-danger">⚠️ Medical Help Required</strong></p>
                                    )}
                                </div>
                            </Popup>
                        </CircleMarker>
                    );
                })}

                {/* ================================================= */}
                {/* HOSPITALS */}
                {/* ================================================= */}
                {layers.hospitals && hospitals.map((hospital) => {
                    const availableBeds = hospital.available_beds ?? hospital.total_beds ?? 0;
                    const totalBeds = hospital.total_beds ?? 100;
                    const bedPct = totalBeds > 0 ? Math.round(((totalBeds - availableBeds) / totalBeds) * 100) : 0;

                    return (
                        <Marker
                            key={`hospital-${hospital.id}`}
                            position={[hospital.latitude, hospital.longitude]}
                            icon={icons.hospital}
                        >
                            <Popup>
                                <div className="map-popup-card">
                                    <h3>🏥 {hospital.name}</h3>
                                    <p><strong>Available Beds:</strong> {availableBeds} / {totalBeds} ({100 - bedPct}% free)</p>
                                    <p><strong>ICU Capacity:</strong> {hospital.available_icu_beds ?? 8} beds</p>
                                    <p><strong>Operational:</strong> {hospital.is_operational ? "🟢 YES" : "🔴 NO"}</p>
                                    <p><strong>Phone:</strong> {hospital.phone || "+91-172-270000"}</p>
                                </div>
                            </Popup>
                        </Marker>
                    );
                })}

                {/* ================================================= */}
                {/* SHELTERS */}
                {/* ================================================= */}
                {layers.shelters && shelters.map((shelter) => (
                    <Marker
                        key={`shelter-${shelter.id}`}
                        position={[shelter.latitude, shelter.longitude]}
                        icon={icons.shelter}
                    >
                        <Popup>
                            <div className="map-popup-card">
                                <h3>⛺ {shelter.name}</h3>
                                <p><strong>Capacity:</strong> {shelter.current_occupancy || 0} / {shelter.capacity} citizens</p>
                                <p><strong>Pet Friendly:</strong> {shelter.pet_friendly ? "🐾 YES" : "❌ NO"}</p>
                                <p><strong>Status:</strong> {shelter.is_active ? "🟢 OPEN" : "🔴 CLOSED"}</p>
                            </div>
                        </Popup>
                    </Marker>
                ))}

                {/* ================================================= */}
                {/* RESCUE TEAMS & FLEET (Canvas Layer via CircleMarker) */}
                {/* ================================================= */}
                {layers.rescueTeams && rescueTeams.map((team) => {
                    const vType = team.vehicle_type?.toUpperCase() || "";
                    let color = "#3b82f6"; // Default rescue
                    if (vType.includes("AMBULANCE") || vType.includes("MEDIC")) color = "#ef4444";
                    else if (vType.includes("FIRE") || vType.includes("HAZMAT")) color = "#f97316";
                    else if (vType.includes("POLICE")) color = "#1d4ed8";

                    return (
                        <CircleMarker
                            key={`team-${team.id}`}
                            center={[team.latitude, team.longitude]}
                            radius={10}
                            pathOptions={{
                                color: '#ffffff',
                                fillColor: color,
                                fillOpacity: 0.9,
                                weight: 2
                            }}
                            eventHandlers={{
                                click: () => onSelectResource && onSelectResource(team)
                            }}
                        >
                            <Popup>
                                <div className="map-popup-card">
                                    <h3>🚑 {team.name}</h3>
                                    <p><strong>Vehicle:</strong> {team.vehicle_type}</p>
                                    <p><strong>Crew:</strong> {team.member_count} members</p>
                                    <p><strong>Status:</strong> <span className={`badge-mini ${team.status?.toLowerCase()}`}>{team.status}</span></p>
                                </div>
                            </Popup>
                        </CircleMarker>
                    );
                })}
            </MapContainer>
        </div>
    );
}

export default DisasterMap;