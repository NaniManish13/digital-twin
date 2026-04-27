from pathlib import Path
import tempfile
import unittest

from biogears_sim.disease_classifier import disease_label_from_filename, train_classifier, train_if_missing_and_predict


class TestDiseaseClassifier(unittest.TestCase):
    def test_filename_label_mapping(self) -> None:
        self.assertEqual(disease_label_from_filename("SinusBradycardia"), "SinusBradycardia")
        self.assertEqual(disease_label_from_filename("HemorrhageClass2Blood"), "Hemorrhage")
        self.assertEqual(disease_label_from_filename("SepticShock_Treatment"), "SepticShock")

    def test_train_and_predict(self) -> None:
        patients_dir = Path("C:/Users/Dell/digital_twin/patients")
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "disease_classifier.pkl"
            train_classifier(patients_dir, model_path)
            self.assertTrue(model_path.exists())

            sample = patients_dir / "SinusBradycardia.xml"
            prediction = train_if_missing_and_predict(sample, patients_dir, model_path)
            self.assertTrue(prediction.label)
            self.assertGreaterEqual(prediction.confidence, 0.0)
            self.assertLessEqual(prediction.confidence, 1.0)


if __name__ == "__main__":
    unittest.main()

