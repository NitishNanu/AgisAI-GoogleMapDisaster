/**
 * AegisAI Dashboard — Sidebar Layout
 * Full redesign: Left sidebar navigation + map + right content panel
 */

import React, { useCallback, useEffect, useState } from "react";

import Sidebar from "../components/Layout/Sidebar";
import AuthModal from "../components/Auth/AuthModal";
import DisasterMap from "../components/Map/DisasterMap";
import MissionControl from "../components/MissionControl";
import SimulationControls from "../components/Simulation/SimulationControls";
import SimulationKPIs from "../components/Simulation/SimulationKPIs";
import SimulationTimeline from "../components/Simulation/SimulationTimeline";
import LiveEventsFeed from "../components/Simulation/LiveEventsFeed";
import WhatIfModal from "../components/Simulation/WhatIfModal";
import SpawnIncidentModal from "../components/Simulation/SpawnIncidentModal";
import ScenarioDesigner from "../components/Scenario/ScenarioDesigner";
import ScenarioListModal from "../components/Scenario/ScenarioListModal";
import IncidentActionPlanModal from "../components/Disaster/IncidentActionPlanModal";
import PredictiveDashboard from "../components/Prediction/PredictiveDashboard";
import AnalyticsDashboard from "../components/Analytics/AnalyticsDashboard";
import ResourcesPanel from "../components/Resources/ResourcesPanel";

import { useAuth } from "../context/AuthContext";
import wsManager from "../services/websocketManager";
import simulationService from "../services/simulationService";
import predictionService from "../services/predictionService";
import incidentService from "../services/incidentService";

import {
    getDisasters,
    getHospitals,
    getShelters,
    getRescueTeams,
    getRecommendedRescueTeams,
    getAssignments,
    createAssignment,
    getMissions,
    updateAssignmentStatus,
} from "../services/disasterService";

