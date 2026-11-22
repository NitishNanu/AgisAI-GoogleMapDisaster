/**
 * AegisAI — AI Decision Review & Human-in-the-Loop Approval Panel.
 *
 * Provides incident commanders with full oversight of AI-recommended tactical
 * emergency decisions: one-click approval, rejection with reason, policy explanation,
 * and live mission execution.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { aiDecisionService } from '../../services/aiDecisionService';
import { useAuth } from '../../context/AuthContext';

function useOptionalAuth() {
  try {
    return useAuth();
  } catch {
    return {
      token: typeof localStorage !== 'undefined' ? localStorage.getItem('aegis_access_token') || 'demo-token' : 'demo-token',
      user: null,
      isAuthenticated: true,
    };
  }
}

function formatApiError(err, fallbackMessage) {
  const status = err?.response?.status;
  if (status === 401) {
    return {
      isAuthError: true,
      status: 401,
      title: 'Security Clearance Required',
      message: 'Active authentication required. Please sign in with Commander, Dispatcher, or Admin clearance to generate and review AI decisions.',
    };
  }
  if (status === 403) {
    return {
      isAuthError: true,
      status: 403,
      title: 'Insufficient Security Clearance',
      message: 'This operation requires Commander, Dispatcher, or Admin operational clearance.',
    };
  }

  const detail = err?.response?.data?.detail;
  let message = '';
  if (Array.isArray(detail)) {
    message = detail.map((d) => d.msg || d.message).join(' • ');
  } else if (typeof detail === 'string') {
    message = detail;
  } else if (err?.response?.data?.message) {
    message = err.response.data.message;
  } else if (err?.message) {
    message = err.message;
  } else {
    message = fallbackMessage;
  }

  return {
    isAuthError: false,
    status: status || 500,
    title: 'Operation Notice',
    message,
  };
}

const STATUS_COLORS = {
  REVIEW_REQUIRED: '#f59e0b',
  APPROVED: '#10b981',
  REJECTED: '#ef4444',
  EXECUTED: '#3b82f6',
  MODIFIED: '#8b5cf6',
  FAILED: '#64748b',
};

const PRIORITY_COLORS = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#f59e0b',
  LOW: '#10b981',
};

function ActionDirectiveView({ action }) {
  const [showRawCoordinates, setShowRawCoordinates] = useState(false);

  if (!action) return null;

  if (typeof action === 'string') {
    return (
      <div className="decision-action-box">
        <div className="decision-action-header">Action Directive</div>
        <div className="decision-action-content">{action}</div>
      </div>
    );
  }

  const {
    directive,
    resource_name,
    vehicle_type,
    destination_hospital_name,
    destination_hospital_id,
    estimated_arrival_minutes,
    distance_km,
    route_geometry,
    recommended_notes,
  } = action;

  const hasStructuredFields = Boolean(
    directive ||
    resource_name ||
    destination_hospital_name ||
    destination_hospital_id ||
    estimated_arrival_minutes != null ||
    distance_km != null ||
    recommended_notes
  );

  if (!hasStructuredFields && !route_geometry) {
    return (
      <div className="decision-action-box">
        <div className="decision-action-header">Action Directive</div>
        <div className="decision-action-content">{JSON.stringify(action, null, 2)}</div>
      </div>
    );
  }

  const coordCount = Array.isArray(route_geometry?.coordinates)
    ? route_geometry.coordinates.length
    : 0;

  const getVehicleIcon = (type) => {
    switch (type) {
      case 'AMBULANCE':
        return '🚑';
      case 'FIRE_TRUCK':
        return '🚒';
      case 'RESCUE_BOAT':
        return '🚤';
      case 'POLICE_PATROL':
        return '🚓';
      case 'HELICOPTER':
        return '🚁';
      case 'RECON_DRONE':
        return '🛸';
      default:
        return '🚨';
    }
  };

  return (
    <div className="decision-action-box">
      <div className="decision-action-header">Action Directive</div>
      {directive && (
        <div className="action-directive-text" style={{ fontSize: '13px', color: '#f1f5f9', fontWeight: 600, marginBottom: '6px' }}>
          {directive}
        </div>
      )}
      <div className="action-directive-grid">
        {resource_name && (
          <div className="action-grid-item">
            <span className="action-item-label">Assigned Resource</span>
            <span className="action-item-value highlight">
              {getVehicleIcon(vehicle_type)} {resource_name}{' '}
              {vehicle_type && <span className="action-vehicle-tag">({vehicle_type})</span>}
            </span>
          </div>
        )}

        {(destination_hospital_name || destination_hospital_id) && (
          <div className="action-grid-item">
            <span className="action-item-label">Destination Facility</span>
            <span className="action-item-value">
              🏥 {destination_hospital_name || `Hospital #${destination_hospital_id}`}
            </span>
          </div>
        )}

        {estimated_arrival_minutes != null && (
          <div className="action-grid-item">
            <span className="action-item-label">Estimated Travel Time</span>
            <span className="action-item-value eta">
              ⏱️ {Number(estimated_arrival_minutes).toFixed(1)} min
            </span>
          </div>
        )}

        {distance_km != null && (
          <div className="action-grid-item">
            <span className="action-item-label">Travel Distance</span>
            <span className="action-item-value">
              📍 {Number(distance_km).toFixed(2)} km
            </span>
          </div>
        )}
      </div>

      {recommended_notes && (
        <div className="action-directive-note">
          <span className="action-note-icon">ℹ️</span>
          <span>{recommended_notes}</span>
        </div>
      )}

      {coordCount > 0 && (
        <div className="action-route-section">
          <div className="action-route-header">
            <span className="action-route-meta">
              🗺️ Turn-by-turn route mapped ({coordCount} waypoints)
            </span>
            <button
              type="button"
              className="btn-toggle-route-coords"
              onClick={() => setShowRawCoordinates((prev) => !prev)}
            >
              {showRawCoordinates ? 'Hide Coordinates' : 'Show Route JSON'}
            </button>
          </div>
          {showRawCoordinates && (
            <pre className="action-route-raw">
              {JSON.stringify(route_geometry, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export default function DecisionReviewPanel({ onExecuteDecision, onOpenAuth }) {
  const { token } = useOptionalAuth();
  const [decisions, setDecisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filterStatus, setFilterStatus] = useState('ALL');
  const [actionLoading, setActionLoading] = useState({});
  const [rejectingId, setRejectingId] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const [explanationData, setExplanationData] = useState({});
  const [loadingExplanation, setLoadingExplanation] = useState({});

  const fetchDecisions = useCallback(async () => {
    if (!token) {
      setLoading(false);
      setError({
        isAuthError: true,
        status: 401,
        title: 'Security Clearance Required',
        message: 'Active authentication required to view and review AI decisions. Please authenticate with Commander, Dispatcher, or Admin clearance.',
      });
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const params = filterStatus === 'ALL' ? {} : { status: filterStatus };
      const res = await aiDecisionService.listDecisions(params);
      const items = res?.data?.items || res?.data || [];
      setDecisions(Array.isArray(items) ? items : []);
    } catch (err) {
      console.error('Failed to load AI decisions:', err);
      setError(formatApiError(err, 'Failed to load decisions from the AI Decision Engine.'));
    } finally {
      setLoading(false);
    }
  }, [filterStatus, token]);

  useEffect(() => {
    fetchDecisions();
  }, [fetchDecisions]);

  const handleGenerate = async () => {
    if (!token) {
      if (onOpenAuth) onOpenAuth();
      else window.dispatchEvent(new CustomEvent('aegis:auth_expired'));
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await aiDecisionService.generateDecisions({ policy_type: 'OPTIMIZED' });
      await fetchDecisions();
    } catch (err) {
      console.error('Failed to generate AI recommendations:', err);
      setError(formatApiError(err, 'Failed to generate AI emergency recommendations.'));
      setLoading(false);
    }
  };

  const handleApprove = async (id) => {
    setActionLoading((prev) => ({ ...prev, [id]: true }));
    try {
      const res = await aiDecisionService.approveDecision(id, { auto_execute: true });
      await fetchDecisions();
      if (onExecuteDecision) onExecuteDecision();
      const updatedNotes = res?.data?.modification_notes || res?.modification_notes || '';
      if (updatedNotes.includes('Auto-dispatch deferred')) {
        alert('Decision APPROVED! Note: Immediate dispatch was deferred because this resource or incident is already engaged in an active mission.');
      }
    } catch (err) {
      alert(`Approval notice: ${err?.response?.data?.message || err.message}`);
      await fetchDecisions();
    } finally {
      setActionLoading((prev) => ({ ...prev, [id]: false }));
    }
  };

  const handleReject = async (id) => {
    if (!rejectReason.trim()) {
      alert('Please enter a rejection reason.');
      return;
    }
    setActionLoading((prev) => ({ ...prev, [id]: true }));
    try {
      await aiDecisionService.rejectDecision(id, rejectReason.trim());
      setRejectingId(null);
      setRejectReason('');
      await fetchDecisions();
    } catch (err) {
      alert(`Rejection failed: ${err?.response?.data?.message || err.message}`);
    } finally {
      setActionLoading((prev) => ({ ...prev, [id]: false }));
    }
  };

  const handleExecute = async (id) => {
    setActionLoading((prev) => ({ ...prev, [id]: true }));
    try {
      await aiDecisionService.executeDecision(id);
      await fetchDecisions();
      if (onExecuteDecision) onExecuteDecision();
    } catch (err) {
      const errMsg = err?.response?.data?.message || err.message || '';
      if (errMsg.includes('already has an active mission') || errMsg.includes('currently')) {
        alert(`Mission Dispatch Conflict: ${errMsg}\n\nThe assigned team is currently deployed on another mission or this incident is already being responded to.`);
      } else {
        alert(`Execution notice: ${errMsg}`);
      }
    } finally {
      setActionLoading((prev) => ({ ...prev, [id]: false }));
    }
  };

  const toggleExplanation = async (id) => {
    if (explanationData[id]) {
      setExplanationData((prev) => ({ ...prev, [id]: null }));
      return;
    }
    setLoadingExplanation((prev) => ({ ...prev, [id]: true }));
    try {
      const res = await aiDecisionService.getExplanation(id);
      setExplanationData((prev) => ({ ...prev, [id]: res?.data || res }));
    } catch (err) {
      console.error('Failed to load explanation:', err);
      setExplanationData((prev) => ({
        ...prev,
        [id]: { narrative: 'Explanation temporarily unavailable from Ollama/XAI engine.' },
      }));
    } finally {
      setLoadingExplanation((prev) => ({ ...prev, [id]: false }));
    }
  };

  return (
    <div className="decision-review-panel">
      {/* Header */}
      <div className="decision-header">
        <div className="decision-title-group">
          <span style={{ fontSize: '24px' }}>🧠</span>
          <div>
            <h2 className="panel-title">AI Tactical Decision Review</h2>
            <p className="panel-subtitle">
              Human-in-the-Loop decision review & algorithmic mission recommendations
            </p>
          </div>
        </div>
        <div className="decision-header-actions">
          <button
            onClick={handleGenerate}
            disabled={loading}
            className="btn-generate-decisions"
            type="button"
          >
            <span>⚡</span>
            <span>Generate Decisions</span>
          </button>
          <button
            onClick={fetchDecisions}
            className="btn-refresh-decisions"
            title="Refresh list"
            type="button"
          >
            🔄
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="decision-filter-bar">
        {['ALL', 'REVIEW_REQUIRED', 'APPROVED', 'EXECUTED', 'REJECTED'].map((st) => (
          <button
            key={st}
            type="button"
            onClick={() => setFilterStatus(st)}
            className={`decision-filter-btn ${filterStatus === st ? 'active' : ''}`}
          >
            {st.replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      {/* Loading State */}
      {loading && (
        <div className="decision-loading">
          <div className="decision-spinner" />
          <span>Evaluating disaster graph & optimizing tactics...</span>
        </div>
      )}

      {/* Error State */}
      {!loading && error && (
        <div className="decision-error-banner">
          <div className="decision-error-content">
            <span style={{ fontSize: '18px' }}>⚠️</span>
            <div>
              <strong>Error loading decisions:</strong>{' '}
              <span>{error.title ? `${error.title} — ` : ''}{error.message || (typeof error === 'string' ? error : JSON.stringify(error))}</span>
            </div>
          </div>
          <div className="decision-error-actions">
            {error.isAuthError ? (
              <button
                type="button"
                onClick={() => (onOpenAuth ? onOpenAuth() : window.dispatchEvent(new CustomEvent('aegis:auth_expired')))}
                className="btn-retry-decision btn-auth-clearance"
              >
                🔐 Sign In / Clearance
              </button>
            ) : (
              <button
                type="button"
                onClick={fetchDecisions}
                className="btn-retry-decision"
              >
                Retry
              </button>
            )}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && decisions.length === 0 && (
        <div className="decision-empty-state">
          <div style={{ fontSize: '36px' }}>🛡️</div>
          <h3>No AI Decisions Pending</h3>
          <p>
            {filterStatus === 'ALL'
              ? 'No active decisions generated yet. Click "Generate Decisions" to evaluate active incidents with our heuristic and optimization engine.'
              : `No decisions currently have status "${filterStatus}".`}
          </p>
          <button
            type="button"
            onClick={handleGenerate}
            className="btn-generate-decisions"
            style={{ marginTop: '6px' }}
          >
            <span>⚡</span>
            <span>Generate Tactical Decisions</span>
          </button>
        </div>
      )}

      {/* Decision Cards List */}
      {!loading && !error && decisions.length > 0 && (
        <div className="decision-list">
          {decisions.map((dec) => {
            const decId = dec.id || dec.decision_uuid;
            const statusColor = STATUS_COLORS[dec.status] || '#94a3b8';
            const priorityColor = PRIORITY_COLORS[dec.priority] || '#94a3b8';
            const confPct = Math.round((dec.confidence || 0) * 100);
            const scorePct = Math.round((dec.score || 0) * 100);
            const isActing = actionLoading[decId];
            const explanation = explanationData[decId];

            return (
              <div key={decId} className="decision-card">
                {/* Card Top Line */}
                <div className="decision-card-top">
                  <div className="decision-card-identity">
                    <span
                      className="badge-priority"
                      style={{
                        backgroundColor: `${priorityColor}22`,
                        color: priorityColor,
                        border: `1px solid ${priorityColor}55`,
                      }}
                    >
                      {dec.priority}
                    </span>
                    <span className="decision-type-label">
                      {dec.decision_type || 'TACTICAL_RESPONSE'}
                    </span>
                    {dec.policy_name && (
                      <span className="decision-policy-tag">
                        [{dec.policy_name} Policy]
                      </span>
                    )}
                  </div>
                  <span
                    className="badge-status"
                    style={{
                      backgroundColor: `${statusColor}22`,
                      color: statusColor,
                      border: `1px solid ${statusColor}55`,
                    }}
                  >
                    {dec.status}
                  </span>
                </div>

                {/* Action Directive */}
                {dec.action && <ActionDirectiveView action={dec.action} />}

                {/* Metrics: Confidence & Optimization Score */}
                <div className="decision-metrics-row">
                  <div className="decision-metric-item">
                    <div className="decision-metric-header">
                      <span>Model Confidence</span>
                      <span className="decision-metric-val">{confPct}%</span>
                    </div>
                    <div className="decision-bar-track">
                      <div
                        className="decision-bar-fill"
                        style={{ width: `${confPct}%`, backgroundColor: '#10b981' }}
                      />
                    </div>
                  </div>

                  <div className="decision-metric-item">
                    <div className="decision-metric-header">
                      <span>Optimization Score</span>
                      <span className="decision-metric-val">{scorePct}%</span>
                    </div>
                    <div className="decision-bar-track">
                      <div
                        className="decision-bar-fill"
                        style={{ width: `${scorePct}%`, backgroundColor: '#6366f1' }}
                      />
                    </div>
                  </div>
                </div>

                {/* Decision Rationale */}
                {Array.isArray(dec.reasoning) && dec.reasoning.length > 0 && (
                  <div className="decision-reasoning-section">
                    <div className="decision-reasoning-title">Decision Rationale</div>
                    <ul className="decision-reasoning-list">
                      {dec.reasoning.map((item, idx) => (
                        <li key={idx}>
                          {typeof item === 'string' ? item : JSON.stringify(item)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Rejection Alert if Rejected */}
                {dec.rejection_reason && (
                  <div className="decision-rejection-alert">
                    <strong>Rejection reason:</strong> {dec.rejection_reason}
                  </div>
                )}

                {/* Explanation Expandable (SHAP Bar Chart + Narrative Summary) */}
                {explanation && (
                  <div className="decision-briefing-wrap">
                    {/* SHAP Mathematical Feature Attributions Bar Chart */}
                    {explanation.feature_attributions && explanation.feature_attributions.length > 0 && (
                      <div className="decision-shap-card">
                        <div className="decision-shap-header">
                          <span>📊 SHAP Feature Attributions (TreeExplainer)</span>
                          <span className="decision-shap-sub">Impact on severity</span>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', paddingTop: '4px' }}>
                          {explanation.feature_attributions.map((attr, idx) => {
                            const val = attr.attribution ?? attr.abs_importance ?? 0;
                            const isPos = val >= 0;
                            const maxVal = Math.max(
                              ...explanation.feature_attributions.map(
                                (a) => Math.abs(a.attribution ?? a.abs_importance ?? 0.1)
                              ),
                              1.0
                            );
                            const barWidth = Math.min(100, Math.round((Math.abs(val) / maxVal) * 100));
                            return (
                              <div key={idx} className="decision-shap-row">
                                <span className="decision-shap-name" title={attr.feature}>
                                  {attr.feature.replace(/_/g, ' ')}
                                </span>
                                <div className="decision-shap-bar-track">
                                  <div
                                    style={{
                                      width: `${barWidth}%`,
                                      height: '100%',
                                      backgroundColor: isPos ? '#f43f5e' : '#10b981',
                                      borderRadius: '3px',
                                      transition: 'width 0.3s ease',
                                    }}
                                  />
                                </div>
                                <span
                                  className="decision-shap-bar-val"
                                  style={{ color: isPos ? '#fb7185' : '#34d399' }}
                                >
                                  {isPos ? '+' : ''}{val.toFixed(2)}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Factual Tactical Briefing — labeled honestly as heuristic or LLM */}
                    <div className="decision-narrative-card">
                      <div className="decision-narrative-header">
                        <strong>
                          <span>📝</span>
                          <span>{explanation.is_fallback ? "Tactical Briefing (Deterministic XAI Heuristic)" : `Tactical Briefing (${explanation.model_used || "Ollama LLM"})`}</span>
                        </strong>
                        {explanation.is_fallback && (
                          <span className="badge-heuristic" title="Ollama offline; generated by rule-based XAI heuristic">HEURISTIC FALLBACK</span>
                        )}
                      </div>

                      {explanation.summary && (
                        <div className="narrative-summary-lead">
                          {explanation.summary}
                        </div>
                      )}

                      {explanation.tactical_briefing && (
                        <p className="narrative-tactical-text">
                          {explanation.tactical_briefing}
                        </p>
                      )}

                      {Array.isArray(explanation.operational_risks) && explanation.operational_risks.length > 0 && (
                        <div className="narrative-section">
                          <span className="narrative-section-title">⚠️ Operational Risks</span>
                          <ul className="narrative-list risk-list">
                            {explanation.operational_risks.map((risk, rIdx) => (
                              <li key={rIdx}>{risk}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {Array.isArray(explanation.recommended_next_steps) && explanation.recommended_next_steps.length > 0 && (
                        <div className="narrative-section">
                          <span className="narrative-section-title">✅ Recommended Next Steps</span>
                          <ul className="narrative-list steps-list">
                            {explanation.recommended_next_steps.map((step, sIdx) => (
                              <li key={sIdx}>{step}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {!explanation.summary && !explanation.tactical_briefing && (
                        <p>
                          {typeof explanation === 'string'
                            ? explanation
                            : (explanation.narrative || explanation.explanation || JSON.stringify(explanation, null, 2))}
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {/* Reject Input Dialog */}
                {rejectingId === decId && (
                  <div className="decision-reject-box">
                    <label>Provide reason for rejection:</label>
                    <textarea
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      placeholder="e.g. Hazardous route condition, secondary collapse danger..."
                      className="decision-reject-textarea"
                      rows={2}
                    />
                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                      <button
                        type="button"
                        onClick={() => {
                          setRejectingId(null);
                          setRejectReason('');
                        }}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: '#94a3b8',
                          fontSize: '11px',
                          cursor: 'pointer',
                          padding: '6px 10px',
                        }}
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={() => handleReject(decId)}
                        disabled={isActing}
                        className="btn-decision-reject"
                        style={{ padding: '6px 14px' }}
                      >
                        Confirm Rejection
                      </button>
                    </div>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="decision-card-actions">
                  <button
                    type="button"
                    onClick={() => toggleExplanation(decId)}
                    disabled={loadingExplanation[decId]}
                    className="btn-toggle-xai"
                  >
                    <span>{explanation ? 'Hide Briefing' : '🔍 XAI Briefing'}</span>
                    {loadingExplanation[decId] && <span style={{ marginLeft: '4px' }}>⏳</span>}
                  </button>

                  <div className="decision-cta-group">
                    {dec.status === 'REVIEW_REQUIRED' && (
                      <>
                        <button
                          type="button"
                          onClick={() => setRejectingId(decId)}
                          disabled={isActing}
                          className="btn-decision-reject"
                        >
                          ✕ Reject
                        </button>
                        <button
                          type="button"
                          onClick={() => handleApprove(decId)}
                          disabled={isActing}
                          className="btn-decision-approve"
                        >
                          ✓ Approve & Dispatch
                        </button>
                      </>
                    )}

                    {dec.status === 'APPROVED' && (
                      <button
                        type="button"
                        onClick={() => handleExecute(decId)}
                        disabled={isActing}
                        className="btn-decision-execute"
                      >
                        🚀 Execute Mission
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
