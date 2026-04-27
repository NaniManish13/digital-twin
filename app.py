from __future__ import annotations

from pathlib import Path
import time
import xml.etree.ElementTree as ET
import json

import streamlit as st

from biogears_sim.disease_classifier import train_if_missing_and_predict
from biogears_sim.engine import SimulationController, create_backend


st.set_page_config(page_title="BioGears Cardiovascular Dashboard", layout="wide")
st.title("BioGears Cardiovascular Live Dashboard")


def infer_disease_from_document(document_path: str) -> str:
    path = Path(document_path)
    keyword_map = (
        ("brady", "Sinus Bradycardia"),
        ("tachy", "Sinus Tachycardia"),
        ("anemia", "Anemia"),
        ("sepsis", "Sepsis"),
        ("septic", "Septic Shock"),
        ("stenosis", "Renal Artery Stenosis"),
        ("effusion", "Pericardial Effusion"),
        ("hemorrhage", "Hemorrhage / Blood Loss"),
        ("dysfunction", "Ventricular Systolic Dysfunction"),
        ("braininjury", "Brain Injury"),
        ("pain", "Pain Stimulus"),
    )

    source = path.stem.lower()
    for token, disease in keyword_map:
        if token in source:
            return disease

    try:
        raw = path.read_text(encoding="utf-8", errors="ignore").lower()
        for token, disease in keyword_map:
            if token in raw:
                return disease
        root = ET.parse(path).getroot()
        if root is not None and root.tag:
            tag = root.tag.lower()
            for token, disease in keyword_map:
                if token in tag:
                    return disease
    except Exception:
        pass

    return "No specific disease detected (normal/unspecified BioGears profile)"


def classify_disease_from_model(document_path: str) -> tuple[str, str]:
    try:
        prediction = train_if_missing_and_predict(
            xml_path=resolve_document_path(document_path),
            patients_dir=Path("patients"),
            model_path=Path("models") / "disease_classifier.pkl",
        )
        label = prediction.label
        confidence = f"{prediction.confidence * 100.0:.1f}%"
        return label, confidence
    except Exception:
        return infer_disease_from_document(document_path), "N/A"


def resolve_document_path(raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return (Path.cwd() / candidate).resolve()


def parse_document_metadata(document_path: str) -> dict[str, str]:
    resolved = resolve_document_path(document_path)
    if not resolved.exists():
        raise FileNotFoundError(f"Document not found: {resolved}")
    if resolved.suffix.lower() != ".xml":
        raise ValueError("Only XML files are supported for patient/state documents")

    metadata = {
        "resolved_path": str(resolved),
        "document_name": resolved.name,
        "document_stem": resolved.stem,
        "detected_disease": infer_disease_from_document(str(resolved)),
    }

    try:
        root = ET.parse(resolved).getroot()
        if root is not None:
            metadata["xml_root"] = root.tag
    except Exception:
        metadata["xml_root"] = "unreadable"

    return metadata


def extract_document_snapshot(document_path: str) -> dict[str, str]:
    resolved = resolve_document_path(document_path)
    if not resolved.exists():
        raise FileNotFoundError(f"Document not found: {resolved}")

    root = ET.parse(resolved).getroot()
    child_tags = [child.tag for child in list(root)[:8]] if root is not None else []

    return {
        "document_name": resolved.name,
        "resolved_path": str(resolved),
        "xml_root": root.tag if root is not None else "unknown",
        "xml_attributes": dict(root.attrib) if root is not None else {},
        "top_level_children": child_tags,
        "element_count": str(sum(1 for _ in root.iter())) if root is not None else "0",
    }


def build_controller(mode: str, document_type: str, document_path: str) -> SimulationController:
    patient_state_file: str | None = None
    standard_patient = "StandardMale"

    cleaned = document_path.strip()
    if cleaned:
        metadata = parse_document_metadata(cleaned)
        if document_type == "state_file":
            patient_state_file = metadata["resolved_path"]
        elif document_type == "patient_file":
            standard_patient = metadata["document_stem"]

    return SimulationController(
        create_backend(
            mode=mode,
            patient_state_file=patient_state_file,
            standard_patient=standard_patient,
        )
    )


def write_live_biogears_snapshot(latest, source_summary: str, disease_label: str) -> None:
    payload = {
        "bpm": float(latest.heart_rate_bpm),
        "heart_rate_bpm": float(latest.heart_rate_bpm),
        "systolic_bp_mmhg": float(latest.systolic_bp_mmhg),
        "diastolic_bp_mmhg": float(latest.diastolic_bp_mmhg),
        "cardiac_output_l_min": float(latest.cardiac_output_l_min),
        "spo2_fraction": float(latest.spo2_fraction),
        "time_s": float(latest.time_s),
        "source": source_summary,
        "detected_condition": disease_label or "Unspecified",
    }
    output_path = Path("backend") / "biogears_live.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")



if "backend_mode" not in st.session_state:
    st.session_state.backend_mode = "auto"
if "backend_warning" not in st.session_state:
    st.session_state.backend_warning = ""
