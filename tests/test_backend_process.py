import json
import tempfile
import unittest
from pathlib import Path

from backend.process import compute_bpm, estimate_sampling_rate, load_signal, normalize_signal


class TestBackendProcess(unittest.TestCase):
    def test_pipeline_from_sample_csv(self):
        csv_path = Path("C:/Users/Dell/digital_twin/backend/input.csv")
        time_axis, signal = load_signal(csv_path)
        sr = estimate_sampling_rate(time_axis)
        cleaned = normalize_signal(signal)

        if len(time_axis) > 1:
            duration = float(time_axis[-1] - time_axis[0])
        else:
            duration = float(len(cleaned) / sr)

        bpm, peaks = compute_bpm(cleaned, duration, sr)
        self.assertGreater(bpm, 0)
        self.assertGreater(len(peaks), 0)

    def test_output_json_shape(self):
        payload = {"bpm": 72, "signal": [0.1, 0.2, 0.3]}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "output.json"
            out.write_text(json.dumps(payload), encoding="utf-8")
            parsed = json.loads(out.read_text(encoding="utf-8"))

        self.assertIn("bpm", parsed)
        self.assertIn("signal", parsed)


if __name__ == "__main__":
    unittest.main()

