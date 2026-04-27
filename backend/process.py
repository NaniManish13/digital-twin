from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks


def load_signal(csv_path: Path) -> tuple[np.ndarray, np.ndarray]:
    times: list[float] = []
    values: list[float] = []

    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        # Keep only non-empty rows so trailing blank lines do not break parsing.
        rows = [row for row in reader if row and any(cell.strip() for cell in row)]

    if not rows:
        raise ValueError("input.csv is empty")

    has_header = False
    first = rows[0]
    if first and any(ch.isalpha() for cell in first for ch in cell):
        has_header = True

    data_rows = rows[1:] if has_header else rows
    if not data_rows:
        raise ValueError("No signal rows found in input.csv")

    if len(data_rows[0]) == 1:
        # Single-column mode: infer time using index/sample rate later.
        for idx, row in enumerate(data_rows):
            values.append(float(row[0].strip()))
            times.append(float(idx))
    else:
        # Two-column mode: expected time,signal.
        for row in data_rows:
            times.append(float(row[0].strip()))
            values.append(float(row[1].strip()))

    return np.asarray(times, dtype=float), np.asarray(values, dtype=float)


def estimate_sampling_rate(time_axis: np.ndarray) -> float:
    if len(time_axis) < 2:
        return 100.0

    diffs = np.diff(time_axis)
    median_dt = float(np.median(diffs))
    if median_dt <= 0:
        return 100.0

    # If time axis looks like sample index, default to 100 Hz.
    if median_dt >= 1.0:
        return 100.0

    return 1.0 / median_dt


def normalize_signal(raw_signal: np.ndarray) -> np.ndarray:
    centered = raw_signal - np.mean(raw_signal)
    std = np.std(centered)
    if std == 0:
        return np.zeros_like(centered)
    return centered / std


def compute_bpm(cleaned_signal: np.ndarray, duration_seconds: float, sampling_rate_hz: float) -> tuple[int, np.ndarray]:
    min_peak_distance = int(0.45 * sampling_rate_hz)
    min_peak_distance = max(min_peak_distance, 1)

    # Adaptive threshold keeps detection stable across low/high-amplitude signals.
    adaptive_height = max(float(np.percentile(cleaned_signal, 75)), 0.2)
    peaks, _ = find_peaks(
        cleaned_signal,
        distance=min_peak_distance,
        prominence=0.4,
        height=adaptive_height,
    )

    if duration_seconds <= 0:
        raise ValueError("Invalid duration computed from signal")

    bpm = int(round((len(peaks) / duration_seconds) * 60.0))
    return bpm, peaks


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    input_path = base_dir / "input.csv"
    output_path = base_dir / "output.json"

    time_axis, signal = load_signal(input_path)
    sampling_rate = estimate_sampling_rate(time_axis)
    if len(time_axis) > 1 and np.all(np.diff(time_axis) > 0) and np.median(np.diff(time_axis)) < 1.0:
        duration_seconds = float(time_axis[-1] - time_axis[0])
    else:
        duration_seconds = float(len(signal) / sampling_rate)

    cleaned = normalize_signal(signal)
    bpm, peaks = compute_bpm(cleaned, duration_seconds, sampling_rate)

    payload = {
        "bpm": bpm,
        "signal": cleaned.tolist(),
        "sampling_rate_hz": sampling_rate,
        "peak_indices": peaks.tolist(),
    }

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    print(f"BPM: {bpm}")
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()

