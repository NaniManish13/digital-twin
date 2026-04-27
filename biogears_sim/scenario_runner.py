from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .actions import ActionDispatcher, ActionRecord
from .data_logger import DataLogger, MetricRow
from .engine import SimulationController, create_backend
from .scenario_models import ScenarioDefinition


@dataclass(frozen=True)
class ScenarioRunResult:
    scenario_name: str
    metrics_file: Path
    action_audit_csv: Path
    action_audit_json: Path
    data_request_manifest: Path
    rows: tuple[MetricRow, ...]
    actions: tuple[ActionRecord, ...]


def _clinical_state(
    hr: float,
    map_mmhg: float,
    spo2: float,
    co: float,
    baseline_bv: float,
    current_bv: float,
) -> str:
    bv_loss = 0.0 if baseline_bv <= 0.0 else max(0.0, (baseline_bv - current_bv) / baseline_bv)
    if map_mmhg < 50.0 or spo2 < 0.85 or bv_loss > 0.40 or co < 2.0:
        return "CRITICAL"
    if hr > 130.0 or hr < 50.0 or (50.0 <= map_mmhg < 60.0) or (0.85 <= spo2 < 0.90) or (0.30 <= bv_loss <= 0.40):
        return "DECOMPENSATING"
    if (100.0 <= hr <= 130.0) or (60.0 <= map_mmhg < 70.0) or (0.90 <= spo2 < 0.95) or (0.15 <= bv_loss < 0.30):
        return "COMPENSATING"
    if (60.0 <= hr <= 100.0) and (70.0 <= map_mmhg <= 105.0) and spo2 >= 0.95 and bv_loss <= 0.05:
        return "NORMAL"
    return "COMPENSATING"


class ScenarioRunner:
    def __init__(self, output_dir: Path, backend_mode: str = "auto", max_duration_s: int | None = None) -> None:
        self.output_dir = output_dir
        self.backend_mode = backend_mode
        self.max_duration_s = max_duration_s
        self.logger = DataLogger(output_dir)

    def _write_data_request_manifest(self, definition: ScenarioDefinition) -> Path:
        output_file = self.output_dir / f"{definition.scenario_name}_data_requests.csv"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w", encoding="utf-8") as handle:
            handle.write("category,name,unit,precision,compartment,substance\n")
            for req in definition.required_data_requests:
                handle.write(
                    f"{req.category},{req.name},{req.unit or ''},{req.precision if req.precision is not None else ''},{req.compartment or ''},{req.substance or ''}\n"
                )
        return output_file

    def run_scenario(self, definition: ScenarioDefinition) -> ScenarioRunResult:
        patient_state_file = definition.engine_state_file
        standard_patient = definition.patient_file or "StandardMale.xml"
        if patient_state_file:
            standard_patient = "StandardMale"

        backend = create_backend(
            mode=self.backend_mode,
            patient_state_file=patient_state_file,
            standard_patient=standard_patient,
        )
        controller = SimulationController(backend)
        dispatcher = ActionDispatcher(backend, definition.scenario_name)

        if not backend.is_ready():
            raise RuntimeError(f"Backend is not ready for scenario: {definition.scenario_name}")

        actions_by_time: dict[int, list] = {}
        for action in definition.actions:
            actions_by_time.setdefault(action.timestamp_s, []).append(action)

        action_records: list[ActionRecord] = []
        metric_rows: list[MetricRow] = []
        baseline_bv: float | None = None
        end_time = max(1, definition.timeline_duration_s)
        if self.max_duration_s is not None:
            end_time = min(end_time, self.max_duration_s)

        for current_time in range(0, end_time):
            for action in actions_by_time.get(current_time, []):
                action_records.append(dispatcher.inject(current_time, action))

            vitals = controller.step(1.0)
            if baseline_bv is None:
                baseline_bv = vitals.blood_volume_l if vitals.blood_volume_l == vitals.blood_volume_l else 5.0

            state = _clinical_state(
                hr=vitals.heart_rate_bpm,
                map_mmhg=vitals.mean_arterial_pressure_mmhg,
                spo2=vitals.spo2_fraction,
                co=vitals.cardiac_output_l_min,
                baseline_bv=baseline_bv,
                current_bv=vitals.blood_volume_l,
            )
            metric_rows.append(
                MetricRow(
                    scenario_name=definition.scenario_name,
                    patient_file=definition.patient_file or definition.engine_state_file or "Unknown",
                    simulation_time_seconds=int(round(vitals.time_s)),
                    heart_rate_bpm=vitals.heart_rate_bpm,
                    systolic_bp_mmhg=vitals.systolic_bp_mmhg,
                    diastolic_bp_mmhg=vitals.diastolic_bp_mmhg,
                    map_mmhg=vitals.mean_arterial_pressure_mmhg,
                    cardiac_output_l_min=vitals.cardiac_output_l_min,
                    stroke_volume_ml=vitals.stroke_volume_ml,
                    blood_volume_l=vitals.blood_volume_l,
                    systemic_vascular_resistance=vitals.systemic_vascular_resistance,
                    spo2=vitals.spo2_fraction,
                    cvp_mmhg=vitals.central_venous_pressure_mmhg,
                    clinical_state=state,
                )
            )

        metrics_file = self.logger.write_metrics(definition.scenario_name, metric_rows)
        action_audit_csv, action_audit_json = self.logger.write_action_audit(definition.scenario_name, action_records)
        manifest_file = self._write_data_request_manifest(definition)

        return ScenarioRunResult(
            scenario_name=definition.scenario_name,
            metrics_file=metrics_file,
            action_audit_csv=action_audit_csv,
            action_audit_json=action_audit_json,
            data_request_manifest=manifest_file,
            rows=tuple(metric_rows),
            actions=tuple(action_records),
        )

