from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .scenario_models import ScenarioAction


@dataclass(frozen=True)
class ActionRecord:
    time_s: int
    scenario_name: str
    action_type: str
    status: str
    detail: str
    payload: dict[str, Any]


def _as_scalar(payload_value: Any) -> tuple[float | None, str | None]:
    if isinstance(payload_value, dict):
        value = payload_value.get("value")
        unit = payload_value.get("unit")
        return (float(value) if value is not None else None, unit)
    if payload_value is None:
        return None, None
    return float(payload_value), None


class ActionDispatcher:
    def __init__(self, backend: Any, scenario_name: str) -> None:
        self._backend = backend
        self._scenario_name = scenario_name

    def _dispatch_payload(self, action: ScenarioAction) -> dict[str, Any]:
        payload = dict(action.payload)
        if action.action_type == "HemorrhageData":
            rate, unit = _as_scalar(payload.get("InitialRate"))
            duration, duration_unit = _as_scalar(payload.get("BleedingDuration"))
            return {
                "compartment": payload.get("Compartment", "Aorta"),
                "rate": rate or 0.0,
                "rate_unit": unit or "mL/min",
                "duration": duration,
                "duration_unit": duration_unit or "s",
            }
        if action.action_type in ("SubstanceInfusionData", "SubstanceBolusData"):
            dose, dose_unit = _as_scalar(payload.get("Dose"))
            conc, conc_unit = _as_scalar(payload.get("Concentration"))
            rate, rate_unit = _as_scalar(payload.get("Rate"))
            return {
                "substance": payload.get("Substance"),
                "admin_route": payload.get("AdminRoute"),
                "dose": dose,
                "dose_unit": dose_unit,
                "concentration": conc,
                "concentration_unit": conc_unit,
                "rate": rate,
                "rate_unit": rate_unit,
            }
        if action.action_type == "SubstanceCompoundInfusionData":
            bag_volume, bag_unit = _as_scalar(payload.get("BagVolume"))
            rate, rate_unit = _as_scalar(payload.get("Rate"))
            return {
                "compound": payload.get("SubstanceCompound"),
                "bag_volume": bag_volume,
                "bag_unit": bag_unit,
                "rate": rate,
                "rate_unit": rate_unit,
            }
        return payload

    def inject(self, time_s: int, action: ScenarioAction) -> ActionRecord:
        mapped_payload = self._dispatch_payload(action)
        try:
            self._backend.apply_action(action.action_type, mapped_payload)
            return ActionRecord(
                time_s=time_s,
                scenario_name=self._scenario_name,
                action_type=action.action_type,
                status="APPLIED",
                detail="Action accepted by backend",
                payload=mapped_payload,
            )
        except NotImplementedError as exc:
            return ActionRecord(
                time_s=time_s,
                scenario_name=self._scenario_name,
                action_type=action.action_type,
                status="UNSUPPORTED",
                detail=str(exc),
                payload=mapped_payload,
            )
        except Exception as exc:
            return ActionRecord(
                time_s=time_s,
                scenario_name=self._scenario_name,
                action_type=action.action_type,
                status="ERROR",
                detail=str(exc),
                payload=mapped_payload,
            )

