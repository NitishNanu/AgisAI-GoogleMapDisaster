import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import DecisionReviewPanel from '../components/AIDecisions/DecisionReviewPanel';
import { aiDecisionService } from '../services/aiDecisionService';

vi.mock('../services/aiDecisionService', () => ({
  aiDecisionService: {
    listDecisions: vi.fn(),
    generateDecisions: vi.fn(),
    approveDecision: vi.fn(),
    rejectDecision: vi.fn(),
    executeDecision: vi.fn(),
    getExplanation: vi.fn(),
  },
}));

describe('DecisionReviewPanel Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders header, title, and filter pills correctly', async () => {
    aiDecisionService.listDecisions.mockResolvedValueOnce({
      data: { items: [], total: 0 },
    });

    render(<DecisionReviewPanel />);

    expect(screen.getByText(/AI Tactical Decision Review/i)).toBeInTheDocument();
    expect(screen.getByText(/Human-in-the-Loop decision review/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Generate Decisions/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^ALL$/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /REVIEW REQUIRED/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^APPROVED$/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^EXECUTED$/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^REJECTED$/i })).toBeInTheDocument();
    });
  });

  it('renders empty state when no decisions exist', async () => {
    aiDecisionService.listDecisions.mockResolvedValueOnce({
      data: { items: [], total: 0 },
    });

    render(<DecisionReviewPanel />);

    await waitFor(() => {
      expect(screen.getByText(/No AI Decisions Pending/i)).toBeInTheDocument();
    });
  });

  it('renders decision cards with priority, action directive, and metrics when data is present', async () => {
    const mockDecisions = [
      {
        id: 101,
        decision_uuid: 'dec-101-uuid',
        priority: 'CRITICAL',
        status: 'REVIEW_REQUIRED',
        decision_type: 'MASS_CASUALTY_TRIAGE',
        policy_name: 'OPTIMIZED',
        confidence: 0.94,
        score: 0.88,
        action: { directive: 'Dispatch 2 triage ambulances to Sector 17' },
        reasoning: ['Casualty count exceeded threshold', 'Hospital ICU load at 40%'],
      },
    ];

    aiDecisionService.listDecisions.mockResolvedValueOnce({
      data: { items: mockDecisions, total: 1 },
    });

    render(<DecisionReviewPanel />);

    await waitFor(() => {
      expect(screen.getByText(/MASS_CASUALTY_TRIAGE/i)).toBeInTheDocument();
      expect(screen.getByText(/CRITICAL/i)).toBeInTheDocument();
      expect(screen.getByText(/REVIEW_REQUIRED/i)).toBeInTheDocument();
      expect(screen.getByText(/94%/i)).toBeInTheDocument();
      expect(screen.getByText(/88%/i)).toBeInTheDocument();
      expect(screen.getByText(/Dispatch 2 triage ambulances to Sector 17/i)).toBeInTheDocument();
      expect(screen.getByText(/Casualty count exceeded threshold/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Approve & Dispatch/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /✕ Reject/i })).toBeInTheDocument();
    });
  });

  it('handles error state and allows retry', async () => {
    aiDecisionService.listDecisions.mockRejectedValueOnce(new Error('PostgreSQL connection failed'));

    render(<DecisionReviewPanel />);

    await waitFor(() => {
      expect(screen.getByText(/Error loading decisions:/i)).toBeInTheDocument();
      expect(screen.getByText(/PostgreSQL connection failed/i)).toBeInTheDocument();
    });

    // Mock success for retry
    aiDecisionService.listDecisions.mockResolvedValueOnce({
      data: { items: [], total: 0 },
    });

    const retryBtn = screen.getByRole('button', { name: /Retry/i });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.queryByText(/PostgreSQL connection failed/i)).not.toBeInTheDocument();
      expect(screen.getByText(/No AI Decisions Pending/i)).toBeInTheDocument();
    });
  });
});
