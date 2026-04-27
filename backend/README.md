# Heart Signal Backend

This backend reads `input.csv`, detects heart peaks, computes BPM, and writes `output.json` for the Three.js frontend.

## Data format

`input.csv` supports either:

1. One column: `signal`
2. Two columns: `time,signal`

A header row is optional.

## Run

From the `backend` folder:

```powershell
python process.py
```

Expected terminal output:

- `BPM: <value>`
- `Saved: <absolute path to output.json>`

## Output JSON contract

```json
{
  "bpm": 72,
  "signal": [0.01, -0.02, 0.15],
  "sampling_rate_hz": 100.0,
  "peak_indices": [60, 144, 228]
}
```

