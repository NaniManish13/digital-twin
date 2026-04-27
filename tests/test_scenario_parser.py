from pathlib import Path
import unittest

from biogears_sim.scenario_parser import load_scenarios


class TestScenarioParser(unittest.TestCase):
    def test_loads_all_patient_scenarios(self) -> None:
        scenarios = load_scenarios(Path("C:/Users/Dell/digital_twin/patients"))
        self.assertEqual(len(scenarios), 33)
        self.assertIn("Medic1Scenario4", scenarios)

    def test_medic4_extracts_bolus_action(self) -> None:
        scenarios = load_scenarios(Path("C:/Users/Dell/digital_twin/patients"))
        scenario = scenarios["Medic1Scenario4"]
        bolus_actions = [a for a in scenario.actions if a.action_type == "SubstanceBolusData"]
        self.assertEqual(len(bolus_actions), 1)
        self.assertEqual(bolus_actions[0].timestamp_s, 30)
        self.assertEqual(bolus_actions[0].payload.get("Substance"), "Succinylcholine")


if __name__ == "__main__":
    unittest.main()

