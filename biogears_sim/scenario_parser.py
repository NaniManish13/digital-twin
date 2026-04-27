from __future__ import annotations

from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from .scenario_models import DataRequestSpec, ScenarioAction, ScenarioDefinition


XML_NS = {
    "bg": "uri:/mil/tatrc/physiology/datamodel",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}
XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"


def _request(category: str, name: str, unit: str | None, precision: int | None, compartment: str | None = None, substance: str | None = None) -> DataRequestSpec:
    return DataRequestSpec(
        category=category,
        name=name,
        unit=unit,
        precision=precision,
        compartment=compartment,
        substance=substance,
    )


UNIVERSAL_DATA_REQUESTS: tuple[DataRequestSpec, ...] = (
    _request("Physiology", "HeartRate", "1/min", 2),
    _request("Physiology", "HeartStrokeVolume", "mL", 1),
    _request("Physiology", "BloodVolume", "L", 2),
    _request("Physiology", "ArterialPressure", "mmHg", 1),
    _request("Physiology", "MeanArterialPressure", "mmHg", 1),
    _request("Physiology", "SystolicArterialPressure", "mmHg", 0),
    _request("Physiology", "DiastolicArterialPressure", "mmHg", 1),
    _request("Physiology", "CardiacOutput", "L/min", 2),
    _request("Physiology", "HemoglobinContent", "g", 0),
    _request("Physiology", "CentralVenousPressure", "mmHg", 2),
    _request("Physiology", "PulmonaryCapillariesWedgePressure", "mmHg", 2),
    _request("Physiology", "SystemicVascularResistance", "mmHg s/mL", 3),
    _request("Physiology", "ExtravascularFluidVolume", "L", 1),
    _request("Physiology", "TidalVolume", "mL", 3),
    _request("Physiology", "TotalLungVolume", "L", 2),
    _request("Physiology", "RespirationRate", "1/min", 2),
    _request("Physiology", "OxygenSaturation", "unitless", 3),
    _request("Physiology", "CarbonDioxideSaturation", "unitless", 3),
    _request("Physiology", "EndTidalCarbonDioxideFraction", "unitless", 4),
    _request("Physiology", "TotalAlveolarVentilation", "L/min", 2),
    _request("Physiology", "TranspulmonaryPressure", "cmH2O", 2),
    _request("Physiology", "CoreTemperature", "degC", 1),
    _request("Physiology", "SkinTemperature", "degC", 1),
    _request("Physiology", "RespiratoryExchangeRatio", "unitless", 3),
    _request("Physiology", "OxygenConsumptionRate", "mL/min", 3),
    _request("Physiology", "CarbonDioxideProductionRate", "mL/min", 3),
    _request("Physiology", "GlomerularFiltrationRate", "mL/min", 0),
    _request("Physiology", "RenalBloodFlow", "L/min", 2),
    _request("Physiology", "UrineProductionRate", "mL/min", 3),
    _request("Physiology", "ArterialBloodPH", "unitless", 2),
    _request("Physiology", "RightAfferentArterioleResistance", "mmHg min/mL", 4),
    _request("GasCompartment", "Pressure", "cmH2O", 2, compartment="LeftAlveoli"),
    _request("GasCompartment", "Oxygen", "mmHg", 2, compartment="LeftAlveoli"),
    _request("GasCompartment", "CarbonDioxide", "mmHg", 2, compartment="LeftAlveoli"),
    _request("GasCompartment", "Pressure", "cmH2O", 2, compartment="RightAlveoli"),
    _request("GasCompartment", "Oxygen", "mmHg", 2, compartment="RightAlveoli"),
    _request("GasCompartment", "CarbonDioxide", "mmHg", 2, compartment="RightAlveoli"),
    _request("GasCompartment", "Oxygen", "cmH2O", 2, compartment="Trachea"),
    _request("GasCompartment", "CarbonDioxide", "cmH2O", 2, compartment="Trachea"),
    _request("LiquidCompartment", "Oxygen", "mmHg", 2, compartment="Aorta"),
    _request("LiquidCompartment", "CarbonDioxide", "mmHg", 2, compartment="Aorta"),
    _request("LiquidCompartment", "Oxygen", "mmHg", 2, compartment="VenaCava"),
    _request("LiquidCompartment", "CarbonDioxide", "mmHg", 2, compartment="VenaCava"),
    _request("LiquidCompartment", "Sodium", "g/L", 2, compartment="RightTubules"),
    _request("LiquidCompartment", "Sodium", "g/L", 2, compartment="LeftTubules"),
    _request("Substance", "AlveolarTransfer", "mL/s", 2, substance="Oxygen"),
    _request("Substance", "AlveolarTransfer", "mL/s", 2, substance="CarbonDioxide"),
    _request("Substance", "BloodConcentration", "ug/L", 6, substance="Epinephrine"),
    _request("Physiology", "LiverGlycogen", "g", 2),
    _request("Physiology", "MuscleGlycogen", "g", 2),
)

