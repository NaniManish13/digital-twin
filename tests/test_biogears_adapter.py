import tempfile
import types
import unittest

from biogears_sim.engine import BioGearsCardiovascularBackend


class FakeScalar:
    def __init__(self) -> None:
        self.value = None
        self.units = None

    def SetValue(self, value, units=None):
        self.value = value
        self.units = units


class FakeHemorrhage:
    def __init__(self) -> None:
        self.initial_rate = FakeScalar()
        self.duration = FakeScalar()
        self.compartment = None

    def SetCompartment(self, name: str) -> None:
        self.compartment = name

    def GetInitialRate(self):
        return self.initial_rate

    def GetBleedingDuration(self):
        return self.duration


class FakeBolus:
    def __init__(self) -> None:
        self.dose = FakeScalar()
        self.substance = None

    def SetSubstance(self, substance):
        self.substance = substance

    def GetDose(self):
        return self.dose


class FakeExercise:
    def __init__(self) -> None:
        self.intensity = FakeScalar()
        self.duration = FakeScalar()

    def GetIntensity(self):
        return self.intensity

    def GetDuration(self):
        return self.duration


class FakeSubstanceManager:
    def GetSubstance(self, name: str):
        return {"name": name}


class FakeEngine:
    last_instance = None

    def __init__(self, _name: str) -> None:
        self.initialized_patient = None
        self.loaded_path = None
        self.processed_actions = []
        FakeEngine.last_instance = self

    def LoadState(self, path: str) -> bool:
        self.loaded_path = path
        return True

    def InitializeEngine(self, patient_name: str = "StandardMale") -> bool:
        self.initialized_patient = patient_name
        return True

    def ProcessAction(self, action) -> bool:
        self.processed_actions.append(action)
        return True

    def GetSubstanceManager(self):
        return FakeSubstanceManager()


def build_fake_bindings():
    return types.SimpleNamespace(
        BioGearsEngine=FakeEngine,
        SEHemorrhage=FakeHemorrhage,
        SESubstanceBolus=FakeBolus,
        SEExercise=FakeExercise,
    )


class TestBioGearsAdapter(unittest.TestCase):
    def test_standard_patient_initialization(self):
        BioGearsCardiovascularBackend(
            standard_patient="StandardFemale",
            bindings_module=build_fake_bindings(),
        )
        self.assertEqual(FakeEngine.last_instance.initialized_patient, "StandardFemale")

    def test_state_file_initialization_is_used_when_present(self):
        with tempfile.NamedTemporaryFile(suffix=".xml") as tmp:
            BioGearsCardiovascularBackend(
                patient_state_file=tmp.name,
                standard_patient="StandardChild",
                bindings_module=build_fake_bindings(),
            )
            self.assertEqual(FakeEngine.last_instance.loaded_path, tmp.name)

    def test_hemorrhage_action_uses_expected_units(self):
        backend = BioGearsCardiovascularBackend(bindings_module=build_fake_bindings())
        backend.trigger_hemorrhage(rate_ml_min=250.0, duration_s=75.0)

        action = FakeEngine.last_instance.processed_actions[-1]
        self.assertEqual(action.compartment, "VenaCava")
        self.assertEqual(action.initial_rate.units, "mL/min")
        self.assertEqual(action.duration.units, "s")


if __name__ == "__main__":
    unittest.main()

