from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .scenario_models import ScenarioDefinition
from .scenario_runner import ScenarioRunner


DEFAULT_COMPARISON_PAIRS: tuple[tuple[str, str], ...] = (
    ("HemorrhageClass2NoFluid", "HemorrhageClass2Blood"),
    ("HemorrhageClass2Saline", "HemorrhageClass2Blood"),
    ("SepticShock", "SepticShock_Treatment"),
    ("SinusBradycardia", "SinusTachycardia"),
    ("RenalStenosisModerateUnilateral", "RenalStenosisSevereBilateral"),
)


@dataclass(frozen=True)
class ComparisonResult:
    scenario_a: str
    scenario_b: str
    file_path: Path


class ComparisonRunner:
    def __init__(self, output_dir: Path, backend_mode: str = "auto", max_duration_s: int | None = None) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.scenario_runner = ScenarioRunner(output_dir=output_dir, backend_mode=backend_mode, max_duration_s=max_duration_s)

    def _write_pair_csv(self, scenario_a: str, scenario_b: str, rows_a: dict[int, dict], rows_b: dict[int, dict]) -> Path:
        out_file = self.output_dir / f"comparison_{scenario_a}_vs_{scenario_b}.csv"
        metrics = ("heart_rate_bpm", "map_mmhg", "cardiac_output_l_min", "blood_volume_l", "systemic_vascular_resistance")

        all_times = sorted(set(rows_a.keys()) | set(rows_b.keys()))
        fieldnames = ["time_s"]
        for metric in metrics:
            fieldnames.extend([
                f"scenario_A_{metric}",
                f"scenario_B_{metric}",
                f"delta_{metric}",
            ])

        with out_file.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for time_s in all_times:
                row = {"time_s": time_s}
                a = rows_a.get(time_s)
                b = rows_b.get(time_s)
                for metric in metrics:
                    a_val = a.get(metric) if a else None
                    b_val = b.get(metric) if b else None
                    row[f"scenario_A_{metric}"] = a_val
                    row[f"scenario_B_{metric}"] = b_val
                    row[f"delta_{metric}"] = (a_val - b_val) if (a_val is not None and b_val is not None) else None
                writer.writerow(row)
        return out_file

    def run_pair(self, definition_a: ScenarioDefinition, definition_b: ScenarioDefinition) -> ComparisonResult:
        result_a = self.scenario_runner.run_scenario(definition_a)
        result_b = self.scenario_runner.run_scenario(definition_b)

        rows_a = {
            row.simulation_time_seconds: {
                "heart_rate_bpm": row.heart_rate_bpm,
                "map_mmhg": row.map_mmhg,
                "cardiac_output_l_min": row.cardiac_output_l_min,
                "blood_volume_l": row.blood_volume_l,
                "systemic_vascular_resistance": row.systemic_vascular_resistance,
            }
            for row in result_a.rows
        }
        rows_b = {
            row.simulation_time_seconds: {
                "heart_rate_bpm": row.heart_rate_bpm,
                "map_mmhg": row.map_mmhg,
                "cardiac_output_l_min": row.cardiac_output_l_min,
                "blood_volume_l": row.blood_volume_l,
                "systemic_vascular_resistance": row.systemic_vascular_resistance,
            }
            for row in result_b.rows
        }

        output = self._write_pair_csv(definition_a.scenario_name, definition_b.scenario_name, rows_a, rows_b)
        return ComparisonResult(definition_a.scenario_name, definition_b.scenario_name, output)

    def run_default_pairs(self, scenarios: dict[str, ScenarioDefinition]) -> list[ComparisonResult]:
        results: list[ComparisonResult] = []
        for scenario_a, scenario_b in DEFAULT_COMPARISON_PAIRS:
            if scenario_a not in scenarios or scenario_b not in scenarios:
                continue
            results.append(self.run_pair(scenarios[scenario_a], scenarios[scenario_b]))
        return results