HEMORRHAGE_ADDITIONS: tuple[DataRequestSpec, ...] = (
    _request("LiquidCompartment", "InFlow", "mL/min", 3, compartment="Aorta"),
    _request("LiquidCompartment", "OutFlow", "mL/min", 3, compartment="Aorta"),
    _request("LiquidCompartment", "InFlow", "mL/min", 3, compartment="Ground"),
    _request("Substance", "BloodConcentration", "g/L", 2, substance="Sodium"),
    _request("Substance", "MassInBody", "g", 1, substance="Sodium"),
    _request("LiquidCompartment", "Sodium", "g/L", 2, compartment="Bladder"),
    _request("Substance", "BloodConcentration", "mg/dL", 3, substance="Lactate"),
    _request("LiquidCompartment", "Albumin", "g/L", 1, compartment="Aorta"),
    _request("Physiology", "StrongIonDifference", "mmol/L", 3),
    _request("Physiology", "UrineOsmolality", "mOsm/kg", 1),
    _request("Physiology", "UrineOsmolarity", "mOsm/L", 1),
)

SEPSIS_ADDITIONS: tuple[DataRequestSpec, ...] = (
    _request("Substance", "MassInBody", "mg", 2, substance="Lactate"),
    _request("Substance", "MassInBlood", "mg", 2, substance="Lactate"),
    _request("Substance", "MassInTissue", "mg", 2, substance="Lactate"),
    _request("Substance", "BloodConcentration", "mg/L", 2, substance="Lactate"),
    _request("Substance", "Clearance-RenalFiltrationRate", "mg/min", 2, substance="Lactate"),
    _request("Physiology", "TotalBilirubin", "mg/dL", 3),
    _request("Physiology", "EnergyDeficit", "W", 3),
    _request("Physiology", "MeanUrineOutput", "mL/min", 3),
    _request("Physiology", "InflammatoryResponse-TissueIntegrity", None, 3),
    _request("Physiology", "InflammatoryResponse-BloodPathogen", None, 3),
    _request("Physiology", "InflammatoryResponse-LocalPathogen", None, 3),
    _request("Physiology", "InflammatoryResponse-LocalMacrophage", None, 3),
    _request("Physiology", "InflammatoryResponse-LocalNeutrophil", None, 3),
    _request("Physiology", "InflammatoryResponse-LocalBarrier", None, 3),
    _request("Physiology", "InflammatoryResponse-Trauma", None, 3),
    _request("Physiology", "InflammatoryResponse-MacrophageResting", None, 3),
    _request("Physiology", "InflammatoryResponse-MacrophageActive", None, 3),
    _request("Physiology", "InflammatoryResponse-NeutrophilActive", None, 3),
    _request("Physiology", "InflammatoryResponse-NeutrophilResting", None, 3),
    _request("Physiology", "InflammatoryResponse-Interleukin6", None, 3),
    _request("Physiology", "InflammatoryResponse-Interleukin10", None, 3),
    _request("Physiology", "InflammatoryResponse-Interleukin12", None, 3),
    _request("Physiology", "InflammatoryResponse-Nitrate", None, 3),
    _request("Physiology", "InflammatoryResponse-NitricOxide", None, 3),
    _request("Physiology", "InflammatoryResponse-TumorNecrosisFactor", None, 3),
    _request("Physiology", "InflammatoryResponse-ConstitutiveNOS", None, 3),
    _request("Physiology", "InflammatoryResponse-InducibleNOSPre", None, 3),
    _request("Physiology", "InflammatoryResponse-InducibleNOS", None, 3),
    _request("LiquidCompartment", "Albumin", "g/dL", 2, compartment="Aorta"),
    _request("LiquidCompartment", "Lactate", "mmol/L", 2, compartment="Aorta"),
    _request("LiquidCompartment", "Lactate", "mg/L", 2, compartment="MuscleTissueIntracellular"),
    _request("LiquidCompartment", "Lactate", "mg/L", 2, compartment="MuscleTissueExtracellular"),
)


