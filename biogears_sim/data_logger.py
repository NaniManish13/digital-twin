from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Iterable

from .actions import ActionRecord


@dataclass(frozen=True)
class MetricRow:
    scenario_name: str
    patient_file: str
    simulation_time_seconds: int
    heart_rate_bpm: float
    systolic_bp_mmhg: float
    diastolic_bp_mmhg: float
    map_mmhg: float
    cardiac_output_l_min: float
    stroke_volume_ml: float
    blood_volume_l: float
    systemic_vascular_resistance: float
    spo2: float
    cvp_mmhg: float
    clinical_state: str


class DataLogger:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_metrics(self, scenario_name: str, rows: Iterable[MetricRow]) -> Path:
        rows = list(rows)
        output_file = self.output_dir / f"{scenario_name}_metrics.csv"
        with output_file.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()) if rows else [
                "scenario_name", "patient_file", "simulation_time_seconds", "heart_rate_bpm", "systolic_bp_mmhg",
                "diastolic_bp_mmhg", "map_mmhg", "cardiac_output_l_min", "stroke_volume_ml", "blood_volume_l",
                "systemic_vascular_resistance", "spo2", "cvp_mmhg", "clinical_state",
            ])
            writer.writeheader()
            for row in rows:
                writer.writerow(asdict(row))
        return output_file

    def write_action_audit(self, scenario_name: str, actions: Iterable[ActionRecord]) -> tuple[Path, Path]:
        actions = list(actions)
        csv_file = self.output_dir / f"{scenario_name}_action_audit.csv"
        with csv_file.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["time_s", "scenario_name", "action_type", "status", "detail", "payload"])
            writer.writeheader()
            for record in actions:
                writer.writerow(
                    {
                        "time_s": record.time_s,
                        "scenario_name": record.scenario_name,
                        "action_type": record.action_type,
                        "status": record.status,
                        "detail": record.detail,
                        "payload": json.dumps(record.payload, sort_keys=True),
                    }
                )

        json_file = self.output_dir / f"{scenario_name}_action_audit.json"
        with json_file.open("w", encoding="utf-8") as handle:
            json.dump([
                {
                    "time_s": record.time_s,
                    "scenario_name": record.scenario_name,
                    "action_type": record.action_type,
                    "status": record.status,
                    "detail": record.detail,
                    "payload": record.payload,
                }
                for record in actions
            ], handle, indent=2)
        return csv_file, json_file

