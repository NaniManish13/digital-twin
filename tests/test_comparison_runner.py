import tempfile
from pathlib import Path
import unittest

from biogears_sim.comparison_runner import ComparisonRunner
from biogears_sim.scenario_parser import load_scenarios


class TestComparisonRunner(unittest.TestCase):
    def test_runs_default_pairs(self) -> None:
        scenarios = load_scenarios(Path("C:/Users/Dell/digital_twin/patients"))
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = ComparisonRunner(output_dir=Path(temp_dir), backend_mode="fallback", max_duration_s=120)
            results = runner.run_default_pairs(scenarios)
            self.assertEqual(len(results), 5)
            for result in results:
                self.assertTrue(result.file_path.exists())


if __name__ == "__main__":
    unittest.main()