if "hemorrhage_active" not in st.session_state:
    st.session_state.hemorrhage_active = False
if "drug_active" not in st.session_state:
    st.session_state.drug_active = False
if "exercise_active" not in st.session_state:
    st.session_state.exercise_active = False
if "patient_document_type" not in st.session_state:
    st.session_state.patient_document_type = "none"
if "patient_document_path" not in st.session_state:
    st.session_state.patient_document_path = ""
if "detected_disease" not in st.session_state:
    st.session_state.detected_disease = ""
if "loaded_patient_summary" not in st.session_state:
    st.session_state.loaded_patient_summary = "Default standard patient"
if "disease_confidence" not in st.session_state:
    st.session_state.disease_confidence = "N/A"
if "patient_document_snapshot" not in st.session_state:
    st.session_state.patient_document_snapshot = {}
if "controller" not in st.session_state:
    try:
        st.session_state.controller = build_controller(
            mode="auto",
            document_type=st.session_state.patient_document_type,
            document_path=st.session_state.patient_document_path,
        )
    except Exception as exc:
        st.session_state.controller = build_controller(
            mode="fallback",
            document_type=st.session_state.patient_document_type,
            document_path=st.session_state.patient_document_path,
        )
        st.session_state.backend_warning = f"BioGears backend unavailable, using fallback simulation: {exc}"
if "last_wall_time" not in st.session_state:
    st.session_state.last_wall_time = time.time()

with st.sidebar:
    st.header("Simulation")
    mode = st.session_state.backend_mode

    st.markdown("---")
    st.subheader("Patient Document")
    document_type = st.radio(
        "Document type",
        options=["none", "state_file", "patient_file"],
        index=["none", "state_file", "patient_file"].index(st.session_state.patient_document_type),
        format_func=lambda v: {
            "none": "Default standard patient",
            "state_file": "BioGears state file (.xml)",
            "patient_file": "BioGears patient file (.xml)",
        }[v],
    )
    document_path = st.text_input(
        "Document path",
        value=st.session_state.patient_document_path,
        disabled=document_type == "none",
        help="Absolute or workspace-relative path to a BioGears XML state/patient file.",
    )
    uploaded = st.file_uploader("Or upload patient/state XML", type=["xml"])


    st.session_state.patient_document_type = document_type
    st.session_state.patient_document_path = document_path

    if st.button("Load patient document", disabled=document_type == "none"):
        selected_path = document_path.strip()
        if uploaded is not None:
            upload_dir = Path("uploaded_docs")
            upload_dir.mkdir(parents=True, exist_ok=True)
            target = upload_dir / uploaded.name
            target.write_bytes(uploaded.getvalue())
            selected_path = str(target)

        st.session_state.patient_document_path = selected_path

        try:
            metadata = parse_document_metadata(selected_path)
            snapshot = extract_document_snapshot(selected_path)
            ml_label, ml_conf = classify_disease_from_model(metadata["resolved_path"])
            st.session_state.detected_disease = ml_label
            st.session_state.disease_confidence = ml_conf
            st.session_state.patient_document_snapshot = snapshot
            st.session_state.loaded_patient_summary = f"{document_type}: {metadata['document_name']} → {snapshot['xml_root']}"
            st.session_state.patient_document_path = metadata["resolved_path"]
            st.session_state.controller = build_controller(mode, document_type, selected_path)
            st.session_state.backend_warning = ""
        except Exception as exc:
            st.session_state.loaded_patient_summary = "Patient document load failed"
            st.session_state.detected_disease = ""
            st.session_state.disease_confidence = "N/A"
            st.session_state.patient_document_snapshot = {}
            st.session_state.patient_document_type = "none"
            st.session_state.patient_document_path = ""
            st.session_state.controller = build_controller("fallback", "none", "")
            st.session_state.backend_warning = f"Could not initialize requested backend with patient document; fallback simulation is active: {exc}"
        st.session_state.last_wall_time = time.time()
        st.rerun()

    # Backend is internal-only (auto/fallback); no manual selector in the UI.

    running = st.checkbox("Run simulation", value=True)
    if st.button("Reset"):
        try:
            st.session_state.controller = build_controller(
                mode=st.session_state.backend_mode,
                document_type=st.session_state.patient_document_type,
                document_path=st.session_state.patient_document_path,
            )
            st.session_state.backend_warning = ""
        except Exception as exc:
            st.session_state.controller = build_controller(mode="fallback", document_type="none", document_path="")
            st.session_state.backend_warning = f"Backend reset fell back to simulation: {exc}"
        st.session_state.last_wall_time = time.time()
        st.rerun()

if st.session_state.backend_warning:
    # Hide expected missing-binding noise when running in fallback-only environments.
    if "BioGears Python bindings are not available" not in st.session_state.backend_warning:
        st.warning(st.session_state.backend_warning)

if st.session_state.patient_document_path:
    st.caption(f"Loaded patient document: `{st.session_state.patient_document_path}`")

if st.session_state.patient_document_snapshot:
    with st.expander("Linked input data → BioGears context", expanded=True):
        st.json(st.session_state.patient_document_snapshot)

