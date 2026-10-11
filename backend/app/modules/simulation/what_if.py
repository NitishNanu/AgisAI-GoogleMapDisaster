import copy
import random

import structlog
from pydantic import BaseModel, Field

from app.modules.simulation.schemas import (
    BuildingState,
    CitizenState,
    CitizenStatus,
    RoadSegment,
    WeatherCondition,
)

logger = structlog.get_logger("aegis_ai.simulation.what_if")


class WhatIfScenarioConfig(BaseModel):
    name: str = Field(default="Optimized Scenario", description="Scenario label")
    strategy: str = Field(
        default="AI_DYNAMIC_EVACUATION",
        description="Strategy: BASELINE | AI_DYNAMIC_EVACUATION | PREEMPTIVE_SHELTER | AGGRESSIVE_DISPATCH",
    )
    evacuation_speed_multiplier: float = Field(default=1.5, ge=0.5, le=5.0)
    panic_reduction_factor: float = Field(default=0.7, ge=0.1, le=2.0)
    shelter_capacity_multiplier: float = Field(default=1.2, ge=1.0, le=3.0)
    dispatch_priority_weight: float = Field(default=1.5, ge=0.5, le=3.0)


class WhatIfTimelineStep(BaseModel):
    tick: int
    safe_citizens: int
    endangered_citizens: int
    evacuating_citizens: int
    injured_citizens: int
    rescued_citizens: int
    damaged_buildings: int
    hospital_bed_occupancy_rate: float


class WhatIfScenarioResult(BaseModel):
    scenario_name: str
    strategy: str
    final_safe_citizens: int
    final_casualties: int
    final_rescued: int
    peak_injured: int
    timeline: list[WhatIfTimelineStep]
    score: float


class WhatIfComparisonResponse(BaseModel):
    baseline_scenario: WhatIfScenarioResult
    intervened_scenario: WhatIfScenarioResult
    casualty_reduction_count: int
    casualty_reduction_percentage: float
    evacuation_acceleration_score: float
    executive_recommendation: str
    recommended_strategy: str


