from __future__ import annotations

import argparse
from pathlib import Path

from biogears_sim.comparison_runner import ComparisonRunner
from biogears_sim.scenario_parser import load_scenarios
from biogears_sim.scenario_runner import ScenarioRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run BioGears scenario integrations and comparison studies.")
    parser.add_argument("--backend", choices=["auto", "biogears", "fallback"], default="auto")
    parser.add_argument("--patients-dir", type=str, default="patients")
    parser.add_argument("--output-dir", type=str, default="outputs")
    parser.add_argument("--max-duration-s", type=int, default=None, help="Optional cap per scenario to limit runtime")

    subparsers = parser.add_subparsers(dest="command", required=True)

    run_one = subparsers.add_parser("scenario", help="Run one scenario by name")
    run_one.add_argument("name", type=str)

    subparsers.add_parser("all", help="Run all discovered scenarios")
    subparsers.add_parser("compare", help="Run the default comparison pairs")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    patients_dir = Path(args.patients_dir)
    output_dir = Path(args.output_dir)
    scenarios = load_scenarios(patients_dir)

    if args.command == "scenario":
        if args.name not in scenarios:
            available = ", ".join(sorted(scenarios.keys()))
            raise SystemExit(f"Unknown scenario '{args.name}'. Available: {available}")
        runner = ScenarioRunner(output_dir=output_dir, backend_mode=args.backend, max_duration_s=args.max_duration_s)
        result = runner.run_scenario(scenarios[args.name])
        print(f"Scenario complete: {result.scenario_name}")
        print(f"Metrics: {result.metrics_file}")
        print(f"Action audit CSV: {result.action_audit_csv}")
        print(f"Action audit JSON: {result.action_audit_json}")
        print(f"Data requests: {result.data_request_manifest}")
        return

    if args.command == "all":
        runner = ScenarioRunner(output_dir=output_dir, backend_mode=args.backend, max_duration_s=args.max_duration_s)
        for name in sorted(scenarios.keys()):
            result = runner.run_scenario(scenarios[name])
            print(f"Completed {result.scenario_name}: {result.metrics_file}")
        return

    if args.command == "compare":
        runner = ComparisonRunner(output_dir=output_dir, backend_mode=args.backend, max_duration_s=args.max_duration_s)
        results = runner.run_default_pairs(scenarios)
        for result in results:
            print(f"Comparison {result.scenario_a} vs {result.scenario_b}: {result.file_path}")
        return

    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()