function Dashboard() {
    const { token, isAuthenticated, user, hasRole } = useAuth();

    // ── MODAL STATES ──────────────────────────────────────────────────────
    const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
    const [isWhatIfOpen, setIsWhatIfOpen] = useState(false);
    const [isSpawnModalOpen, setIsSpawnModalOpen] = useState(false);
    const [isLibraryOpen, setIsLibraryOpen] = useState(false);
    const [isIAPModalOpen, setIsIAPModalOpen] = useState(false);
    const [activeIAP, setActiveIAP] = useState(null);
    const [loadingIAP, setLoadingIAP] = useState(false);

    // ── CORE DATA ─────────────────────────────────────────────────────────
    const [disasters, setDisasters] = useState([]);
    const [hospitals, setHospitals] = useState([]);
    const [shelters, setShelters] = useState([]);
    const [rescueTeams, setRescueTeams] = useState([]);
    const [assignments, setAssignments] = useState([]);
    const [missions, setMissions] = useState([]);
    const [forecastData, setForecastData] = useState(null);

    // ── SIMULATION ────────────────────────────────────────────────────────
    const [simulationState, setSimulationState] = useState(null);
    const [cityState, setCityState] = useState(null);
    const [simulationEvents, setSimulationEvents] = useState([]);
    const [loadingSimAction, setLoadingSimAction] = useState(false);

    // ── NAVIGATION ────────────────────────────────────────────────────────
    const [activeTab, setActiveTab] = useState("INCIDENTS");
    const [selectedDisaster, setSelectedDisaster] = useState(null);
    const [selectedMission, setSelectedMission] = useState(null);

    // ── SMART DISPATCH ────────────────────────────────────────────────────
    const [recommendedTeams, setRecommendedTeams] = useState([]);
    const [recommendedTeam, setRecommendedTeam] = useState(null);
    const [activeRoute, setActiveRoute] = useState(null);

    // ── UI ────────────────────────────────────────────────────────────────
    const [loading, setLoading] = useState(true);
    const [routeLoading, setRouteLoading] = useState(false);
    const [dispatchLoading, setDispatchLoading] = useState(false);
    const [error, setError] = useState(null);

    // ── DATA FETCHERS ─────────────────────────────────────────────────────
    const fetchMissionsData = useCallback(async () => {
        try {
            const res = await getMissions();
            if (res?.data) setMissions(res.data);
        } catch (err) {
            console.error("Failed to load missions:", err);
        }
    }, []);

    const fetchSimulationData = useCallback(async () => {
        try {
            const [simState, snapshot, events] = await Promise.all([
                simulationService.getSimulationState(),
                simulationService.getCitySnapshot(),
                simulationService.getSimulationEvents(30),
            ]);
            setSimulationState(simState);
            setCityState(snapshot);
            setSimulationEvents(events);
        } catch (err) {
            console.warn("Simulation data note:", err);
        }
    }, []);

    const loadDashboard = useCallback(async () => {
        try {
            setError(null);
            const [disastersData, hospitalsData, sheltersData, teamsData] = await Promise.all([
                getDisasters().catch((e) => { console.warn(e?.message); return []; }),
                getHospitals().catch((e) => { console.warn(e?.message); return []; }),
                getShelters().catch((e) => { console.warn(e?.message); return []; }),
                getRescueTeams().catch((e) => { console.warn(e?.message); return []; }),
            ]);

            setDisasters(disastersData || []);
            setHospitals(hospitalsData || []);
            setShelters(sheltersData || []);
            setRescueTeams(teamsData || []);

            await Promise.all([
                fetchMissionsData().catch(() => {}),
                fetchSimulationData().catch(() => {}),
            ]);

            if (token) {
                try {
                    const assignmentData = await getAssignments(token);
                    setAssignments(assignmentData || []);
                } catch {
                    setAssignments([]);
                }
            }

            predictionService.getPredictiveDashboard()
                .then((res) => { if (res?.data) setForecastData(res.data); })
                .catch(() => {});

            if (!disastersData.length && !hospitalsData.length) {
                setError("Backend API is reconnecting. Check uvicorn terminal.");
            }
        } catch (err) {
            console.error("Dashboard load error:", err);
            setError("Unable to connect to backend at http://127.0.0.1:8000.");
        } finally {
            setLoading(false);
        }
    }, [token, fetchMissionsData, fetchSimulationData]);

    // ── INITIAL HYDRATION ─────────────────────────────────────────────────
    useEffect(() => {
        let ignore = false;
        async function run() { if (!ignore) await loadDashboard(); }
        run();
        return () => { ignore = true; };
    }, [loadDashboard]);

    // ── WEBSOCKET SUBSCRIPTIONS ───────────────────────────────────────────
    useEffect(() => {
        wsManager.connect(token);

        const unsubIncidentCreated = wsManager.subscribe("INCIDENT_CREATED", (inc) => {
            if (!inc) return;
            setDisasters((prev) => prev.some((d) => d.id === inc.id) ? prev : [inc, ...prev]);
        });

        const unsubIncidentUpdated = wsManager.subscribe("INCIDENT_UPDATED", (inc) => {
            if (!inc) return;
            setDisasters((prev) => prev.map((d) => d.id === inc.id ? { ...d, ...inc } : d));
            if (selectedDisaster?.id === inc.id)
                setSelectedDisaster((prev) => ({ ...prev, ...inc }));
        });

        const unsubMissionCreated = wsManager.subscribe("MISSION_CREATED", () => {
            fetchMissionsData();
            getRescueTeams().then(setRescueTeams);
        });

        const unsubMissionUpdated = wsManager.subscribe("MISSION_UPDATED", () => {
            fetchMissionsData();
            getRescueTeams().then(setRescueTeams);
        });

        const unsubSimTick = wsManager.subscribe("SIMULATION_TICK", (tickData) => {
            if (!tickData) return;
            setSimulationState((prev) => ({
                ...(prev || {}),
                current_tick: tickData.tick,
                is_running: true,
                active_incidents: tickData.disasters_count,
            }));
            setCityState((prev) => ({
                ...(prev || {}),
                tick_count: tickData.tick,
                safe_citizens: tickData.safe_citizens,
                endangered_citizens: tickData.endangered_citizens,
                evacuating_citizens: tickData.evacuating_citizens,
                injured_citizens: tickData.injured_citizens,
                rescued_citizens: tickData.rescued_citizens,
                weather: tickData.weather || prev?.weather,
                traffic: tickData.traffic || prev?.traffic,
            }));
            if (tickData.recent_events?.length) {
                setSimulationEvents((prev) => {
                    const combined = [...tickData.recent_events, ...prev];
                    const seen = new Set();
                    return combined.filter((ev) => {
                        const key = `${ev.tick}-${ev.event_type}-${ev.description}`;
                        if (seen.has(key)) return false;
                        seen.add(key);
                        return true;
                    }).slice(0, 50);
                });
            }
        });

        const unsubScenarioLaunched = wsManager.subscribe("SCENARIO_LAUNCHED", loadDashboard);

        const unsubPredUpdated = wsManager.subscribe("prediction.updated", (predData) => {
            if (predData) setForecastData(predData);
        });

        return () => {
            unsubIncidentCreated();
            unsubIncidentUpdated();
            unsubMissionCreated();
            unsubMissionUpdated();
            unsubSimTick();
            unsubScenarioLaunched();
            unsubPredUpdated();
        };
    }, [token, fetchMissionsData, selectedDisaster, loadDashboard]);

    // ── SIMULATION ACTIONS ────────────────────────────────────────────────
    const handleSimulationAction = async (action) => {
        if (!isAuthenticated) { setIsAuthModalOpen(true); return; }
        setLoadingSimAction(true);
        try {
            const newState = await simulationService.performAction(action);
            if (newState) setSimulationState(newState);
            if (action === "tick" || action === "reset") {
                const snapshot = await simulationService.getCitySnapshot();
                setCityState(snapshot);
                const fresh = await getDisasters();
                setDisasters(fresh);
            }
        } catch (err) {
            console.error("Simulation action failed:", err);
            alert(err?.response?.data?.message || err?.message || "Simulation action failed.");
        } finally {
            setLoadingSimAction(false);
        }
    };

    // ── SELECT DISASTER ────────────────────────────────────────────────────
    async function selectDisaster(disaster) {
        setSelectedDisaster(disaster);
        setSelectedMission(null);
        setRecommendedTeams([]);
        setRecommendedTeam(null);
        setActiveRoute(null);
        if (activeTab !== "INCIDENTS") setActiveTab("INCIDENTS");

        try {
            setRouteLoading(true);
            const result = await getRecommendedRescueTeams(disaster.id);
            if (result.success && result.teams) {
                setRecommendedTeams(result.teams);
                if (result.recommended_team) {
                    const best = result.recommended_team;
                    setRecommendedTeam(best);
                    setActiveRoute({
                        distance_km: best.distance_km,
                        duration_minutes: best.eta_minutes,
                        geometry: best.route_geometry,
                    });
                }
            }
        } catch (err) {
            console.error("Smart dispatch recommendation failed:", err);
        } finally {
            setRouteLoading(false);
        }
    }

    // ── GENERATE AI INCIDENT ACTION PLAN (IAP) ─────────────────────────────
    async function handleOpenIAP(incidentId) {
        setLoadingIAP(true);
        setIsIAPModalOpen(true);
        try {
            const data = await incidentService.getIncidentIAP(incidentId);
            setActiveIAP(data);
        } catch (err) {
            console.error("IAP generation error:", err);
            alert(err?.response?.data?.message || err?.message || "Failed to generate Incident Action Plan.");
        } finally {
            setLoadingIAP(false);
        }
    }

    // ── SELECT MISSION ─────────────────────────────────────────────────────
    function handleSelectMission(mission) {
        setSelectedMission(mission);
        if (mission?.route_geometry) {
            setActiveRoute({
                distance_km: mission.distance_km,
                duration_minutes: mission.eta_minutes,
                geometry: mission.route_geometry,
            });
        }
    }

    // ── UPDATE MISSION STATUS ──────────────────────────────────────────────
    async function handleUpdateMissionStatus(assignmentId, newStatus) {
        if (!isAuthenticated) { setIsAuthModalOpen(true); return; }
        try {
            await updateAssignmentStatus(assignmentId, newStatus, token);
            setRescueTeams(await getRescueTeams());
            await fetchMissionsData();
            if (token) setAssignments(await getAssignments(token));
            if (newStatus === "COMPLETED") alert("🎉 Mission completed! Response unit is now AVAILABLE.");
        } catch (err) {
            console.error("Status update failed:", err);
            alert(err?.response?.data?.message || err?.response?.data?.detail || "Failed to update mission status.");
        }
    }

    // ── DISPATCH TEAM ──────────────────────────────────────────────────────
    async function dispatchTeam() {
        if (!selectedDisaster || !recommendedTeam) return;
        if (!isAuthenticated) { setIsAuthModalOpen(true); return; }
        if (!hasRole(["ADMIN", "COMMANDER", "DISPATCHER"])) {
            alert(`⚠️ Dispatch Clearance Required:\nOnly COMMANDER, DISPATCHER, or ADMIN can dispatch.\nYour role: ${user?.role || "CITIZEN"}.`);
            setIsAuthModalOpen(true);
            return;
        }
        try {
            setDispatchLoading(true);
            const assignment = await createAssignment(selectedDisaster.id, recommendedTeam.team_id, token);
            if (assignment) setAssignments((prev) => [...prev, assignment]);
            setRescueTeams(await getRescueTeams());
            await fetchMissionsData();
            setRecommendedTeams((prev) =>
                prev.map((t) => t.team_id === recommendedTeam.team_id ? { ...t, status: "DISPATCHED" } : t)
            );
            setRecommendedTeam((prev) => prev ? { ...prev, status: "DISPATCHED" } : prev);
            if (assignment) {
                setActiveRoute({
                    distance_km: assignment.distance_km || recommendedTeam.distance_km,
                    duration_minutes: assignment.estimated_arrival_minutes || recommendedTeam.eta_minutes,
                    geometry: assignment.route_geometry || recommendedTeam.route_geometry,
                });
            }
            setActiveTab("MISSIONS");
        } catch (err) {
            console.error("Dispatch failed:", err);
            if (err?.response?.status === 403) {
                alert(`⚠️ Dispatch Authority Denied (403 Forbidden). Your role: ${user?.role || "CITIZEN"}.`);
                setIsAuthModalOpen(true);
            } else {
                alert(err?.response?.data?.message || err?.response?.data?.detail || "Dispatch failed.");
            }
        } finally {
            setDispatchLoading(false);
        }
    }

    // ── LOADING SCREEN ─────────────────────────────────────────────────────
    if (loading) {
        return (
            <div className="loading-screen">
                <div className="loading-logo">🛡️</div>
                <div className="loading-spinner" />
                <p className="loading-text">Initializing AegisAI Digital Twin & Telemetry Stream...</p>
                <span className="loading-sub">Connecting to backend services</span>
            </div>
        );
    }

    const availableTeamsCount = rescueTeams.filter((t) => t.status === "AVAILABLE").length;

    // ── MAIN LAYOUT ────────────────────────────────────────────────────────
    return (
        <div className="aegis-app">
            {/* ── LEFT SIDEBAR ── */}
            <Sidebar
                activeTab={activeTab}
                onTabChange={setActiveTab}
                onOpenAuthModal={() => setIsAuthModalOpen(true)}
                onOpenLibrary={() => setIsLibraryOpen(true)}
                onOpenWhatIf={() => setIsWhatIfOpen(true)}
                onOpenSpawnModal={() => setIsSpawnModalOpen(true)}
                disastersCount={disasters.length}
                missionsCount={missions.length}
            />

            {/* ── MAIN BODY: MAP + PANEL ── */}
            <div className="aegis-main">
                {/* KPI RIBBON at top of main */}
                <div className="aegis-kpi-ribbon">
                    <SimulationKPIs
                        disastersCount={disasters.length}
                        missionsCount={missions.length}
                        availableTeamsCount={availableTeamsCount}
                        totalTeamsCount={rescueTeams.length}
                        hospitals={hospitals}
                        cityState={cityState}
                    />
                    {error && (
                        <div className="aegis-error-bar">
                            <span>⚠️ {error}</span>
                            <button className="retry-btn" onClick={loadDashboard}>🔄 Retry</button>
                        </div>
                    )}
                </div>

                {/* ── SCENARIO STUDIO — full aegis-main overlay ── */}
                {activeTab === "SCENARIO" && (
                    <div className="scenario-fullscreen-overlay">
                        <div className="scenario-overlay-header">
                            <span className="scenario-overlay-back-btn" onClick={() => setActiveTab("INCIDENTS")}>← Back to Map</span>
                        </div>
                        <div className="scenario-overlay-inner">
                            <ScenarioDesigner
                                onScenarioLaunched={async () => {
                                    await loadDashboard();
                                    setActiveTab("SIMULATION");
                                }}
                                onOpenLibrary={() => setIsLibraryOpen(true)}
                            />
                        </div>
                    </div>
                )}

                {/* MAP + CONTENT SPLIT — hidden when scenario is open */}
                <div className={`aegis-content ${activeTab === "SCENARIO" ? "aegis-content-hidden" : ""}`}>
                    {/* MAP — always visible */}
                    <section className="aegis-map-section">
                        <DisasterMap
                            disasters={disasters}
                            hospitals={hospitals}
                            shelters={shelters}
                            rescueTeams={rescueTeams}
                            assignments={assignments}
                            activeRoute={activeRoute}
                            buildings={cityState?.buildings || []}
                            roads={cityState?.roads || []}
                            citizens={cityState?.citizens || []}
                            forecastData={forecastData}
                            onSelectIncident={selectDisaster}
                        />
                    </section>

                    {/* RIGHT PANEL — always rendered */}
                    <aside className="aegis-right-panel">


                        {/* ── INCIDENTS ── */}
                        {activeTab === "INCIDENTS" && (
                            <div className="right-panel-scroll">
                                <div className="panel-header">
                                    <span className="panel-icon">🚨</span>
                                    <div>
                                        <h2 className="panel-title">Active Incidents</h2>
                                        <p className="panel-subtitle">{disasters.length} active disaster{disasters.length !== 1 ? "s" : ""} reported</p>
                                    </div>
                                </div>

                                {disasters.length === 0 ? (
                                    <div className="empty-state">
                                        <span className="empty-icon">✅</span>
                                        <p>All clear — no active incidents.</p>
                                        <span>Use Scenario Studio to simulate a disaster event.</span>
                                    </div>
                                ) : (
                                    <div className="incident-list">
                                        {disasters.map((disaster) => (
                                            <div
                                                key={disaster.id}
                                                className={`incident-card ${selectedDisaster?.id === disaster.id ? "selected" : ""}`}
                                                onClick={() => selectDisaster(disaster)}
                                            >
                                                <div className="incident-card-main">
                                                    <h3>🚨 {disaster.title}</h3>
                                                    <p>{disaster.disaster_type?.replace(/_/g, " ")}</p>
                                                </div>
                                                <span className={`severity-badge ${disaster.severity?.toLowerCase()}`}>
                                                    {disaster.severity}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {/* SELECTED DISASTER DETAILS */}
                                {selectedDisaster && (
                                    <div className="incident-detail-panel">
                                        <div className="panel-header" style={{ marginBottom: 12 }}>
                                            <span className="panel-icon">📍</span>
                                            <div>
                                                <h2 className="panel-title">Incident Details</h2>
                                                <p className="panel-subtitle">Smart dispatch & unit ranking</p>
                                            </div>
                                        </div>

                                        <h3 className="incident-detail-title">{selectedDisaster.title}</h3>

                                        <div className="detail-grid">
                                            <div className="detail-row"><span>Type</span><strong>{selectedDisaster.disaster_type}</strong></div>
                                            <div className="detail-row"><span>Severity</span><strong>{selectedDisaster.severity}</strong></div>
                                            <div className="detail-row"><span>Status</span><strong>{selectedDisaster.status}</strong></div>
                                            {selectedDisaster.affected_radius_meters && (
                                                <div className="detail-row">
                                                    <span>Radius</span>
                                                    <strong>{(selectedDisaster.affected_radius_meters / 1000).toFixed(1)} km</strong>
                                                </div>
                                            )}
                                        </div>

                                        <button
                                            className="action-btn ai-iap-btn"
                                            style={{
                                                width: "100%",
                                                marginTop: 10,
                                                marginBottom: 10,
                                                padding: "10px 14px",
                                                background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
                                                color: "white",
                                                fontWeight: 600,
                                                borderRadius: 8,
                                                border: "none",
                                                cursor: "pointer",
                                                display: "flex",
                                                alignItems: "center",
                                                justifyContent: "center",
                                                gap: 8,
                                                boxShadow: "0 4px 12px rgba(99, 102, 241, 0.3)",
                                            }}
                                            onClick={() => handleOpenIAP(selectedDisaster.id)}
                                        >
                                            <span>🧠</span> AI Incident Action Plan (IAP) & Directives
                                        </button>

                                        <hr className="detail-divider" />

                                        {routeLoading && (
                                            <div className="route-loading">
                                                <div className="spinner" />
                                                Evaluating candidates & computing OSRM routes...
                                            </div>
                                        )}

                                        {!routeLoading && recommendedTeams.length > 0 && (
                                            <div className="team-ranking">
                                                <h3>🚑 Smart Candidate Ranking</h3>
                                                {recommendedTeams.map((team) => (
                                                    <div
                                                        key={team.team_id}
                                                        className={`team-ranking-card ${team.rank === 1 ? "best-team" : ""}`}
                                                    >
                                                        <div className="team-rank">#{team.rank}</div>
                                                        <div className="team-info">
                                                            <strong>{team.team_name}</strong>
                                                            <span>{team.vehicle_type}</span>
                                                            <span>🚗 {team.distance_km} km • ⏱ {team.eta_minutes} min</span>
                                                            <span>Status: {team.status}</span>
                                                        </div>
                                                        <div className="team-score">{team.score}</div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}

                                        {!routeLoading && recommendedTeam && (
                                            <div className="recommended-team">
                                                <div className="recommended-title">🏆 Recommended Response Unit</div>
                                                <h3>{recommendedTeam.team_name}</h3>
                                                <p>{recommendedTeam.vehicle_type} • {recommendedTeam.members} members</p>
                                                <div className="route-box">
                                                    <div><strong>🚗 Road Distance</strong><span>{recommendedTeam.distance_km} km</span></div>
                                                    <div><strong>⏱ ETA</strong><span>{recommendedTeam.eta_minutes} min</span></div>
                                                </div>
                                                <div className="response-score">
                                                    Response Score: <strong>{recommendedTeam.score}/100</strong>
                                                </div>
                                                {recommendedTeam.status === "AVAILABLE" && (
                                                    <button
                                                        className="dispatch-button"
                                                        onClick={dispatchTeam}
                                                        disabled={dispatchLoading}
                                                    >
                                                        {dispatchLoading ? "Dispatching..." : "🚑 DISPATCH UNIT"}
                                                    </button>
                                                )}
                                                {recommendedTeam.status === "DISPATCHED" && (
                                                    <div className="dispatched-message">🚑 Unit Dispatched & En Route</div>
                                                )}
                                            </div>
                                        )}

                                        {!routeLoading && !recommendedTeam && recommendedTeams.length === 0 && (
                                            <div className="no-team">No available rescue units within operational radius.</div>
                                        )}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* ── MISSIONS ── */}
                        {activeTab === "MISSIONS" && (
                            <div className="right-panel-scroll">
                                <MissionControl
                                    missions={missions}
                                    onUpdateStatus={handleUpdateMissionStatus}
                                    onSelectMission={handleSelectMission}
                                    selectedMissionId={selectedMission?.assignment_id}
                                />
                            </div>
                        )}

                        {/* ── SCENARIO STUDIO ── */}
                        {activeTab === "SCENARIO" && (
                            <div className="right-panel-scroll">
                                <ScenarioDesigner
                                    onScenarioLaunched={async () => {
                                        await loadDashboard();
                                        setActiveTab("SIMULATION");
                                    }}
                                    onOpenLibrary={() => setIsLibraryOpen(true)}
                                />
                            </div>
                        )}

                        {/* ── DIGITAL TWIN ── */}
                        {activeTab === "SIMULATION" && (
                            <div className="right-panel-scroll">
                                <SimulationControls
                                    simulationState={simulationState}
                                    cityState={cityState}
                                    onAction={handleSimulationAction}
                                    onOpenWhatIf={() => setIsWhatIfOpen(true)}
                                    onOpenSpawnModal={() => setIsSpawnModalOpen(true)}
                                    loadingAction={loadingSimAction}
                                />
                                <SimulationTimeline
                                    currentTick={simulationState?.current_tick || 0}
                                    isRunning={simulationState?.is_running || false}
                                />
                                <LiveEventsFeed events={simulationEvents} />
                            </div>
                        )}

                        {/* ── PREDICTIVE AI ── */}
                        {activeTab === "PREDICTIONS" && (
                            <div className="right-panel-scroll">
                                <PredictiveDashboard
                                    onSelectIncident={selectDisaster}
                                    simulationId={simulationState?.simulation_id}
                                />
                            </div>
                        )}

                        {/* ── ANALYTICS ── */}
                        {activeTab === "ANALYTICS" && (
                            <div className="right-panel-scroll">
                                <AnalyticsDashboard
                                    cityState={cityState}
                                    disasters={disasters}
                                    missions={missions}
                                    rescueTeams={rescueTeams}
                                />
                            </div>
                        )}

                        {/* ── RESOURCES ── */}
                        {activeTab === "RESOURCES" && (
                            <div className="right-panel-scroll">
                                <ResourcesPanel
                                    hospitals={hospitals}
                                    shelters={shelters}
                                    rescueTeams={rescueTeams}
                                />
                            </div>
                        )}

                        {/* ── SETTINGS ── */}
                        {activeTab === "SETTINGS" && (
                            <div className="right-panel-scroll">
                                <div className="panel-header">
                                    <span className="panel-icon">⚙️</span>
                                    <div>
                                        <h2 className="panel-title">System Settings</h2>
                                        <p className="panel-subtitle">Configuration & preferences</p>
                                    </div>
                                </div>
                                <div className="settings-grid">
                                    <div className="settings-section">
                                        <h3>Connection</h3>
                                        <div className="setting-row">
                                            <span>Backend API</span>
                                            <code>http://127.0.0.1:8000</code>
                                        </div>
                                        <div className="setting-row">
                                            <span>WebSocket</span>
                                            <code>ws://localhost:8000/ws/v1/stream</code>
                                        </div>
                                    </div>
                                    <div className="settings-section">
                                        <h3>Session</h3>
                                        <div className="setting-row">
                                            <span>User</span>
                                            <strong>{user?.name || "Guest"}</strong>
                                        </div>
                                        <div className="setting-row">
                                            <span>Role</span>
                                            <strong>{user?.role || "GUEST"}</strong>
                                        </div>
                                        <div className="setting-row">
                                            <span>Email</span>
                                            <strong>{user?.email || "—"}</strong>
                                        </div>
                                    </div>
                                    <div className="settings-section">
                                        <h3>Actions</h3>
                                        <button
                                            className="settings-action-btn"
                                            onClick={loadDashboard}
                                        >
                                            🔄 Refresh All Data
                                        </button>
                                        {!isAuthenticated && (
                                            <button
                                                className="settings-action-btn primary"
                                                onClick={() => setIsAuthModalOpen(true)}
                                            >
                                                🔑 Sign In / Register
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>
                        )}
                    </aside>
                </div>
            </div>

            {/* ── MODALS ── */}
            <AuthModal isOpen={isAuthModalOpen} onClose={() => setIsAuthModalOpen(false)} />
            <WhatIfModal isOpen={isWhatIfOpen} onClose={() => setIsWhatIfOpen(false)} />
            <ScenarioListModal
                isOpen={isLibraryOpen}
                onClose={() => setIsLibraryOpen(false)}
                onLaunchScenario={async () => {
                    await loadDashboard();
                    setActiveTab("SIMULATION");
                }}
            />
            <SpawnIncidentModal
                isOpen={isSpawnModalOpen}
                onClose={() => setIsSpawnModalOpen(false)}
                onIncidentSpawned={async () => {
                    const fresh = await getDisasters();
                    setDisasters(fresh);
                    fetchSimulationData();
                }}
            />
            <IncidentActionPlanModal
                isOpen={isIAPModalOpen}
                onClose={() => setIsIAPModalOpen(false)}
                iap={activeIAP}
                loading={loadingIAP}
                incidentTitle={selectedDisaster?.title}
            />
        </div>
    );
}

export default Dashboard;