class WhatIfEngine:
    @staticmethod
    def _simulate_tick(
        citizens: list[CitizenState],
        buildings: list[BuildingState],
        roads: list[RoadSegment],
        weather: WeatherCondition,
        strategy: str,
        config: WhatIfScenarioConfig,
        tick_num: int,
        rng: random.Random,
    ) -> WhatIfTimelineStep:
        for citizen in citizens:
            if citizen.status == CitizenStatus.SAFE:
                if rng.random() < (0.02 * config.panic_reduction_factor):
                    citizen.status = CitizenStatus.ENDANGERED
            elif citizen.status == CitizenStatus.ENDANGERED:
                if strategy in ("AI_DYNAMIC_EVACUATION", "PREEMPTIVE_SHELTER"):
                    if rng.random() < (0.45 * config.evacuation_speed_multiplier):
                        citizen.status = CitizenStatus.EVACUATING
                else:
                    if rng.random() < 0.20:
                        citizen.status = CitizenStatus.EVACUATING
                    elif rng.random() < 0.15:
                        citizen.status = CitizenStatus.INJURED
            elif citizen.status == CitizenStatus.EVACUATING:
                rescue_prob = 0.35 if strategy == "AGGRESSIVE_DISPATCH" else 0.25
                if rng.random() < (rescue_prob * config.evacuation_speed_multiplier):
                    citizen.status = CitizenStatus.RESCUED
                elif rng.random() < (0.08 * config.panic_reduction_factor):
                    citizen.status = CitizenStatus.INJURED
            elif citizen.status == CitizenStatus.INJURED:
                if rng.random() < 0.20:
                    citizen.status = CitizenStatus.RESCUED

        safe_c = sum(1 for c in citizens if c.status == CitizenStatus.SAFE)
        endangered_c = sum(1 for c in citizens if c.status == CitizenStatus.ENDANGERED)
        evacuating_c = sum(1 for c in citizens if c.status == CitizenStatus.EVACUATING)
        injured_c = sum(1 for c in citizens if c.status == CitizenStatus.INJURED)
        rescued_c = sum(1 for c in citizens if c.status == CitizenStatus.RESCUED)
        damaged_b = sum(1 for b in buildings if b.is_damaged)

        return WhatIfTimelineStep(
            tick=tick_num,
            safe_citizens=safe_c,
            endangered_citizens=endangered_c,
            evacuating_citizens=evacuating_c,
            injured_citizens=injured_c,
            rescued_citizens=rescued_c,
            damaged_buildings=damaged_b,
            hospital_bed_occupancy_rate=round(min(1.0, (injured_c * 1.5) / 1000.0), 2),
        )

    @classmethod
    def run_comparison(
        cls,
        base_citizens: list[CitizenState],
        base_buildings: list[BuildingState],
        base_roads: list[RoadSegment],
        base_weather: WeatherCondition,
        intervened_config: WhatIfScenarioConfig,
        ticks_to_simulate: int = 15,
        random_seed: int = 42,
    ) -> WhatIfComparisonResponse:
        baseline_config = WhatIfScenarioConfig(
            name="Standard Baseline Response",
            strategy="BASELINE",
            evacuation_speed_multiplier=1.0,
            panic_reduction_factor=1.0,
            shelter_capacity_multiplier=1.0,
            dispatch_priority_weight=1.0,
        )

        # 1. Run Baseline Scenario
        rng_base = random.Random(random_seed)
        citizens_base = [copy.deepcopy(c) for c in base_citizens]
        buildings_base = [copy.deepcopy(b) for b in base_buildings]
        roads_base = [copy.deepcopy(r) for r in base_roads]
        weather_base = copy.deepcopy(base_weather)

        timeline_base: list[WhatIfTimelineStep] = []
        for t in range(1, ticks_to_simulate + 1):
            step = cls._simulate_tick(
                citizens_base, buildings_base, roads_base, weather_base,
                "BASELINE", baseline_config, t, rng_base
            )
            timeline_base.append(step)

        final_base = timeline_base[-1]
        base_score = round(
            (final_base.rescued_citizens + final_base.safe_citizens)
            / max(1, len(base_citizens)) * 100.0,
            1,
        )

        result_base = WhatIfScenarioResult(
            scenario_name=baseline_config.name,
            strategy=baseline_config.strategy,
            final_safe_citizens=final_base.safe_citizens,
            final_casualties=final_base.injured_citizens,
            final_rescued=final_base.rescued_citizens,
            peak_injured=max(step.injured_citizens for step in timeline_base),
            timeline=timeline_base,
            score=base_score,
        )

        # 2. Run Intervened Scenario
        rng_inter = random.Random(random_seed)
        citizens_inter = [copy.deepcopy(c) for c in base_citizens]
        buildings_inter = [copy.deepcopy(b) for b in base_buildings]
        roads_inter = [copy.deepcopy(r) for r in base_roads]
        weather_inter = copy.deepcopy(base_weather)

        timeline_inter: list[WhatIfTimelineStep] = []
        for t in range(1, ticks_to_simulate + 1):
            step = cls._simulate_tick(
                citizens_inter, buildings_inter, roads_inter, weather_inter,
                intervened_config.strategy, intervened_config, t, rng_inter
            )
            timeline_inter.append(step)

        final_inter = timeline_inter[-1]
        inter_score = round(
            (final_inter.rescued_citizens + final_inter.safe_citizens)
            / max(1, len(base_citizens)) * 100.0,
            1,
        )

        result_inter = WhatIfScenarioResult(
            scenario_name=intervened_config.name,
            strategy=intervened_config.strategy,
            final_safe_citizens=final_inter.safe_citizens,
            final_casualties=final_inter.injured_citizens,
            final_rescued=final_inter.rescued_citizens,
            peak_injured=max(step.injured_citizens for step in timeline_inter),
            timeline=timeline_inter,
            score=inter_score,
        )

        # 3. Calculate Differential Analytics
        casualty_diff = max(0, result_base.final_casualties - result_inter.final_casualties)
        pct_reduction = (
            round((casualty_diff / max(1, result_base.final_casualties)) * 100.0, 1)
            if result_base.final_casualties > 0
            else 0.0
        )
        acceleration_score = round(
            (result_inter.final_rescued / max(1, result_base.final_rescued + 1)) * 1.2, 2
        )

        recommendation = (
            f"Strategy '{intervened_config.name}' yields a {pct_reduction}% reduction in casualties "
            f"and improves evacuation throughput by factor {acceleration_score}x compared to standard baseline."
        )

        return WhatIfComparisonResponse(
            baseline_scenario=result_base,
            intervened_scenario=result_inter,
            casualty_reduction_count=casualty_diff,
            casualty_reduction_percentage=pct_reduction,
            evacuation_acceleration_score=acceleration_score,
            executive_recommendation=recommendation,
            recommended_strategy=intervened_config.strategy,
        )