def _strip_ns(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _to_float_if_numeric(raw: str) -> float | str:
    try:
        return float(raw)
    except Exception:
        return raw


def _set_payload(payload: dict[str, Any], key: str, value: Any) -> None:
    if key not in payload:
        payload[key] = value
        return
    current = payload[key]
    if isinstance(current, list):
        current.append(value)
    else:
        payload[key] = [current, value]


def _parse_node(node: ET.Element) -> Any:
    children = list(node)
    if not children:
        if "value" in node.attrib:
            return {
                "value": _to_float_if_numeric(node.attrib["value"]),
                "unit": node.attrib.get("unit"),
            }
        text = (node.text or "").strip()
        if text:
            return _to_float_if_numeric(text)
        if node.attrib:
            return {
                key: val
                for key, val in node.attrib.items()
                if key != XSI_TYPE
            }
        return None

    payload: dict[str, Any] = {}
    for key, val in node.attrib.items():
        if key == XSI_TYPE:
            continue
        payload[_strip_ns(key)] = _to_float_if_numeric(val)

    for child in children:
        _set_payload(payload, _strip_ns(child.tag), _parse_node(child))
    return payload


def _seconds_from_scalar(value: Any) -> int:
    if not isinstance(value, dict):
        return int(float(value))
    scalar_value = float(value.get("value", 0.0))
    unit = (value.get("unit") or "s").lower()
    if unit in ("s", "sec", "second", "seconds"):
        return int(round(scalar_value))
    if unit in ("min", "minute", "minutes"):
        return int(round(scalar_value * 60.0))
    if unit in ("hr", "h", "hour", "hours"):
        return int(round(scalar_value * 3600.0))
    return int(round(scalar_value))


def _parse_data_requests(root: ET.Element) -> tuple[float | None, tuple[DataRequestSpec, ...]]:
    dr_node = root.find("bg:DataRequests", XML_NS)
    if dr_node is None:
        return None, ()

    sps = dr_node.attrib.get("SamplesPerSecond")
    samples_per_second = float(sps) if sps is not None else None

    requests: list[DataRequestSpec] = []
    for req in dr_node.findall("bg:DataRequest", XML_NS):
        req_type = req.attrib.get(XSI_TYPE, "")
        category = req_type.replace("DataRequestData", "") or "Unknown"
        precision = req.attrib.get("Precision")
        requests.append(
            DataRequestSpec(
                category=category,
                name=req.attrib.get("Name", ""),
                unit=req.attrib.get("Unit"),
                precision=int(precision) if precision is not None else None,
                compartment=req.attrib.get("Compartment"),
                substance=req.attrib.get("Substance"),
            )
        )
    return samples_per_second, tuple(requests)


def _build_required_requests(scenario_name: str, xml_requests: tuple[DataRequestSpec, ...]) -> tuple[DataRequestSpec, ...]:
    required: list[DataRequestSpec] = list(UNIVERSAL_DATA_REQUESTS)

    lower = scenario_name.lower()
    if "hemorrhage" in lower or "txa" in lower:
        required.extend(HEMORRHAGE_ADDITIONS)
    if "sepsis" in lower or "septicshock" in lower:
        required.extend(SEPSIS_ADDITIONS)

    required.extend(xml_requests)

    deduped: dict[tuple[str, str, str | None, str | None, str | None], DataRequestSpec] = {}
    for req in required:
        key = (req.category, req.name, req.unit, req.compartment, req.substance)
        deduped[key] = req
    return tuple(deduped.values())


def parse_scenario_file(file_path: Path) -> ScenarioDefinition:
    root = ET.parse(file_path).getroot()

    # Use filename stem as canonical key to avoid collisions in reused XML <Name> fields.
    scenario_name = file_path.stem
    init = root.find("bg:InitialParameters", XML_NS)

    patient_file = init.findtext("bg:PatientFile", default=None, namespaces=XML_NS) if init is not None else None
    engine_state_file = root.findtext("bg:EngineStateFile", default=None, namespaces=XML_NS)

    samples_per_second, xml_data_requests = _parse_data_requests(root)

    actions: list[ScenarioAction] = []
    timeline_s = 0
    for node in root.findall(".//bg:Actions/bg:Action", XML_NS):
        action_type = node.attrib.get(XSI_TYPE, "")
        payload = _parse_node(node)
        if action_type == "AdvanceTimeData":
            action_time = payload.get("Time") if isinstance(payload, dict) else None
            timeline_s += _seconds_from_scalar(action_time or {"value": 0.0, "unit": "s"})
            continue

        actions.append(
            ScenarioAction(
                action_type=action_type,
                timestamp_s=timeline_s,
                payload=payload if isinstance(payload, dict) else {},
            )
        )

    required_requests = _build_required_requests(scenario_name, xml_data_requests)

    return ScenarioDefinition(
        scenario_name=scenario_name,
        scenario_file=str(file_path),
        patient_file=patient_file,
        engine_state_file=engine_state_file,
        samples_per_second=samples_per_second,
        timeline_duration_s=timeline_s,
        actions=tuple(actions),
        xml_data_requests=xml_data_requests,
        required_data_requests=required_requests,
    )


def load_scenarios(patients_dir: Path) -> dict[str, ScenarioDefinition]:
    scenarios: dict[str, ScenarioDefinition] = {}
    for file_path in sorted(patients_dir.glob("*.xml")):
        definition = parse_scenario_file(file_path)
        scenarios[definition.scenario_name] = definition
    return scenarios

