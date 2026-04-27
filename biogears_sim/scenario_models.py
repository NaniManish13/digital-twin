from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ActionScalar:
    value: float
    unit: str | None = None


@dataclass(frozen=True)
class ScenarioAction:
    action_type: str
    timestamp_s: int
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DataRequestSpec:
    category: str
    name: str
    unit: str | None
    precision: int | None
    compartment: str | None = None
    substance: str | None = None


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_name: str
    scenario_file: str
    patient_file: str | None
    engine_state_file: str | None
    samples_per_second: float | None
    timeline_duration_s: int
    actions: tuple[ScenarioAction, ...]
    xml_data_requests: tuple[DataRequestSpec, ...]
    required_data_requests: tuple[DataRequestSpec, ...]

