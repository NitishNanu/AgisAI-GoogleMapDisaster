import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PredictiveDashboard from '../components/Prediction/PredictiveDashboard';
import predictionService from '../services/predictionService';

vi.mock('../services/predictionService', () => ({
  default: {
    getPredictiveDashboard: vi.fn(),
  },
}));

vi.mock('../services/websocketManager', () => ({
  default: {
    subscribe: vi.fn(() => vi.fn()),
  },
}));

const mockDashboardData = {
  data: {
    casualties: {
      current_casualties: 12,
      model_confidence: 0.94,
      forecast: [
        { horizon_minutes: 5, expected_casualties: 14, confidence: 0.95 },
        { horizon_minutes: 15, expected_casualties: 20, confidence: 0.92 },
        { horizon_minutes: 30, expected_casualties: 28, confidence: 0.88 },
        { horizon_minutes: 60, expected_casualties: 42, confidence: 0.82 },
      ],
    },
    hospitals: [
      {
        hospital_id: 1,
        name: 'City General Hospital',
        current_icu_occupancy_percent: 85,
        current_bed_occupancy_percent: 78,
        expected_overload_minutes: 25,
        forecast: [
          { horizon_minutes: 5, projected_icu_occupancy_percent: 87, status: 'STABLE' },
          { horizon_minutes: 15, projected_icu_occupancy_percent: 92, status: 'CRITICAL' },
          { horizon_minutes: 30, projected_icu_occupancy_percent: 99, status: 'OVERLOAD' },
          { horizon_minutes: 60, projected_icu_occupancy_percent: 100, status: 'OVERLOAD' },
        ],
      },
    ],
    resources: [
      {
        resource_type: 'AMBULANCE',
        vehicle_type: 'AMBULANCE',
        current_available: 4,
        forecast: [
          { horizon_minutes: 5, projected_shortage: 0, status: 'SUFFICIENT' },
          { horizon_minutes: 15, projected_shortage: 2, status: 'DEFICIT' },
          { horizon_minutes: 30, projected_shortage: 5, status: 'CRITICAL_SHORTAGE' },
          { horizon_minutes: 60, projected_shortage: 8, status: 'CRITICAL_SHORTAGE' },
        ],
      },
    ],
    disaster_risk: [
      {
        incident_id: 101,
        disaster_type: 'FIRE',
        current_severity: 'HIGH',
        risk_score: 0.85,
      },
    ],
    alerts: [
      {
        id: 'alt-1',
        title: 'ICU Saturation Warning',
        severity: 'CRITICAL',
        description: 'City General will reach capacity in 25 min',
      },
    ],
    model_metadata: {
      model_name: 'AegisAI-PredictiveEngine-v1',
      version: '1.2.0',
    },
  },
};

describe('PredictiveDashboard Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders all horizon tabs (+5m, +15m, +30m, +60m)', async () => {
    predictionService.getPredictiveDashboard.mockResolvedValueOnce(mockDashboardData);

    render(<PredictiveDashboard simulationId="sim-123" />);

    // Wait for telemetry data to load
    await waitFor(() => {
      expect(screen.getByText('Forecast Focus:')).toBeInTheDocument();
    });

    // Check all horizon buttons render
    expect(screen.getByRole('button', { name: '+5m' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '+15m' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '+30m' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '+60m' })).toBeInTheDocument();
  });

  it('switches active focus horizon when horizon button is clicked', async () => {
    predictionService.getPredictiveDashboard.mockResolvedValueOnce(mockDashboardData);

    render(<PredictiveDashboard simulationId="sim-123" />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '+15m' })).toBeInTheDocument();
    });

    const btn15 = screen.getByRole('button', { name: '+15m' });
    fireEvent.click(btn15);

    expect(btn15).toHaveClass('active');
    expect(screen.getByText('Focus Horizon: +15m')).toBeInTheDocument();
  });
});
