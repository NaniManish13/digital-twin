import tempfile
from pathlib import Path
import unittest

from biogears_sim.scenario_parser import load_scenarios
from biogears_sim.scenario_runner import ScenarioRunner


class TestScenarioRunner(unittest.TestCase):
    def test_runs_single_scenario_and_writes_outputs(self) -> None:
        scenarios = load_scenarios(Path("C:/Users/Dell/digital_twin/patients"))
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = ScenarioRunner(output_dir=Path(temp_dir), backend_mode="fallback", max_duration_s=120)
            result = runner.run_scenario(scenarios["HemorrhageClass2Blood"])
            self.assertTrue(result.metrics_file.exists())
            self.assertTrue(result.action_audit_csv.exists())
            self.assertTrue(result.action_audit_json.exists())
            self.assertTrue(result.data_request_manifest.exists())
            self.assertGreater(len(result.rows), 0)
            self.assertGreater(len(result.actions), 0)


if __name__ == "__main__":
    unittest.main()

