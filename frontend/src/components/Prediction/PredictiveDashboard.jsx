import React, { useState, useEffect, useMemo, useCallback } from 'react';
import predictionService from '../../services/predictionService';
import wsManager from '../../services/websocketManager';

/**
 * Custom Responsive SVG Line Chart for Casualty Horizon Projections.
 */
function CasualtyHorizonChart({ casualties, selectedHorizon }) {
  if (!casualties || !casualties.forecast || casualties.forecast.length === 0) {
    return <div className="pred-empty-chart">No casualty forecast data available.</div>;
  }

  const dataPoints = [
    {
      horizon: 0,
      label: 'Now',
      total: casualties.current_casualties,
      critical: casualties.current_critical,
      confidence: 1.0,
    },
    ...casualties.forecast.map((pt) => ({
      horizon: pt.horizon_minutes,
      label: `+${pt.horizon_minutes}m`,
      total: pt.expected_casualties,
      critical: pt.critical_patients,
      confidence: pt.confidence || 0.85,
    })),
  ];

  const maxVal = Math.max(...dataPoints.map((d) => d.total), 10) * 1.2;
  const width = 500;
  const height = 180;
  const padX = 40;
  const padY = 25;

  const getX = (idx) => padX + (idx / (dataPoints.length - 1)) * (width - 2 * padX);
  const getY = (val) => height - padY - (val / maxVal) * (height - 2 * padY);

  const totalPointsPath = dataPoints.map((d, i) => `${getX(i)},${getY(d.total)}`).join(' ');
  const criticalPointsPath = dataPoints.map((d, i) => `${getX(i)},${getY(d.critical)}`).join(' ');

  const totalAreaPath = `${getX(0)},${height - padY} ${totalPointsPath} ${getX(dataPoints.length - 1)},${height - padY}`;

  return (
    <div className="pred-chart-container">
      <div className="pred-chart-header">
        <div className="pred-chart-title">
          <span>Casualty & Critical Patient Projection</span>
          <span className="pred-confidence-tag">
            Confidence: {Math.round(dataPoints[dataPoints.length - 1].confidence * 100)}%
          </span>
        </div>
        <div className="pred-legend">
          <span className="legend-item"><span className="legend-dot total" /> Projected Total</span>
          <span className="legend-item"><span className="legend-dot critical" /> Critical / ALS</span>
        </div>
      </div>

      <svg viewBox={`0 0 ${width} ${height}`} className="pred-svg-chart">
        <defs>
          <linearGradient id="totalGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ef4444" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#ef4444" stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {[0.25, 0.5, 0.75, 1.0].map((frac, idx) => {
          const y = height - padY - frac * (height - 2 * padY);
          return (
            <line
              key={idx}
              x1={padX}
              y1={y}
              x2={width - padX}
              y2={y}
              stroke="rgba(255,255,255,0.07)"
              strokeDasharray="3 3"
            />
          );
        })}

        {/* Area fill */}
        <polygon points={totalAreaPath} fill="url(#totalGrad)" />

        {/* Total line */}
        <polyline
          points={totalPointsPath}
          fill="none"
          stroke="#ef4444"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Critical line */}
        <polyline
          points={criticalPointsPath}
          fill="none"
          stroke="#f59e0b"
          strokeWidth="2.5"
          strokeDasharray="4 2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Data points & labels */}
        {dataPoints.map((d, i) => {
          const cx = getX(i);
          const cyTotal = getY(d.total);
          const cyCrit = getY(d.critical);
          const isSelected = selectedHorizon === d.horizon;

          return (
            <g key={i}>
              <circle
                cx={cx}
                cy={cyTotal}
                r={isSelected ? 6 : 4.5}
                fill="#ef4444"
                stroke="#1e293b"
                strokeWidth="2"
              />
              <text x={cx} y={cyTotal - 10} textAnchor="middle" fill="#f87171" fontSize="11" fontWeight="bold">
                {d.total}
              </text>

              <circle
                cx={cx}
                cy={cyCrit}
                r={isSelected ? 5 : 3.5}
                fill="#f59e0b"
                stroke="#1e293b"
                strokeWidth="1.5"
              />

              <text x={cx} y={height - 8} textAnchor="middle" fill="#94a3b8" fontSize="10">
                {d.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/**
 * Main Predictive Intelligence Command-Center Dashboard.
 */
export default function PredictiveDashboard({ onSelectIncident, simulationId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastFetched, setLastFetched] = useState(() => Date.now());
  const [secondsAgo, setSecondsAgo] = useState(0);
  const [selectedHorizon, setSelectedHorizon] = useState(30);
  const [alertFilter, setAlertFilter] = useState('ALL');
  const [expandedAlertId, setExpandedAlertId] = useState(null);

  const fetchDashboard = useCallback(async (isBackground = false) => {
    try {
      if (!isBackground) setLoading(true);
      const res = await predictionService.getPredictiveDashboard(simulationId);
      if (res && res.data) {
        setData(res.data);
        setLastFetched(Date.now());
        setError(null);
      }
    } catch (err) {
      console.error('Failed to fetch predictive dashboard:', err);
      if (!data) setError('Predictive Intelligence engine currently unavailable.');
    } finally {
      if (!isBackground) setLoading(false);
    }
  }, [simulationId, data]);

  useEffect(() => {
    fetchDashboard();

    // Real-time WebSocket prediction telemetry
    const unsubPred = wsManager.subscribe('prediction.updated', (eventData) => {
      if (eventData) {
        setData(eventData);
        setLastFetched(Date.now());
        setError(null);
      }
    });

    const unsubSim = wsManager.subscribe('SIMULATION_TICK', () => {
      fetchDashboard(true);
    });

    const interval = setInterval(() => {
      fetchDashboard(true);
    }, 30000);

    return () => {
      if (typeof unsubPred === 'function') unsubPred();
      if (typeof unsubSim === 'function') unsubSim();
      clearInterval(interval);
    };
  }, [fetchDashboard]);

  // Live timer for stale indicator
  useEffect(() => {
    const timer = setInterval(() => {
      setSecondsAgo(Math.floor((Date.now() - lastFetched) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [lastFetched]);

  const filteredAlerts = useMemo(() => {
    if (!data || !data.alerts) return [];
    if (alertFilter === 'ALL') return data.alerts;
    return data.alerts.filter((a) => a.severity === alertFilter);
  }, [data, alertFilter]);

  const toggleAlertExpand = (id) => {
    setExpandedAlertId((prev) => (prev === id ? null : id));
  };

  if (loading && !data) {
    return (
      <div className="pred-loading-state">
        <div className="pred-spinner" />
        <p>Synthesizing Predictive Disaster Forecasts (+5m, +15m, +30m, +60m)...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="pred-error-state">
        <div className="pred-error-icon">⚠️</div>
        <h3>Forecast Service Offline</h3>
        <p>{error}</p>
        <button onClick={() => fetchDashboard()} className="btn btn-primary">
          Retry Forecast Connection
        </button>
      </div>
    );
  }

  const casualties = data?.casualties;
  const hospitals = data?.hospitals || [];
  const resources = data?.resources || [];
  const disasterRisks = data?.disaster_risk || [];
  const meta = data?.model_metadata;

  const cas30 = casualties?.forecast?.find((f) => f.horizon_minutes === 30);
  const casGrowthPct = casualties?.current_casualties
    ? Math.round((((cas30?.expected_casualties || casualties.current_casualties) - casualties.current_casualties) / casualties.current_casualties) * 100)
    : 0;

  const overloadedHospitals = hospitals.filter((h) => h.status === 'OVERLOAD' || h.status === 'CRITICAL');
  const criticalShortages = resources.filter((r) => r.shortage_risk_level === 'CRITICAL' || r.shortage_risk_level === 'HIGH');

  return (
    <div className="predictive-dashboard-wrapper">
      {/* Header & Control HUD */}
      <div className="pred-header">
        <div className="pred-header-left">
          <div className="pred-badge-live">
            <span className="live-pulse" /> PREDICTIVE INTELLIGENCE
          </div>
          <h2>Multi-Horizon Disaster Forecasting</h2>
          <div className="pred-meta-row">
            <span className="pred-meta-pill source">
              Source: {data?.prediction_source || 'SIMULATION + ML'}
            </span>
            <span className="pred-meta-pill model">
              Model: {meta?.model_name} (v{meta?.model_version})
            </span>
            <span className={`pred-meta-pill stale ${secondsAgo > 30 ? 'warning' : ''}`}>
              Updated {secondsAgo}s ago
            </span>
          </div>
        </div>

        <div className="pred-header-controls">
          <div className="pred-horizon-selector">
            <span className="pred-horizon-label">Forecast Focus:</span>
            {[5, 15, 30, 60].map((h) => (
              <button
                key={h}
                className={`horizon-btn ${selectedHorizon === h ? 'active' : ''}`}
                onClick={() => setSelectedHorizon(h)}
              >
                +{h}m
              </button>
            ))}
          </div>
          <button className="pred-refresh-btn" onClick={() => fetchDashboard()} title="Refresh telemetry">
            ↻
          </button>
        </div>
      </div>

      {/* KPI Headline Cards */}
      <div className="pred-kpi-grid">
        <div className="pred-kpi-card danger">
          <div className="kpi-top">
            <span className="kpi-label">Projected Casualties (+30m)</span>
            <span className="kpi-badge growth">+{casGrowthPct}%</span>
          </div>
          <div className="kpi-value-row">
            <span className="kpi-num">{cas30?.expected_casualties ?? casualties?.current_casualties ?? 0}</span>
            <span className="kpi-sub">Current: {casualties?.current_casualties ?? 0}</span>
          </div>
          <div className="kpi-bar-bg">
            <div className="kpi-bar-fill danger" style={{ width: `${Math.min(100, (cas30?.expected_casualties || 1) * 3)}%` }} />
          </div>
        </div>

        <div className="pred-kpi-card warning">
          <div className="kpi-top">
            <span className="kpi-label">Hospitals at Risk</span>
            <span className={`kpi-badge ${overloadedHospitals.length > 0 ? 'critical' : 'stable'}`}>
              {overloadedHospitals.length > 0 ? 'SATURATION RISK' : 'CAPACITY OK'}
            </span>
          </div>
          <div className="kpi-value-row">
            <span className="kpi-num">{overloadedHospitals.length}</span>
            <span className="kpi-sub">of {hospitals.length} active facilities</span>
          </div>
          <div className="kpi-bar-bg">
            <div
              className="kpi-bar-fill warning"
              style={{ width: `${(overloadedHospitals.length / Math.max(1, hospitals.length)) * 100}%` }}
            />
          </div>
        </div>

        <div className="pred-kpi-card primary">
          <div className="kpi-top">
            <span className="kpi-label">Resource Shortages</span>
            <span className="kpi-badge deficit">
              {criticalShortages.length > 0 ? `${criticalShortages.length} FLEETS SHORT` : 'BALANCED'}
            </span>
          </div>
          <div className="kpi-value-row">
            <span className="kpi-num">{criticalShortages.length}</span>
            <span className="kpi-sub">vehicle categories</span>
          </div>
          <div className="kpi-bar-bg">
            <div
              className="kpi-bar-fill primary"
              style={{ width: `${(criticalShortages.length / Math.max(1, resources.length)) * 100}%` }}
            />
          </div>
        </div>

        <div className="pred-kpi-card secondary">
          <div className="kpi-top">
            <span className="kpi-label">Active Hazards Tracked</span>
            <span className="kpi-badge stable">MONITORED</span>
          </div>
          <div className="kpi-value-row">
            <span className="kpi-num">{disasterRisks.length}</span>
            <span className="kpi-sub">epicenters evaluated</span>
          </div>
          <div className="kpi-bar-bg">
            <div className="kpi-bar-fill secondary" style={{ width: '70%' }} />
          </div>
        </div>
      </div>

      {/* Main Analysis Grid */}
      <div className="pred-main-grid">
        {/* Left Column: Casualty Chart & Hospital Forecasts */}
        <div className="pred-col-left">
          {/* Casualty Projection Chart */}
          <div className="pred-panel">
            <CasualtyHorizonChart casualties={casualties} selectedHorizon={selectedHorizon} />
          </div>

          {/* Hospital Saturation Forecast */}
          <div className="pred-panel">
            <div className="pred-panel-header">
              <div className="panel-title">
                <span>🏥 Hospital ER & ICU Saturation Forecast</span>
              </div>
              <span className="panel-sub">Focus Horizon: +{selectedHorizon}m</span>
            </div>

            <div className="pred-hospital-list">
              {hospitals.map((h) => {
                const targetForecast =
                  h.forecast.find((f) => f.horizon_minutes === selectedHorizon) || h.forecast[0];
                const icuPct = targetForecast?.projected_icu_occupancy_percent ?? h.current_icu_occupancy_percent;
                const bedPct = targetForecast?.projected_bed_occupancy_percent ?? h.current_bed_occupancy_percent;
                const isOver = targetForecast?.is_overloaded || icuPct >= 100.0;

                return (
                  <div key={h.hospital_id} className={`pred-hosp-row ${isOver ? 'overload' : ''}`}>
                    <div className="hosp-info">
                      <div className="hosp-name-row">
                        <span className="hosp-name">{h.name}</span>
                        <span className={`hosp-status-tag ${targetForecast?.status?.toLowerCase() || 'normal'}`}>
                          {targetForecast?.status || 'NORMAL'}
                        </span>
                      </div>
                      {h.expected_overload_minutes && (
                        <span className="hosp-overload-alert">
                          ⚠️ Projected ICU saturation in ~{Math.round(h.expected_overload_minutes)} min
                        </span>
                      )}
                    </div>

                    <div className="hosp-gauges">
                      <div className="gauge-item">
                        <div className="gauge-label">
                          <span>ICU Load</span>
                          <span className={icuPct >= 90 ? 'text-danger font-bold' : ''}>{icuPct}%</span>
                        </div>
                        <div className="gauge-track">
                          <div
                            className={`gauge-fill ${icuPct >= 100 ? 'overload' : icuPct >= 90 ? 'critical' : icuPct >= 75 ? 'warning' : 'normal'}`}
                            style={{ width: `${Math.min(100, icuPct)}%` }}
                          />
                        </div>
                      </div>

                      <div className="gauge-item">
                        <div className="gauge-label">
                          <span>General Beds</span>
                          <span>{bedPct}%</span>
                        </div>
                        <div className="gauge-track">
                          <div
                            className={`gauge-fill ${bedPct >= 90 ? 'critical' : 'normal'}`}
                            style={{ width: `${Math.min(100, bedPct)}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Column: Fleet Demand & Predictive Alerts */}
        <div className="pred-col-right">
          {/* Resource Demand Horizon */}
          <div className="pred-panel">
            <div className="pred-panel-header">
              <div className="panel-title">
                <span>🚒 Fleet Demand & Shortage Analysis</span>
              </div>
              <span className="panel-sub">+{selectedHorizon}m Horizon</span>
            </div>

            <div className="pred-resource-grid">
              {resources.map((r) => {
                const targetDemand =
                  r.forecast.find((f) => f.horizon_minutes === selectedHorizon) || r.forecast[0];
                const shortage = targetDemand?.projected_shortage || 0;
                const req = targetDemand?.required_count || 0;

                return (
                  <div key={r.resource_type} className={`pred-res-card ${shortage > 0 ? 'shortage' : ''}`}>
                    <div className="res-header">
                      <span className="res-name">{r.resource_type.replace('_', ' ')}</span>
                      {shortage > 0 ? (
                        <span className="res-shortage-badge">-{shortage} SHORT</span>
                      ) : (
                        <span className="res-ok-badge">ADEQUATE</span>
                      )}
                    </div>
                    <div className="res-metrics">
                      <div className="res-metric-item">
                        <span className="m-label">Available:</span>
                        <span className="m-val">{r.current_available}</span>
                      </div>
                      <div className="res-metric-item">
                        <span className="m-label">Required:</span>
                        <span className="m-val highlight">{req}</span>
                      </div>
                    </div>
                    <div className="res-bar-bg">
                      <div
                        className={`res-bar-fill ${shortage > 0 ? 'danger' : 'normal'}`}
                        style={{ width: `${Math.min(100, (r.current_available / Math.max(1, req)) * 100)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Predictive Alerts HUD */}
          <div className="pred-panel alerts-panel">
            <div className="pred-panel-header">
              <div className="panel-title">
                <span>🚨 Predictive Operational Alerts</span>
                <span className="alert-count-pill">{filteredAlerts.length}</span>
              </div>
              <div className="pred-alert-filters">
                {['ALL', 'CRITICAL', 'HIGH', 'WARNING'].map((f) => (
                  <button
                    key={f}
                    className={`alert-filter-btn ${alertFilter === f ? 'active' : ''}`}
                    onClick={() => setAlertFilter(f)}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            <div className="pred-alerts-list">
              {filteredAlerts.length === 0 ? (
                <div className="pred-no-alerts">
                  <span>✅</span> No predictive alerts triggered. All horizons within operational bounds.
                </div>
              ) : (
                filteredAlerts.map((alt) => {
                  const isExpanded = expandedAlertId === alt.id;
                  return (
                    <div
                      key={alt.id}
                      className={`pred-alert-card ${alt.severity.toLowerCase()}`}
                      onClick={() => toggleAlertExpand(alt.id)}
                    >
                      <div className="alert-card-top">
                        <span className={`alert-sev-badge ${alt.severity.toLowerCase()}`}>
                          {alt.severity}
                        </span>
                        <span className="alert-title">{alt.title}</span>
                      </div>
                      <p className="alert-msg">{alt.message}</p>

                      {isExpanded && (
                        <div className="alert-expanded-drawer">
                          <div className="drawer-item">
                            <span className="drawer-label">Factual XAI Explanation:</span>
                            <p className="drawer-text">{alt.explanation}</p>
                          </div>
                          <div className="drawer-item action">
                            <span className="drawer-label">Recommended Tactical Action:</span>
                            <p className="drawer-text action-highlight">{alt.recommended_action}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
