"""Simulation Engine Unit Tests."""

import asyncio

import pytest

from app.modules.simulation.engine import DigitalTwinEngine
from app.modules.simulation.schemas import CitizenStatus, SimulationConfig


@pytest.fixture(autouse=True)
def reset_engine():
    """Reset the simulation engine before each test for isolation."""
    engine = DigitalTwinEngine()
    engine.reset()
    yield
    engine.reset()


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestEngineInitialization:
    def test_singleton_pattern(self):
        e1 = DigitalTwinEngine()
        e2 = DigitalTwinEngine()
        assert e1 is e2

    def test_initial_tick_count_zero(self):
        from app.modules.simulation.engine import engine
        assert engine.tick_count == 0

    def test_initial_not_running(self):
        from app.modules.simulation.engine import engine
        assert engine.is_running is False

    def test_citizens_initialized(self):
        from app.modules.simulation.engine import engine
        assert len(engine.citizens) >= 100

    def test_buildings_initialized(self):
        from app.modules.simulation.engine import engine
        assert len(engine.buildings) >= 5

    def test_roads_initialized(self):
        from app.modules.simulation.engine import engine
        assert len(engine.roads) >= 3


class TestTickProcessing:
    def test_tick_increments_counter(self):
        from app.modules.simulation.engine import engine
        _run(engine.tick())
        assert engine.tick_count == 1

    def test_multiple_ticks(self):
        from app.modules.simulation.engine import engine
        for _ in range(5):
            _run(engine.tick())
        assert engine.tick_count == 5

    def test_tick_returns_state(self):
        from app.modules.simulation.engine import engine
        from app.modules.simulation.schemas import DigitalTwinCityState
        state = _run(engine.tick())
        assert isinstance(state, DigitalTwinCityState)

    def test_tick_state_has_citizens(self):
        from app.modules.simulation.engine import engine
        state = _run(engine.tick())
        assert state.total_citizens > 0

    def test_event_log_grows_with_ticks(self):
        from app.modules.simulation.engine import engine
        _run(engine.tick())
        events = engine.get_event_log()
        assert len(events) > 0


class TestDisasterProximity:
    def test_add_disaster_increments_count(self):
        from app.modules.simulation.engine import engine
        engine.force_add_disaster(30.7415, 76.7785, "CRITICAL")
        assert engine.active_disasters_count == 1

    def test_multiple_disasters_accumulate(self):
        from app.modules.simulation.engine import engine
        engine.force_add_disaster(30.7415, 76.7785, "CRITICAL")
        engine.force_add_disaster(30.7330, 76.7850, "HIGH")
        assert engine.active_disasters_count == 2

    def test_citizen_can_become_endangered_near_disaster(self):
        from app.modules.simulation.engine import engine
        # Add disaster very close to citizen cluster center
        engine.force_add_disaster(30.7399, 76.7830, "CRITICAL")
        # Run several ticks to allow state transitions
        for _ in range(10):
            _run(engine.tick())
        endangered = sum(
            1 for c in engine.citizens
            if c.status in (CitizenStatus.ENDANGERED, CitizenStatus.EVACUATING, CitizenStatus.INJURED)
        )
        # At least some citizens should have been affected
        assert endangered > 0


class TestConfigUpdate:
    def test_update_weather_multiplier(self):
        from app.modules.simulation.engine import engine
        config = SimulationConfig(weather_multiplier=3.0)
        engine.update_config(config)
        assert engine.config["weather_multiplier"] == 3.0

    def test_update_panic_factor(self):
        from app.modules.simulation.engine import engine
        config = SimulationConfig(citizen_panic_factor=2.5)
        engine.update_config(config)
        assert engine.config["citizen_panic_factor"] == 2.5

    def test_auto_spawn_incidents_flag(self):
        from app.modules.simulation.engine import engine
        config = SimulationConfig(auto_spawn_incidents=True)
        engine.update_config(config)
        assert engine.config["auto_spawn_incidents"] is True


class TestReset:
    def test_reset_clears_tick_count(self):
        from app.modules.simulation.engine import engine
        _run(engine.tick())
        _run(engine.tick())
        engine.reset()
        assert engine.tick_count == 0

    def test_reset_clears_disasters(self):
        from app.modules.simulation.engine import engine
        engine.force_add_disaster(30.7415, 76.7785, "HIGH")
        engine.reset()
        assert engine.active_disasters_count == 0

    def test_reset_clears_event_log(self):
        from app.modules.simulation.engine import engine
        _run(engine.tick())
        engine.reset()
        # After reset, event log should only have the reset event
        events = engine.get_event_log()
        assert all("reset" in e.description.lower() for e in events)