context_col1, context_col2, context_col3 = st.columns(3)
context_col1.metric("Patient Source", st.session_state.loaded_patient_summary)
context_col2.metric("Detected Condition", st.session_state.detected_disease or "Unspecified")
context_col3.metric("Model Confidence", st.session_state.disease_confidence)


controller: SimulationController = st.session_state.controller

if controller.history:
    latest = controller.history[-1]
else:
    latest = controller.step(0.1)

if running:
    now = time.time()
    elapsed = max(now - st.session_state.last_wall_time, 0.1)
    steps = max(1, int(elapsed / 0.2))
    dt = elapsed / steps
    for _ in range(steps):
        latest = controller.step(dt)
    st.session_state.last_wall_time = now
else:
    st.session_state.last_wall_time = time.time()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Heart Rate (bpm)", f"{latest.heart_rate_bpm:.1f}")
c2.metric("Blood Pressure (mmHg)", f"{latest.systolic_bp_mmhg:.0f}/{latest.diastolic_bp_mmhg:.0f}")
c3.metric("Cardiac Output (L/min)", f"{latest.cardiac_output_l_min:.2f}")
c4.metric("SpO2 (%)", f"{latest.spo2_fraction * 100.0:.1f}")

try:
    write_live_biogears_snapshot(
        latest=latest,
        source_summary=st.session_state.loaded_patient_summary,
        disease_label=st.session_state.detected_disease,
    )
except Exception:
    pass


with st.expander("Trigger Events", expanded=True):
    h1, h2, h3 = st.columns(3)

    with h1:
        st.subheader("Hemorrhage")
        hemorrhage_rate = st.slider("Rate (mL/min)", min_value=10, max_value=500, value=180, step=10)
        hemorrhage_duration = st.slider("Duration (s)", min_value=10, max_value=300, value=90, step=5)
        col_start_h, col_stop_h = st.columns(2)
        with col_start_h:
            if st.button("Start hemorrhage"):
                controller.trigger_hemorrhage(float(hemorrhage_rate), float(hemorrhage_duration))
                st.session_state.hemorrhage_active = True
        with col_stop_h:
            if st.button("Stop hemorrhage", disabled=not st.session_state.hemorrhage_active):
                controller.stop_hemorrhage()
                st.session_state.hemorrhage_active = False

    with h2:
        st.subheader("Drug Injection")
        drug_name = st.text_input("Substance name", value="Epinephrine")
        drug_dose = st.slider("Dose (mg)", min_value=1.0, max_value=20.0, value=5.0, step=0.5)
        col_start_d, col_stop_d = st.columns(2)
        with col_start_d:
            if st.button("Inject bolus"):
                controller.trigger_drug_injection(drug_name, float(drug_dose))
                st.session_state.drug_active = True
        with col_stop_d:
            if st.button("Stop injection", disabled=not st.session_state.drug_active):
                controller.stop_drug_injection(drug_name)
                st.session_state.drug_active = False

    with h3:
        st.subheader("Exercise")
        exercise_intensity = st.slider("Intensity", min_value=0.1, max_value=1.0, value=0.6, step=0.1)
        exercise_duration = st.slider("Duration (s) ", min_value=10, max_value=600, value=180, step=10)
        col_start_e, col_stop_e = st.columns(2)
        with col_start_e:
            if st.button("Start exercise"):
                controller.trigger_exercise(float(exercise_intensity), float(exercise_duration))
                st.session_state.exercise_active = True
        with col_stop_e:
            if st.button("Stop exercise", disabled=not st.session_state.exercise_active):
                controller.stop_exercise()
                st.session_state.exercise_active = False

frame = controller.history_frame()
if frame.empty:
    st.info("Run the simulation to populate charts.")
else:
    if st.session_state.patient_document_snapshot:
        frame = frame.copy()
        frame["input_document_name"] = st.session_state.patient_document_snapshot.get("document_name", "")
        frame["input_root_tag"] = st.session_state.patient_document_snapshot.get("xml_root", "")
        frame["input_disease_label"] = st.session_state.detected_disease or "Unspecified"

    display_columns = [
        "time_s",
        "heart_rate_bpm",
        "systolic_bp_mmhg",
        "diastolic_bp_mmhg",
        "cardiac_output_l_min",
        "spo2_percent",
    ]
    if "input_document_name" in frame.columns:
        display_columns += ["input_document_name", "input_root_tag", "input_disease_label"]

    st.dataframe(
        frame[display_columns].tail(25),
        use_container_width=True,
        height=320,
    )
    st.line_chart(frame.set_index("time_s")[["heart_rate_bpm"]], height=200)
    st.line_chart(frame.set_index("time_s")[["systolic_bp_mmhg", "diastolic_bp_mmhg"]], height=250)
    st.line_chart(frame.set_index("time_s")[["cardiac_output_l_min"]], height=200)
    st.line_chart(frame.set_index("time_s")[["spo2_percent"]], height=200)

if running:
    time.sleep(0.5)
    st.rerun()


