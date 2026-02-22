# src/generate_logs.py
from __future__ import annotations
import os
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

random.seed(42)
np.random.seed(42)

FAIL_REASONS = ["battery_sag", "link_drop", "overheat", "sensor_glitch", "unknown"]

@dataclass
class SessionConfig:
    session_id: str
    duration_s: int
    base_voltage: float = 16.8   # 4S full
    base_temp_c: float = 30.0

def generate_session(cfg: SessionConfig) -> pd.DataFrame:
    t = np.arange(0, cfg.duration_s, 1)

    # battery model (simple): voltage droops with time + current
    current = np.clip(np.random.normal(18, 4, size=len(t)), 5, 35)
    voltage = cfg.base_voltage - 0.0025 * t - 0.015 * (current - 18) + np.random.normal(0, 0.05, len(t))
    voltage = np.clip(voltage, 12.0, cfg.base_voltage)

    # temp rises with load and time
    cpu_load = np.clip(np.random.normal(55, 15, size=len(t)), 10, 95)
    temp = cfg.base_temp_c + 0.01 * t + 0.08 * (cpu_load - 55) + np.random.normal(0, 0.3, len(t))
    temp = np.clip(temp, 20, 110)

    # link quality occasionally drops
    link = np.clip(np.random.normal(0.92, 0.06, size=len(t)), 0.0, 1.0)
    # inject sporadic drops
    for _ in range(random.randint(0, 3)):
        start = random.randint(0, max(0, cfg.duration_s - 20))
        link[start:start+random.randint(5, 20)] -= np.random.uniform(0.25, 0.6)
    link = np.clip(link, 0.0, 1.0)

    df = pd.DataFrame({
        "session_id": cfg.session_id,
        "t_s": t,
        "voltage_v": voltage,
        "current_a": current,
        "temp_c": temp,
        "cpu_load_pct": cpu_load,
        "link_q": link,
    })

    # events
    df["event"] = "OK"
    df.loc[df["voltage_v"] < 13.2, "event"] = "WARN_BATTERY"
    df.loc[df["link_q"] < 0.45, "event"] = "WARN_LINK"
    df.loc[df["temp_c"] > 85, "event"] = "WARN_TEMP"

    # maybe fail once
    if random.random() < 0.35:
        fail_t = random.randint(int(cfg.duration_s*0.3), cfg.duration_s-1)
        reason = random.choice(FAIL_REASONS)
        df.loc[df["t_s"] >= fail_t, "event"] = "FAIL"
        df["fail_reason"] = ""
        df.loc[df["t_s"] >= fail_t, "fail_reason"] = reason
    else:
        df["fail_reason"] = ""

    return df

def main(out_dir: str = "data/raw", n_sessions: int = 30):
    os.makedirs(out_dir, exist_ok=True)
    start = datetime.now()

    manifest = []
    for i in range(n_sessions):
        sid = f"S{i+1:03d}"
        dur = random.randint(180, 720)
        cfg = SessionConfig(session_id=sid, duration_s=dur, base_temp_c=random.uniform(22, 38))
        df = generate_session(cfg)

        path = os.path.join(out_dir, f"{sid}.csv")
        df.to_csv(path, index=False)
        manifest.append({"session_id": sid, "duration_s": dur, "file": path})

    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"generated_at": start.isoformat(), "sessions": manifest}, f, ensure_ascii=False, indent=2)

    print(f"Generated {n_sessions} sessions into {out_dir}")

if __name__ == "__main__":
    main()