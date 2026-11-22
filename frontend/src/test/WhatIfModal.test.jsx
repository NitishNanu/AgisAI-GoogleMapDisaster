import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import WhatIfModal from '../components/Simulation/WhatIfModal';
import simulationService from '../services/simulationService';

vi.mock('../services/simulationService', () => ({
  default: {
    runWhatIf: vi.fn(),
  },
}));

describe('WhatIfModal Component', () => {
  it('renders nothing when isOpen is false', () => {
    const { container } = render(<WhatIfModal isOpen={false} onClose={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('handles missing backend outcome data gracefully without showing fake 92/18/40 fallback values', async () => {
    // Backend returns success true but missing outcome objects
    simulationService.runWhatIf.mockResolvedValueOnce({
      success: true,
      baseline_outcome: null,
      intervened_outcome: null,
    });

    render(<WhatIfModal isOpen={true} onClose={() => {}} />);

    // Click submit button
    const submitBtn = screen.getByRole('button', { name: /Execute Comparative Sandbox/i });
    fireEvent.click(submitBtn);

    // Wait for the explicit error banner
    await waitFor(() => {
      expect(
        screen.getByText(/Comparative simulation outcome data unavailable from backend engine/i)
      ).toBeInTheDocument();
    });

    // Ensure fallback numbers 92, 18, 40 are NOT present in document
    expect(screen.queryByText('92')).not.toBeInTheDocument();
    expect(screen.queryByText('18')).not.toBeInTheDocument();
    expect(screen.queryByText('40')).not.toBeInTheDocument();
  });

  it('renders real outcome data correctly when backend returns outcomes', async () => {
    simulationService.runWhatIf.mockResolvedValueOnce({
      success: true,
      baseline_outcome: {
        safe_citizens: 55,
        injured_citizens: 30,
        endangered_citizens: 65,
      },
      intervened_outcome: {
        safe_citizens: 120,
        injured_citizens: 5,
        endangered_citizens: 10,
      },
    });

    render(<WhatIfModal isOpen={true} onClose={() => {}} />);

    const submitBtn = screen.getByRole('button', { name: /Execute Comparative Sandbox/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('55')).toBeInTheDocument();
      expect(screen.getByText('30')).toBeInTheDocument();
      expect(screen.getByText('65')).toBeInTheDocument();
      expect(screen.getByText('120')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('10')).toBeInTheDocument();
    });
  });
});
