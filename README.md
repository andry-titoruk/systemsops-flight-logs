# 🚀 SystemsOps Flight Logs

Synthetic telemetry → ETL → reliability analytics → calibrated risk scoring → dashboard (next milestone)

A systems-oriented reliability analytics pipeline built on synthetic drone telemetry data.  
The project simulates how raw flight logs become structured engineering insights.

---

# 🎯 Problem

Flight test sessions generate large volumes of telemetry logs.  
Raw CSV files alone do not provide structured insight into:

- Failure rate
- Time to first failure (MTTF)
- Warning density
- Degradation patterns
- Risk stratification across sessions

Engineering teams need structured reliability metrics to:

- Detect weak subsystems
- Prioritize engineering effort
- Quantify operational risk
- Improve survivability and robustness

This project builds a minimal internal reliability analytics system to simulate that workflow.

---

# 🏗 Architecture

## Data Flow


Synthetic Generator
↓
Raw CSV logs (data/raw)
↓
ETL normalization
↓
SQLite database (data/processed/telemetry.db)
↓
Session-level reliability metrics
↓
Calibrated risk classification
↓
Dashboard (next milestone)


---

# 📊 Current Capabilities

## ✅ Synthetic telemetry generator

Generates multiple session profiles:

- **Normal**
- **Degraded**
- **Failure-prone**

Simulates:

- Battery sag
- Link drops
- Thermal overload
- Random subsystem failures

Each session includes:
- Per-second telemetry
- Event tagging (OK / WARN / FAIL)
- Failure reason attribution

---

## ✅ ETL → SQLite

Normalizes raw logs into:

### `telemetry`
- Per-second flight telemetry
- Events
- Voltage, temperature, link quality, CPU load

### `sessions`
- One row per session
- Duration
- Failure flag
- Failure reason
- Time to first failure

ETL is idempotent and safe to re-run.

---

## ✅ Multi-Factor Reliability Scoring

Each session receives a composite score:


Score = 100
- 60 × had_fail
- 40 × warning_density
- 20 × battery_sag_pct
- 15 × link_drop_pct
- 15 × overheat_pct


Where:

- `warning_density` = WARN time / total session time
- `battery_sag_pct` = time under safe voltage threshold
- `link_drop_pct` = time below link quality threshold
- `overheat_pct` = time above temperature threshold

Scores are clipped to `[0, 100]`.

---

## ✅ Percentile-Based Risk Calibration

Instead of fixed thresholds, risk classes are calibrated dynamically:

- **HIGH**  → bottom 20% of sessions
- **MEDIUM** → next 30%
- **LOW** → top 50%

This ensures robust stratification even when score distributions shift.

The system prints calibrated score boundaries at runtime.

---

# 📈 Example Output


Sessions: 30
Failures: 4 (13.33%)
Mean time to first failure: 274.2 s

Risk class distribution:
HIGH: 6
MEDIUM: 9
LOW: 15


Top worst sessions include degradation metrics and root causes.

---

# 🧠 Engineering Insight

This pipeline demonstrates:

- Structured telemetry normalization
- Reliability metric engineering
- Multi-factor risk modeling
- Dynamic percentile calibration
- Separation of data layer vs scoring logic

The architecture mirrors real-world robotics / defense telemetry workflows.

---

# ⚙ Stack

- Python
- pandas
- SQLite
- NumPy
- (Next) Streamlit

---

# 🚀 How to Run

### 1️⃣ Generate synthetic logs

```bash
python -m src.generate_logs
```
### 2️⃣ Run ETL
```bash
python -m src.etl
```
Database will be created at:
```bash
data/processed/telemetry.db
```

### 3️⃣ Compute reliability metrics
```bash
python -m src.metrics
```
Per-session metrics will be exported to:

```bash
data/processed/metrics_sessions.csv
```
🔜 Next Milestone

- Interactive Streamlit dashboard:
- KPI cards (Failure rate, MTTF)
- Reliability score histogram
- Risk distribution visualization
- Session filtering
- Telemetry drill-down per session

# 📌 Why This Matters

In real-world robotics and miltech systems:

Raw logs are useless without structure.

Reliability metrics drive engineering prioritization.

Risk stratification informs mission planning.

Data-driven telemetry analysis improves survivability.

This project simulates that decision-support layer.

👤 Author

Andrii Titoruk
Data-driven performance & systems analyst.

---