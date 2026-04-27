# BioGears Cardiovascular Scenario Integration

This project integrates the 33 scenario XML files in `patients/` into one cohesive Python simulation runner.

- Parses each scenario XML (patient/state loading, ordered actions, and data requests)
- Replays actions on either a BioGears backend (`pybiogears` / `biogears`) or fallback physiology model
- Advances simulation in strict 1-second steps with per-second cardiovascular logging
- Labels each row with clinical state (`NORMAL`, `COMPENSATING`, `DECOMPENSATING`, `CRITICAL`)
- Produces action audit trails (CSV + JSON) and comparison CSVs for the required scenario pairs

## Project layout

- `biogears_sim/engine.py` - backend adapters and low-level action injection
- `biogears_sim/actions.py` - action dispatcher and normalized payload mapping
- `biogears_sim/scenario_parser.py` - XML parser for all scenarios and data request plans
- `biogears_sim/data_logger.py` - metrics and action audit writers
- `biogears_sim/scenario_runner.py` - one-scenario execution engine
- `biogears_sim/comparison_runner.py` - side-by-side differential runner
- `main.py` - CLI for single scenario, all scenarios, and default comparisons
- `app.py` - live dashboard

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run integrated scenarios

Run one scenario:

```powershell
python main.py --backend fallback scenario HemorrhageClass2Blood
```

Run all 33 scenarios:

```powershell
python main.py --backend fallback all
```

Run required comparison pairs:

```powershell
python main.py --backend fallback compare
```

Common options:

- `--backend auto|biogears|fallback`
- `--patients-dir patients`
- `--output-dir outputs`
- `--max-duration-s <seconds>` optional cap for dry-runs or quick validation

Generated outputs per scenario:

- `<ScenarioName>_metrics.csv`
- `<ScenarioName>_action_audit.csv`
- `<ScenarioName>_action_audit.json`
- `<ScenarioName>_data_requests.csv`

Generated outputs per comparison:

- `comparison_<ScenarioA>_vs_<ScenarioB>.csv`

## Dashboard

```powershell
streamlit run app.py
```

The dashboard includes a live 3D heart model driven by current simulation vitals (HR, BP, SpO2, CO).
Users can load patient/state XML documents and see disease prediction plus 3D heart response in real time.

## Disease Classification Model (XML -> Disease Type)

The app now includes an ML classifier trained from all XML files in `patients/`.
When a user uploads a patient/state XML, the dashboard predicts the most likely disease type and shows confidence.

Train or refresh the model manually:

```powershell
python train_disease_classifier.py --patients-dir patients --model-out models/disease_classifier.pkl
```

The dashboard also auto-trains this model if `models/disease_classifier.pkl` is missing.


## Tests

```powershell
python -m unittest discover -s tests -v
```


