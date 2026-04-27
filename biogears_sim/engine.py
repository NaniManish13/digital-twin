from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
import math
from pathlib import Path
import random
from typing import Deque

import pandas as pd


STANDARD_PATIENTS = ("StandardMale", "StandardFemale", "StandardChild")


@dataclass
class VitalSigns:
    time_s: float
    heart_rate_bpm: float
    systolic_bp_mmhg: float
    diastolic_bp_mmhg: float
    mean_arterial_pressure_mmhg: float
    cardiac_output_l_min: float
    stroke_volume_ml: float
    blood_volume_l: float
    systemic_vascular_resistance: float
    spo2_fraction: float
    central_venous_pressure_mmhg: float


class CardiovascularBackend(ABC):
    @abstractmethod
    def step(self, dt_s: float) -> VitalSigns:
        raise NotImplementedError

    @abstractmethod
    def trigger_hemorrhage(self, rate_ml_min: float, duration_s: float, compartment: str = "VenaCava") -> None:
        raise NotImplementedError

    @abstractmethod
    def trigger_drug_injection(self, substance_name: str, dose_mg: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def trigger_exercise(self, intensity: float, duration_s: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop_hemorrhage(self, compartment: str = "VenaCava") -> None:
        raise NotImplementedError

    @abstractmethod
    def stop_drug_injection(self, substance_name: str = "Epinephrine") -> None:
        raise NotImplementedError

    @abstractmethod
    def stop_exercise(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def apply_action(self, action_type: str, payload: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_ready(self) -> bool:
        raise NotImplementedError


class FallbackCardiovascularBackend(CardiovascularBackend):
    """Simple physiology surrogate used when BioGears bindings are unavailable."""

    def __init__(self) -> None:
        self.time_s = 0.0
        self._rng = random.Random(42)
        self._events: list[dict] = []
        self._baseline = {
            "hr": 72.0,
            "sbp": 118.0,
            "dbp": 76.0,
            "co": 5.0,
            "sv": 70.0,
            "bv": 5.2,
            "svr": 18.0,
            "cvp": 4.5,
            "spo2": 0.985,
        }
        self._state = dict(self._baseline)

    def trigger_hemorrhage(self, rate_ml_min: float, duration_s: float, compartment: str = "VenaCava") -> None:
        self._events.append(
            {
                "kind": "hemorrhage",
                "start": self.time_s,
                "end": self.time_s + max(duration_s, 1.0),
                "rate": max(rate_ml_min, 0.0),
                "compartment": compartment,
            }
        )

    def trigger_drug_injection(self, substance_name: str, dose_mg: float) -> None:
        self._events.append(
            {
                "kind": "drug",
                "start": self.time_s,
                "end": self.time_s + 120.0,
                "name": substance_name,
                "dose": max(dose_mg, 0.0),
            }
        )

    def trigger_exercise(self, intensity: float, duration_s: float) -> None:
        self._events.append(
            {
                "kind": "exercise",
                "start": self.time_s,
                "end": self.time_s + max(duration_s, 1.0),
                "intensity": min(max(intensity, 0.0), 1.0),
            }
        )

    def stop_hemorrhage(self, compartment: str = "VenaCava") -> None:
        self._events = [e for e in self._events if e.get("kind") != "hemorrhage" or e.get("compartment") != compartment]

    def stop_drug_injection(self, substance_name: str = "Epinephrine") -> None:
        self._events = [e for e in self._events if e.get("kind") != "drug" or e.get("name") != substance_name]

    def stop_exercise(self) -> None:
        self._events = [e for e in self._events if e.get("kind") != "exercise"]

    def _event_gain(self, start: float, end: float, ramp_s: float = 6.0) -> float:
        if self.time_s < start:
            return 0.0
        if self.time_s <= end:
            return min(1.0, (self.time_s - start) / ramp_s)
        decay = (self.time_s - end) / 30.0
        return max(0.0, math.exp(-decay))

    def _targets(self) -> dict[str, float]:
        target = dict(self._baseline)

        for event in self._events:
            gain = self._event_gain(event["start"], event["end"])
            if gain <= 0.001:
                continue

            if event["kind"] == "hemorrhage":
                severity = min(event["rate"] / 300.0, 1.0)
                target["hr"] += gain * (30.0 * severity)
                target["sbp"] -= gain * (50.0 * severity)
                target["dbp"] -= gain * (28.0 * severity)
                target["co"] -= gain * (2.4 * severity)
                target["bv"] -= gain * (1.5 * severity)
                target["cvp"] -= gain * (2.2 * severity)
                target["spo2"] -= gain * (0.055 * severity)
            elif event["kind"] == "drug":
                potency = min(event["dose"] / 10.0, 1.0)
                target["hr"] += gain * (14.0 * potency)
                target["sbp"] += gain * (22.0 * potency)
                target["dbp"] += gain * (10.0 * potency)
                target["co"] += gain * (1.1 * potency)
                target["cvp"] += gain * (0.5 * potency)
                target["spo2"] += gain * (0.006 * potency)
            elif event["kind"] == "exercise":
                intensity = event["intensity"]
                target["hr"] += gain * (70.0 * intensity)
                target["sbp"] += gain * (35.0 * intensity)
                target["dbp"] += gain * (8.0 * intensity)
                target["co"] += gain * (7.0 * intensity)
                target["bv"] -= gain * (0.2 * intensity)
                target["spo2"] -= gain * (0.018 * intensity)

        return target

    def step(self, dt_s: float) -> VitalSigns:
        dt_s = max(dt_s, 0.01)
        self.time_s += dt_s

        target = self._targets()
        # First-order response toward targets gives smooth hemodynamic transitions.
        for key, tau in (("hr", 5.0), ("sbp", 8.0), ("dbp", 8.0), ("co", 7.0), ("bv", 12.0), ("cvp", 10.0), ("spo2", 12.0)):
            alpha = 1.0 - math.exp(-dt_s / tau)
            self._state[key] += (target[key] - self._state[key]) * alpha

        # Keep secondary parameters coherent with the primary cardiovascular state.
        self._state["sv"] = (self._state["co"] * 1000.0) / max(self._state["hr"], 1.0)
        self._state["svr"] = max(8.0, min(40.0, 20.0 + (95.0 - self._state["sbp"]) * 0.2))
        self._state["cvp"] = max(1.0, min(20.0, 3.0 + (self._state["bv"] - 4.0) * 2.0))

        self._events = [
            e for e in self._events if self.time_s <= (e["end"] + 180.0)
        ]

        self._state["hr"] += self._rng.uniform(-0.4, 0.4)
        self._state["sbp"] += self._rng.uniform(-0.7, 0.7)
        self._state["dbp"] += self._rng.uniform(-0.6, 0.6)
        self._state["co"] += self._rng.uniform(-0.04, 0.04)
        self._state["bv"] += self._rng.uniform(-0.005, 0.005)
        self._state["spo2"] += self._rng.uniform(-0.0015, 0.0015)

        self._state["hr"] = min(max(self._state["hr"], 30.0), 220.0)
        self._state["sbp"] = min(max(self._state["sbp"], 50.0), 240.0)
        self._state["dbp"] = min(max(self._state["dbp"], 30.0), 160.0)
        self._state["co"] = min(max(self._state["co"], 1.0), 18.0)
        self._state["sv"] = min(max(self._state["sv"], 15.0), 170.0)
        self._state["bv"] = min(max(self._state["bv"], 2.0), 8.0)
        self._state["svr"] = min(max(self._state["svr"], 5.0), 45.0)
        self._state["cvp"] = min(max(self._state["cvp"], 0.0), 25.0)
        self._state["spo2"] = min(max(self._state["spo2"], 0.45), 1.0)

        map_mmhg = self._state["dbp"] + (self._state["sbp"] - self._state["dbp"]) / 3.0

        return VitalSigns(
            time_s=self.time_s,
            heart_rate_bpm=self._state["hr"],
            systolic_bp_mmhg=self._state["sbp"],
            diastolic_bp_mmhg=self._state["dbp"],
            mean_arterial_pressure_mmhg=map_mmhg,
            cardiac_output_l_min=self._state["co"],
            stroke_volume_ml=self._state["sv"],
            blood_volume_l=self._state["bv"],
            systemic_vascular_resistance=self._state["svr"],
            spo2_fraction=self._state["spo2"],
            central_venous_pressure_mmhg=self._state["cvp"],
        )

    def is_ready(self) -> bool:
        return True

    def apply_action(self, action_type: str, payload: dict) -> None:
        if action_type == "HemorrhageData":
            rate = float(payload.get("rate", 0.0))
            duration = float(payload.get("duration", 300.0) or 300.0)
            self.trigger_hemorrhage(rate_ml_min=rate, duration_s=duration)
            self._state["bv"] = max(2.0, self._state["bv"] - (rate / 1000.0) * (duration / 60.0) * 0.08)
            return
        if action_type in ("SubstanceBolusData", "SubstanceInfusionData"):
            dose = float(payload.get("dose") or 0.0)
            self.trigger_drug_injection(str(payload.get("substance") or "UnknownSubstance"), dose_mg=dose)
            return
        if action_type == "SubstanceCompoundInfusionData":
            compound = str(payload.get("compound") or "UnknownCompound")
            rate = float(payload.get("rate") or 0.0)
            if "saline" in compound.lower() or "blood" in compound.lower():
                self._state["bv"] = min(8.0, self._state["bv"] + (rate / 1000.0) * 0.04)
            return
        if action_type == "AcuteStressData":
            severity = float(payload.get("Severity", {}).get("value", 0.5)) if isinstance(payload.get("Severity"), dict) else 0.5
            self.trigger_exercise(intensity=max(0.1, min(1.0, severity)), duration_s=120.0)
            return
        if action_type == "PainStimulusData":
            severity = float(payload.get("Severity", {}).get("value", 0.5)) if isinstance(payload.get("Severity"), dict) else 0.5
            self.trigger_exercise(intensity=max(0.05, min(0.8, severity)), duration_s=180.0)
            return
        if action_type == "CardiacArrestData":
            self._state["co"] = 0.8
            self._state["hr"] = 20.0
            self._state["sbp"] = 50.0
            self._state["dbp"] = 30.0
            self._state["spo2"] = 0.8
            return
        if action_type in ("ChestCompressionForceData", "ChestCompressionForceScaleData"):
            self._state["co"] = min(3.0, self._state["co"] + 0.8)
            self._state["sbp"] = min(95.0, self._state["sbp"] + 4.0)
            return
        if action_type == "PericardialEffusionData":
            self._state["co"] = max(1.5, self._state["co"] - 0.3)
            self._state["cvp"] = min(20.0, self._state["cvp"] + 1.5)
            return
        if action_type in (
            "BrainInjuryData",
            "AirwayObstructionData",
            "AsthmaAttackData",
            "TensionPneumothoraxData",
            "ConsumeNutrientsData",
            "SerializeStateData",
            "PatientAssessmentRequestData",
        ):
            return
        raise NotImplementedError(f"Fallback backend does not implement action type: {action_type}")


class BioGearsCardiovascularBackend(CardiovascularBackend):
    """Thin wrapper around BioGears Python bindings."""

    def __init__(
        self,
        patient_state_file: str | None = None,
        standard_patient: str = "StandardMale",
        bindings_module: object | None = None,
    ) -> None:
        bindings = bindings_module or self._import_bindings()
        self._SEExercise = self._require_symbol(bindings, "SEExercise")
        self._SEHemorrhage = self._require_symbol(bindings, "SEHemorrhage")
        self._SESubstanceBolus = self._require_symbol(bindings, "SESubstanceBolus")
        self._SESubstanceInfusion = getattr(bindings, "SESubstanceInfusion", None)
        self._SESubstanceCompoundInfusion = getattr(bindings, "SESubstanceCompoundInfusion", None)
        self._SEAcuteStress = getattr(bindings, "SEAcuteStress", None)
        self._SEPainStimulus = getattr(bindings, "SEPainStimulus", None)
        self._SEBrainInjury = getattr(bindings, "SEBrainInjury", None)
        self._SEPericardialEffusion = getattr(bindings, "SEPericardialEffusion", None)
        self._SECardiacArrest = getattr(bindings, "SECardiacArrest", None)
        self._SEChestCompressionForce = getattr(bindings, "SEChestCompressionForce", None)
        self._SEChestCompressionForceScale = getattr(bindings, "SEChestCompressionForceScale", None)
        engine_ctor = self._require_symbol(bindings, "BioGearsEngine")
        self._engine = engine_ctor("PythonDashboard")

        loaded = self._initialize_engine(
            patient_state_file=patient_state_file,
            standard_patient=standard_patient,
        )
        if not loaded:
            raise RuntimeError(
                "BioGears engine initialization failed. Provide a valid state file or supported standard patient."
            )

        self.time_s = 0.0
        self._ready = True

    @staticmethod
    def _require_symbol(bindings: object, symbol_name: str) -> object:
        symbol = getattr(bindings, symbol_name, None)
        if symbol is None:
            raise RuntimeError(f"BioGears bindings missing required symbol: {symbol_name}")
        return symbol

    @staticmethod
    def _import_bindings() -> object:
        import importlib

        errors: list[str] = []
        for module_name in ("pybiogears", "biogears"):
            try:
                return importlib.import_module(module_name)
            except Exception as exc:
                errors.append(f"{module_name}: {exc}")
        raise RuntimeError(
            "BioGears Python bindings are not available. Tried pybiogears and biogears. "
            + " | ".join(errors)
        )

    def _initialize_engine(self, patient_state_file: str | None, standard_patient: str) -> bool:
        if patient_state_file:
            state_path = Path(patient_state_file)
            if not state_path.exists():
                raise RuntimeError(f"State file does not exist: {state_path}")
            if hasattr(self._engine, "LoadState"):
                try:
                    if bool(self._engine.LoadState(str(state_path))):
                        return True
                except Exception:
                    pass

        if not hasattr(self._engine, "InitializeEngine"):
            return False

        normalized_patient = standard_patient[:-4] if standard_patient.lower().endswith(".xml") else standard_patient

        # Binding variants accept either `InitializeEngine(<name>)` or no args.
        try:
            if bool(self._engine.InitializeEngine(normalized_patient)):
                return True
        except TypeError:
            pass
        except Exception:
            pass

        try:
            if bool(self._engine.InitializeEngine(standard_patient)):
                return True
        except Exception:
            pass

        try:
            if bool(self._engine.InitializeEngine()):
                return True
        except Exception:
            pass

        return False

    @staticmethod
    def _set_scalar(target: object, value: float, units: str | None = None) -> bool:
        if target is None:
            return False

        if hasattr(target, "SetValue"):
            if units is not None:
                try:
                    target.SetValue(value, units)
                    return True
                except Exception:
                    pass
            try:
                target.SetValue(value)
                return True
            except Exception:
                pass

        if hasattr(target, "Set"):
            try:
                target.Set(value)
                return True
            except Exception:
                pass

        return False

    def _set_action_scalar(
        self,
        action: object,
        scalar_getters: tuple[str, ...],
        scalar_setters: tuple[str, ...],
        value: float,
        units: str | None = None,
    ) -> None:
        for getter_name in scalar_getters:
            getter = getattr(action, getter_name, None)
            if callable(getter):
                try:
                    if self._set_scalar(getter(), value, units):
                        return
                except Exception:
                    pass

        for setter_name in scalar_setters:
            setter = getattr(action, setter_name, None)
            if not callable(setter):
                continue
            if units is not None:
                try:
                    setter(value, units)
                    return
                except Exception:
                    pass
            try:
                setter(value)
                return
            except Exception:
                pass

        names = ", ".join(scalar_getters + scalar_setters)
        raise RuntimeError(f"Unable to set action scalar using any of: {names}")

    def _process_action(self, action: object) -> None:
        if not hasattr(self._engine, "ProcessAction"):
            raise RuntimeError("BioGears engine does not expose ProcessAction")
        result = self._engine.ProcessAction(action)
        if result is False:
            raise RuntimeError("BioGears rejected action")

    def _extract_value(self, getter_obj: object, units: str | None = None) -> float:
        if units and hasattr(getter_obj, "GetValue"):
            try:
                return float(getter_obj.GetValue(units))
            except Exception:
                pass
        if hasattr(getter_obj, "GetValue"):
            return float(getter_obj.GetValue())
        return float(getter_obj)

    def _current_vitals(self) -> VitalSigns:
        cardio = self._engine.GetCardiovascularSystem()
        blood = self._engine.GetBloodChemistrySystem() if hasattr(self._engine, "GetBloodChemistrySystem") else None

        hr = self._extract_value(cardio.GetHeartRate(), "1/min")
        sbp = self._extract_value(cardio.GetSystolicArterialPressure(), "mmHg")
        dbp = self._extract_value(cardio.GetDiastolicArterialPressure(), "mmHg")
        map_mmhg = self._extract_value(cardio.GetMeanArterialPressure(), "mmHg") if hasattr(cardio, "GetMeanArterialPressure") else dbp + (sbp - dbp) / 3.0
        co = self._extract_value(cardio.GetCardiacOutput(), "L/min")
        sv = self._extract_value(cardio.GetHeartStrokeVolume(), "mL") if hasattr(cardio, "GetHeartStrokeVolume") else (co * 1000.0 / max(hr, 1.0))
        bv = self._extract_value(cardio.GetBloodVolume(), "L") if hasattr(cardio, "GetBloodVolume") else float("nan")
        svr = self._extract_value(cardio.GetSystemicVascularResistance(), "mmHg s/mL") if hasattr(cardio, "GetSystemicVascularResistance") else float("nan")
        cvp = self._extract_value(cardio.GetCentralVenousPressure(), "mmHg") if hasattr(cardio, "GetCentralVenousPressure") else float("nan")

        spo2 = float("nan")
        if blood and hasattr(blood, "GetOxygenSaturation"):
            spo2 = self._extract_value(blood.GetOxygenSaturation())

        return VitalSigns(
            time_s=self.time_s,
            heart_rate_bpm=hr,
            systolic_bp_mmhg=sbp,
            diastolic_bp_mmhg=dbp,
            mean_arterial_pressure_mmhg=map_mmhg,
            cardiac_output_l_min=co,
            stroke_volume_ml=sv,
            blood_volume_l=bv,
            systemic_vascular_resistance=svr,
            spo2_fraction=spo2,
            central_venous_pressure_mmhg=cvp,
        )

    def step(self, dt_s: float) -> VitalSigns:
        dt_s = max(dt_s, 0.01)
        self.time_s += dt_s
        if hasattr(self._engine, "AdvanceModelTime"):
            self._engine.AdvanceModelTime(dt_s, "s")
        return self._current_vitals()

    def trigger_hemorrhage(self, rate_ml_min: float, duration_s: float, compartment: str = "VenaCava") -> None:
        action = self._SEHemorrhage()
        if hasattr(action, "SetCompartment"):
            action.SetCompartment(compartment)
        self._set_action_scalar(
            action,
            scalar_getters=("GetInitialRate", "GetRate"),
            scalar_setters=("SetInitialRate", "SetRate"),
            value=max(rate_ml_min, 0.0),
            units="mL/min",
        )
        self._set_action_scalar(
            action,
            scalar_getters=("GetBleedingDuration", "GetDuration"),
            scalar_setters=("SetBleedingDuration", "SetDuration"),
            value=max(duration_s, 1.0),
            units="s",
        )
        self._process_action(action)

    def trigger_drug_injection(self, substance_name: str, dose_mg: float) -> None:
        action = self._SESubstanceBolus()
        if hasattr(action, "SetSubstance") and hasattr(self._engine, "GetSubstanceManager"):
            substance = self._engine.GetSubstanceManager().GetSubstance(substance_name)
            if substance is None:
                raise RuntimeError(f"Unknown substance in BioGears manager: {substance_name}")
            action.SetSubstance(substance)
        self._set_action_scalar(
            action,
            scalar_getters=("GetDose",),
            scalar_setters=("SetDose",),
            value=max(dose_mg, 0.0),
            units="mg",
        )
        self._process_action(action)

    def trigger_exercise(self, intensity: float, duration_s: float) -> None:
        action = self._SEExercise()
        self._set_action_scalar(
            action,
            scalar_getters=("GetIntensity",),
            scalar_setters=("SetIntensity",),
            value=min(max(intensity, 0.0), 1.0),
        )
        self._set_action_scalar(
            action,
            scalar_getters=("GetDuration",),
            scalar_setters=("SetDuration",),
            value=max(duration_s, 1.0),
            units="s",
        )
        self._process_action(action)

    def stop_hemorrhage(self, compartment: str = "VenaCava") -> None:
        action = self._SEHemorrhage()
        if hasattr(action, "SetCompartment"):
            action.SetCompartment(compartment)
        self._set_action_scalar(
            action,
            scalar_getters=("GetInitialRate", "GetRate"),
            scalar_setters=("SetInitialRate", "SetRate"),
            value=0.0,
            units="mL/min",
        )
        self._process_action(action)

    def stop_drug_injection(self, substance_name: str = "Epinephrine") -> None:
        # Best-effort stop: no dedicated cancel action across bindings; issue a zero-dose bolus if supported.
        action = self._SESubstanceBolus()
        if hasattr(action, "SetSubstance") and hasattr(self._engine, "GetSubstanceManager"):
            substance = self._engine.GetSubstanceManager().GetSubstance(substance_name)
            if substance is not None:
                action.SetSubstance(substance)
        self._set_action_scalar(
            action,
            scalar_getters=("GetDose",),
            scalar_setters=("SetDose",),
            value=0.0,
            units="mg",
        )
        self._process_action(action)

    def stop_exercise(self) -> None:
        action = self._SEExercise()
        self._set_action_scalar(
            action,
            scalar_getters=("GetIntensity",),
            scalar_setters=("SetIntensity",),
            value=0.0,
        )
        self._set_action_scalar(
            action,
            scalar_getters=("GetDuration",),
            scalar_setters=("SetDuration",),
            value=1.0,
            units="s",
        )
        self._process_action(action)

    def is_ready(self) -> bool:
        return bool(self._ready)

    def _set_substance(self, action: object, substance_name: str | None) -> None:
        if not substance_name:
            return
        if not hasattr(action, "SetSubstance") or not hasattr(self._engine, "GetSubstanceManager"):
            return
        substance = self._engine.GetSubstanceManager().GetSubstance(substance_name)
        if substance is None:
            raise RuntimeError(f"Unknown substance in BioGears manager: {substance_name}")
        action.SetSubstance(substance)

    def _set_compound(self, action: object, compound_name: str | None) -> None:
        if not compound_name:
            return
        if not hasattr(action, "SetSubstanceCompound") or not hasattr(self._engine, "GetSubstanceManager"):
            return
        manager = self._engine.GetSubstanceManager()
        getter = getattr(manager, "GetCompound", None) or getattr(manager, "GetSubstanceCompound", None)
        if not callable(getter):
            return
        compound = getter(compound_name)
        if compound is None:
            raise RuntimeError(f"Unknown compound in BioGears manager: {compound_name}")
        action.SetSubstanceCompound(compound)

    def apply_action(self, action_type: str, payload: dict) -> None:
        if not self.is_ready():
            raise RuntimeError("BioGears engine is not ready for action processing")

        if action_type == "HemorrhageData":
            self.trigger_hemorrhage(
                rate_ml_min=float(payload.get("rate", 0.0) or 0.0),
                duration_s=float(payload.get("duration") or 300.0),
                compartment=str(payload.get("compartment") or "VenaCava"),
            )
            return

        if action_type == "SubstanceBolusData":
            self.trigger_drug_injection(
                substance_name=str(payload.get("substance") or "Epinephrine"),
                dose_mg=float(payload.get("dose") or 0.0),
            )
            return

        if action_type == "SubstanceInfusionData" and self._SESubstanceInfusion is not None:
            action = self._SESubstanceInfusion()
            self._set_substance(action, payload.get("substance"))
            self._set_action_scalar(action, ("GetRate",), ("SetRate",), float(payload.get("rate") or 0.0), payload.get("rate_unit") or "mL/min")
            self._set_action_scalar(action, ("GetConcentration",), ("SetConcentration",), float(payload.get("concentration") or 0.0), payload.get("concentration_unit") or "ug/mL")
            self._set_action_scalar(action, ("GetVolume", "GetDose"), ("SetVolume", "SetDose"), float(payload.get("dose") or 0.0), payload.get("dose_unit") or "mL")
            self._process_action(action)
            return

        if action_type == "SubstanceCompoundInfusionData" and self._SESubstanceCompoundInfusion is not None:
            action = self._SESubstanceCompoundInfusion()
            self._set_compound(action, payload.get("compound"))
            self._set_action_scalar(action, ("GetBagVolume",), ("SetBagVolume",), float(payload.get("bag_volume") or 0.0), payload.get("bag_unit") or "mL")
            self._set_action_scalar(action, ("GetRate",), ("SetRate",), float(payload.get("rate") or 0.0), payload.get("rate_unit") or "mL/min")
            self._process_action(action)
            return

        if action_type == "AcuteStressData" and self._SEAcuteStress is not None:
            action = self._SEAcuteStress()
            severity = payload.get("Severity", {}).get("value") if isinstance(payload.get("Severity"), dict) else None
            self._set_action_scalar(action, ("GetSeverity",), ("SetSeverity",), float(severity or 0.5))
            self._process_action(action)
            return

        if action_type == "PainStimulusData" and self._SEPainStimulus is not None:
            action = self._SEPainStimulus()
            severity = payload.get("Severity", {}).get("value") if isinstance(payload.get("Severity"), dict) else None
            self._set_action_scalar(action, ("GetSeverity",), ("SetSeverity",), float(severity or 0.5))
            self._process_action(action)
            return

        if action_type == "BrainInjuryData" and self._SEBrainInjury is not None:
            action = self._SEBrainInjury()
            severity = payload.get("Severity", {}).get("value") if isinstance(payload.get("Severity"), dict) else None
            self._set_action_scalar(action, ("GetSeverity",), ("SetSeverity",), float(severity or 0.5))
            self._process_action(action)
            return

        if action_type == "PericardialEffusionData" and self._SEPericardialEffusion is not None:
            action = self._SEPericardialEffusion()
            rate = payload.get("AccumulationRate", {}).get("value") if isinstance(payload.get("AccumulationRate"), dict) else None
            unit = payload.get("AccumulationRate", {}).get("unit") if isinstance(payload.get("AccumulationRate"), dict) else "mL/s"
            self._set_action_scalar(action, ("GetAccumulationRate",), ("SetAccumulationRate",), float(rate or 0.0), unit)
            self._process_action(action)
            return

        if action_type == "CardiacArrestData" and self._SECardiacArrest is not None:
            self._process_action(self._SECardiacArrest())
            return

        if action_type == "ChestCompressionForceData" and self._SEChestCompressionForce is not None:
            action = self._SEChestCompressionForce()
            force = payload.get("Force", {}).get("value") if isinstance(payload.get("Force"), dict) else None
            self._set_action_scalar(action, ("GetForce",), ("SetForce",), float(force or 0.0), "N")
            self._process_action(action)
            return

        if action_type == "ChestCompressionForceScaleData" and self._SEChestCompressionForceScale is not None:
            action = self._SEChestCompressionForceScale()
            scale = payload.get("ForceScale", {}).get("value") if isinstance(payload.get("ForceScale"), dict) else None
            self._set_action_scalar(action, ("GetForceScale",), ("SetForceScale",), float(scale or 0.0))
            self._process_action(action)
            return

        if action_type in ("SerializeStateData", "PatientAssessmentRequestData", "ConsumeNutrientsData", "AirwayObstructionData", "AsthmaAttackData", "TensionPneumothoraxData"):
            raise NotImplementedError(f"Action type requires dedicated binding wrapper: {action_type}")

        raise NotImplementedError(f"Unsupported BioGears action type: {action_type}")


def create_backend(
    mode: str = "auto",
    patient_state_file: str | None = None,
    standard_patient: str = "StandardMale",
) -> CardiovascularBackend:
    selected = mode.lower()
    if selected == "fallback":
        return FallbackCardiovascularBackend()
    if selected == "biogears":
        return BioGearsCardiovascularBackend(
            patient_state_file=patient_state_file,
            standard_patient=standard_patient,
        )

    try:
        return BioGearsCardiovascularBackend(
            patient_state_file=patient_state_file,
            standard_patient=standard_patient,
        )
    except Exception:
        return FallbackCardiovascularBackend()


class SimulationController:
    def __init__(self, backend: CardiovascularBackend, history_limit: int = 4000) -> None:
        self.backend = backend
        self.history: Deque[VitalSigns] = deque(maxlen=history_limit)

    def step(self, dt_s: float) -> VitalSigns:
        vitals = self.backend.step(dt_s)
        self.history.append(vitals)
        return vitals

    def trigger_hemorrhage(self, rate_ml_min: float, duration_s: float, compartment: str = "VenaCava") -> None:
        self.backend.trigger_hemorrhage(rate_ml_min, duration_s, compartment)

    def trigger_drug_injection(self, substance_name: str, dose_mg: float) -> None:
        self.backend.trigger_drug_injection(substance_name, dose_mg)

    def trigger_exercise(self, intensity: float, duration_s: float) -> None:
        self.backend.trigger_exercise(intensity, duration_s)

    def stop_hemorrhage(self, compartment: str = "VenaCava") -> None:
        self.backend.stop_hemorrhage(compartment)

    def stop_drug_injection(self, substance_name: str = "Epinephrine") -> None:
        self.backend.stop_drug_injection(substance_name)

    def stop_exercise(self) -> None:
        self.backend.stop_exercise()

    def history_frame(self) -> pd.DataFrame:
        if not self.history:
            return pd.DataFrame(
                columns=[
                    "time_s",
                    "heart_rate_bpm",
                    "systolic_bp_mmhg",
                    "diastolic_bp_mmhg",
                    "mean_arterial_pressure_mmhg",
                    "cardiac_output_l_min",
                    "stroke_volume_ml",
                    "blood_volume_l",
                    "systemic_vascular_resistance",
                    "central_venous_pressure_mmhg",
                    "spo2_percent",
                ]
            )

        rows = [
            {
                "time_s": v.time_s,
                "heart_rate_bpm": v.heart_rate_bpm,
                "systolic_bp_mmhg": v.systolic_bp_mmhg,
                "diastolic_bp_mmhg": v.diastolic_bp_mmhg,
                "mean_arterial_pressure_mmhg": v.mean_arterial_pressure_mmhg,
                "cardiac_output_l_min": v.cardiac_output_l_min,
                "stroke_volume_ml": v.stroke_volume_ml,
                "blood_volume_l": v.blood_volume_l,
                "systemic_vascular_resistance": v.systemic_vascular_resistance,
                "central_venous_pressure_mmhg": v.central_venous_pressure_mmhg,
                "spo2_percent": v.spo2_fraction * 100.0,
            }
            for v in self.history
        ]
        return pd.DataFrame(rows)

