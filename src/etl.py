# src/etl.py
from __future__ import annotations

import json
import os
import sqlite3
from glob import glob
from typing import Optional

import pandas as pd


RAW_DIR = "data/raw"
OUT_DB = "data/processed/telemetry.db"


def _load_manifest(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_one_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    # normalize dtypes (important for stable ETL)
    df["session_id"] = df["session_id"].astype(str)
    df["t_s"] = df["t_s"].astype(int)

    for col in ["voltage_v", "current_a", "temp_c", "cpu_load_pct", "link_q"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["event"] = df["event"].astype(str)
    df["fail_reason"] = df.get("fail_reason", "").fillna("").astype(str)

    return df


def _build_sessions_table(telemetry: pd.DataFrame, generated_at: Optional[str]) -> pd.DataFrame:
    # duration = max t + 1 per session
    duration = telemetry.groupby("session_id")["t_s"].max().add(1).rename("duration_s")

    # find first FAIL moment (if any)
    fail_rows = telemetry[telemetry["event"] == "FAIL"].copy()
    if not fail_rows.empty:
        first_fail = fail_rows.groupby("session_id")["t_s"].min().rename("first_fail_t_s")
        # take the fail_reason at first fail time
        fail_rows = fail_rows.merge(first_fail, on="session_id", how="inner")
        first_fail_reason = (
            fail_rows[fail_rows["t_s"] == fail_rows["first_fail_t_s"]]
            .groupby("session_id")["fail_reason"]
            .first()
            .rename("fail_reason")
        )
        had_fail = first_fail.notna().astype(int).rename("had_fail")
    else:
        first_fail = pd.Series(dtype="float64", name="first_fail_t_s")
        first_fail_reason = pd.Series(dtype="object", name="fail_reason")
        had_fail = pd.Series(dtype="int64", name="had_fail")

    sessions = pd.concat([duration, had_fail, first_fail, first_fail_reason], axis=1).reset_index()
    sessions["had_fail"] = sessions["had_fail"].fillna(0).astype(int)
    sessions["first_fail_t_s"] = sessions["first_fail_t_s"].astype("Int64")
    sessions["fail_reason"] = sessions["fail_reason"].fillna("").astype(str)
    sessions["generated_at"] = generated_at or ""

    # session_id as primary key later
    return sessions[["session_id", "duration_s", "had_fail", "fail_reason", "first_fail_t_s", "generated_at"]]


def run_etl(raw_dir: str = RAW_DIR, out_db: str = OUT_DB) -> None:
    os.makedirs(os.path.dirname(out_db), exist_ok=True)

    manifest_path = os.path.join(raw_dir, "manifest.json")
    generated_at = None
    if os.path.exists(manifest_path):
        manifest = _load_manifest(manifest_path)
        generated_at = manifest.get("generated_at")

    csv_paths = sorted(glob(os.path.join(raw_dir, "S*.csv")))
    if not csv_paths:
        raise FileNotFoundError(f"No session CSV files found in {raw_dir}")

    telemetry_frames = [_read_one_csv(p) for p in csv_paths]
    telemetry = pd.concat(telemetry_frames, ignore_index=True)

    # sessions summary table
    sessions = _build_sessions_table(telemetry, generated_at)

    # write to sqlite
    with sqlite3.connect(out_db) as conn:
        telemetry.to_sql("telemetry", conn, if_exists="replace", index=False)
        sessions.to_sql("sessions", conn, if_exists="replace", index=False)

        # indexes for speed
        conn.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_session ON telemetry(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_event ON telemetry(event)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_telemetry_session_t ON telemetry(session_id, t_s)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_sessions_session ON sessions(session_id)")

    print(f"ETL complete ✅  telemetry rows: {len(telemetry):,}  sessions: {len(sessions):,}")
    print(f"SQLite written to: {out_db}")


if __name__ == "__main__":
    run_etl()