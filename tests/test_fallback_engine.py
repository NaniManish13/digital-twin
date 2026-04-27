import unittest

from biogears_sim.engine import FallbackCardiovascularBackend


class TestFallbackCardiovascularBackend(unittest.TestCase):
    def test_baseline_ranges(self) -> None:
        engine = FallbackCardiovascularBackend()
        v = engine.step(1.0)
        self.assertTrue(40 <= v.heart_rate_bpm <= 120)
        self.assertTrue(80 <= v.systolic_bp_mmhg <= 140)
        self.assertTrue(3.0 <= v.cardiac_output_l_min <= 8.0)
        self.assertTrue(0.90 <= v.spo2_fraction <= 1.0)

    def test_hemorrhage_drops_pressure(self) -> None:
        engine = FallbackCardiovascularBackend()
        baseline = engine.step(1.0)
        engine.trigger_hemorrhage(rate_ml_min=300, duration_s=90)
        for _ in range(60):
            current = engine.step(1.0)
        self.assertLess(current.systolic_bp_mmhg, baseline.systolic_bp_mmhg)

    def test_exercise_boosts_hr_and_co(self) -> None:
        engine = FallbackCardiovascularBackend()
        baseline = engine.step(1.0)
        engine.trigger_exercise(intensity=0.9, duration_s=120)
        for _ in range(45):
            current = engine.step(1.0)
        self.assertGreater(current.heart_rate_bpm, baseline.heart_rate_bpm)
        self.assertGreater(current.cardiac_output_l_min, baseline.cardiac_output_l_min)


if __name__ == "__main__":
    unittest.main()

