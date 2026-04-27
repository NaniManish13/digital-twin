from __future__ import annotations

from dataclasses import dataclass
from math import exp, log
import pickle
from pathlib import Path
import re
from typing import Iterable
import xml.etree.ElementTree as ET


TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_\-/]*")


@dataclass(frozen=True)
class DiseasePrediction:
    label: str
    confidence: float
    model_path: str


def disease_label_from_filename(file_stem: str) -> str:
    stem = file_stem.lower()
    if stem.startswith("hemorrhage") or "hemorrhage" in stem or "txa" in stem:
        return "Hemorrhage"
    if "septicshock" in stem:
        return "SepticShock"
    if "sepsis" in stem:
        return "Sepsis"
    if "brady" in stem:
        return "SinusBradycardia"
    if "tachy" in stem:
        return "SinusTachycardia"
    if "anemia" in stem:
        return "Anemia"
    if "effusion" in stem:
        return "PericardialEffusion"
    if "stenosis" in stem:
        return "RenalStenosis"
    if "ventricular" in stem or "dysfunction" in stem:
        return "VentricularDysfunction"
    if "braininjury" in stem:
        return "BrainInjury"
    if "pain" in stem:
        return "PainStimulus"
    if "dehydrate" in stem:
        return "Dehydration"
    if "acutestress" in stem:
        return "AcuteStress"
    if "cpr" in stem:
        return "CardiacArrestCPR"
    if "ivfluids" in stem or "saline" in stem:
        return "FluidResuscitation"
    if "medic" in stem:
        return "TraumaMedicProtocol"
    if "baroreceptors" in stem:
        return "BaroreflexChallenge"
    return "OtherCondition"


def _xml_feature_text(xml_path: Path) -> str:
    raw = xml_path.read_text(encoding="utf-8", errors="ignore")
    tokens = [xml_path.stem]

    try:
        root = ET.parse(xml_path).getroot()
        for elem in root.iter():
            tag = re.sub(r"^\{.*\}", "", elem.tag)
            tokens.append(tag)
            for key, value in elem.attrib.items():
                tokens.append(key)
                tokens.append(str(value))
            if elem.text:
                text = elem.text.strip()
                if text:
                    tokens.append(text)
    except Exception:
        pass

    return "\n".join(tokens) + "\n" + raw


def _tokenize(text: str) -> list[str]:
    lowered = text.lower()
    return TOKEN_RE.findall(lowered)


def _iter_ngrams(tokens: Iterable[str], n: int = 2) -> list[str]:
    token_list = list(tokens)
    if len(token_list) < n:
        return []
    return ["::".join(token_list[i : i + n]) for i in range(len(token_list) - n + 1)]


def _extract_features(xml_path: Path) -> list[str]:
    text = _xml_feature_text(xml_path)
    tokens = _tokenize(text)
    bigrams = _iter_ngrams(tokens, n=2)
    return tokens + bigrams


def train_classifier(patients_dir: Path, model_output_path: Path) -> Path:
    if not patients_dir.exists():
        raise FileNotFoundError(f"Patients directory not found: {patients_dir}")

    xml_files = sorted(patients_dir.glob("*.xml"))
    if not xml_files:
        raise RuntimeError(f"No XML files found in {patients_dir}")

    labels = [disease_label_from_filename(path.stem) for path in xml_files]
    classes = sorted(set(labels))

    class_doc_count = {label: 0 for label in classes}
    class_token_total = {label: 0 for label in classes}
    class_token_counts: dict[str, dict[str, int]] = {label: {} for label in classes}
    vocabulary: set[str] = set()

    for xml_path, label in zip(xml_files, labels):
        class_doc_count[label] += 1
        features = _extract_features(xml_path)
        for token in features:
            vocabulary.add(token)
            class_token_total[label] += 1
            current = class_token_counts[label].get(token, 0)
            class_token_counts[label][token] = current + 1

    payload = {
        "classes": classes,
        "class_doc_count": class_doc_count,
        "class_token_total": class_token_total,
        "class_token_counts": class_token_counts,
        "vocabulary_size": max(1, len(vocabulary)),
        "doc_count": len(xml_files),
        "train_files": [p.name for p in xml_files],
    }

    model_output_path.parent.mkdir(parents=True, exist_ok=True)
    with model_output_path.open("wb") as handle:
        pickle.dump(payload, handle)

    return model_output_path


def predict_disease(xml_path: Path, model_path: Path) -> DiseasePrediction:
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    with model_path.open("rb") as handle:
        payload = pickle.load(handle)

    classes: list[str] = payload["classes"]
    class_doc_count: dict[str, int] = payload["class_doc_count"]
    class_token_total: dict[str, int] = payload["class_token_total"]
    class_token_counts: dict[str, dict[str, int]] = payload["class_token_counts"]
    vocabulary_size: int = payload["vocabulary_size"]
    doc_count: int = payload["doc_count"]

    features = _extract_features(xml_path)

    log_scores: dict[str, float] = {}
    for label in classes:
        prior = (class_doc_count[label] + 1.0) / (doc_count + len(classes))
        log_prob = log(prior)
        denom = class_token_total[label] + vocabulary_size
        token_counts = class_token_counts[label]
        for token in features:
            count = token_counts.get(token, 0)
            log_prob += log((count + 1.0) / denom)
        log_scores[label] = log_prob

    max_log = max(log_scores.values())
    probs = {label: exp(score - max_log) for label, score in log_scores.items()}
    total = sum(probs.values())
    normalized = {label: val / total for label, val in probs.items()}

    best_label = max(normalized, key=normalized.get)
    return DiseasePrediction(
        label=best_label,
        confidence=float(normalized[best_label]),
        model_path=str(model_path),
    )


def train_if_missing_and_predict(
    xml_path: Path,
    patients_dir: Path,
    model_path: Path,
) -> DiseasePrediction:
    if not model_path.exists():
        train_classifier(patients_dir, model_path)
    return predict_disease(xml_path, model_path)

