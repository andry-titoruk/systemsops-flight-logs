# SystemsOps Flight Logs

Synthetic telemetry → ETL → reliability metrics → dashboard.

A small systems-oriented reliability analytics pipeline built on synthetic drone telemetry data.

---

## 🎯 Problem

Flight test sessions generate large volumes of telemetry logs.  
Raw CSV files are hard to analyze directly and do not provide structured insight into:

- Failure rate
- Time to first failure
- Warning density
- Reliability bottlenecks
- Risk patterns across sessions

This project builds a minimal internal reliability analytics system that:

1. Generates synthetic telemetry sessions
2. Normalizes raw logs via ETL
3. Stores structured data in SQLite
4. Enables metric computation and future dashboarding

---

## 🏗 Architecture

### Data Layers

| Layer | Description |
|-------|------------|
| `data/raw` | Synthetic per-session telemetry logs |
| `data/processed` | Normalized SQLite database |
| `src/generate_logs.py` | Telemetry generator |
| `src/etl.py` | Raw → structured database |
| `src/metrics.py` | Reliability metrics layer (next milestone) |
| `src/dashboard.py` | Visualization layer (future milestone) |

---

## 📊 Current Capabilities

✔ Generate synthetic telemetry sessions  
✔ Normalize logs into structured SQLite database  
✔ Create two core tables:

### `telemetry`
- Per-second flight telemetry
- Events (OK / WARN / FAIL)
- Link, voltage, temperature, CPU load

### `sessions`
- One row per session
- Duration
- Failure flag
- Failure reason
- First failure timestamp

---

## 🧠 Why This Matters

In real-world robotics / miltech systems:

- Raw logs are useless without structure.
- Reliability metrics drive engineering decisions.
- Bottleneck detection improves survivability and robustness.
- Product decisions require quantitative telemetry analysis.

This project simulates that workflow.

---

## ⚙ Stack

- Python
- pandas
- SQLite
- matplotlib (future)
- Streamlit (future)

---

## 🚀 How to Run

### 1. Generate synthetic logs
```bash
python -m src.generate_logs
```
### 2. Run ETL
```bash
python -m src.etl
```

Database will be created at:
`data/processed/telemetry.db`

---

## 🗺 Roadmap

- [x] Synthetic telemetry generator
- [x] ETL → SQLite
- [ ] Reliability metrics computation
- [ ] Risk scoring
- [ ] Interactive dashboard
- [ ] Decision log & engineering prioritization layer