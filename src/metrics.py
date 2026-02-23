import os
import sqlite3
import pandas as pd

DB_PATH = "data/processed/telemetry.db"
OUT_DIR = "data/processed"
OUT_SESSIONS_CSV = os.path.join(OUT_DIR, "metrics_sessions.csv")


# --- thresholds (domain assumptions) ---
BATTERY_WARN_V = 13.2
LINK_WARN_Q = 0.45
TEMP_WARN_C = 85.0


def get_connection():
    return sqlite3.connect(DB_PATH)


def load_tables():
    with get_connection() as conn:
        telemetry = pd.read_sql("SELECT * FROM telemetry", conn)
        sessions = pd.read_sql("SELECT * FROM sessions", conn)
    return telemetry, sessions


def compute_session_metrics(telemetry_df: pd.DataFrame, sessions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns one row per session with multi-factor reliability metrics.
    """
    # total rows per session (each row ~ 1 second)
    total_rows = telemetry_df.groupby("session_id").size().rename("rows_total")

    # warning density: WARN rows / total rows
    warn_rows = telemetry_df[telemetry_df["event"].str.startswith("WARN", na=False)].groupby("session_id").size()
    warning_density = (warn_rows / total_rows).fillna(0.0).rename("warning_density")

    # degradation signals (percent of time in "bad" state)
    battery_sag_rows = telemetry_df[telemetry_df["voltage_v"] < BATTERY_WARN_V].groupby("session_id").size()
    link_drop_rows = telemetry_df[telemetry_df["link_q"] < LINK_WARN_Q].groupby("session_id").size()
    overheat_rows = telemetry_df[telemetry_df["temp_c"] > TEMP_WARN_C].groupby("session_id").size()

    battery_sag_pct = (battery_sag_rows / total_rows).fillna(0.0).rename("battery_sag_pct")
    link_drop_pct = (link_drop_rows / total_rows).fillna(0.0).rename("link_drop_pct")
    overheat_pct = (overheat_rows / total_rows).fillna(0.0).rename("overheat_pct")

    out = sessions_df.copy()

    # attach aggregates
    out = out.merge(total_rows.reset_index(), on="session_id", how="left")
    out = out.merge(warning_density.reset_index(), on="session_id", how="left")
    out = out.merge(battery_sag_pct.reset_index(), on="session_id", how="left")
    out = out.merge(link_drop_pct.reset_index(), on="session_id", how="left")
    out = out.merge(overheat_pct.reset_index(), on="session_id", how="left")

    for col in ["rows_total", "warning_density", "battery_sag_pct", "link_drop_pct", "overheat_pct"]:
        out[col] = out[col].fillna(0)

    # convenience
    out["time_to_first_fail_s"] = out["first_fail_t_s"]

    return out


def compute_reliability_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Multi-factor score:
    - had_fail is a big penalty
    - warning_density and degradation signals are moderate penalties
    Score is clipped to [0, 100].
    """
    df = df.copy()

    # Penalties (weights can be tuned later)
    # Interpreting densities as 0..1. We map them to points.
    fail_penalty = 60 * df["had_fail"]
    warn_penalty = 25 * df["warning_density"]
    battery_penalty = 10 * df["battery_sag_pct"]
    link_penalty = 10 * df["link_drop_pct"]
    temp_penalty = 10 * df["overheat_pct"]

    df["reliability_score"] = 100 - (fail_penalty + warn_penalty + battery_penalty + link_penalty + temp_penalty)
    df["reliability_score"] = df["reliability_score"].clip(0, 100)

    # Risk classes (simple, readable thresholds)
    df["risk_class"] = pd.cut(
        df["reliability_score"],
        bins=[-0.1, 70, 85, 100.1],
        labels=["HIGH", "MEDIUM", "LOW"],
        include_lowest=True,
    )

    return df


def print_summary(df: pd.DataFrame) -> None:
    n = len(df)
    fails = int(df["had_fail"].sum())
    failure_rate = fails / n if n else 0.0

    failed = df[df["had_fail"] == 1]
    mttf = float(failed["time_to_first_fail_s"].dropna().mean()) if not failed.empty else None

    print(f"Sessions: {n}")
    print(f"Failures: {fails} (failure_rate={failure_rate:.2%})")
    if mttf is not None:
        print(f"Mean time to first failure (failed sessions): {mttf:.1f} s")
    else:
        print("Mean time to first failure: N/A (no failed sessions)")

    print("\nRisk class distribution:")
    print(df["risk_class"].value_counts(dropna=False))

    print("\nTop 10 worst sessions (lowest score):")
    cols = [
        "session_id",
        "had_fail",
        "fail_reason",
        "time_to_first_fail_s",
        "warning_density",
        "battery_sag_pct",
        "link_drop_pct",
        "overheat_pct",
        "reliability_score",
        "risk_class",
    ]
    print(df.sort_values("reliability_score").head(10)[cols].to_string(index=False))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    telemetry_df, sessions_df = load_tables()
    session_metrics = compute_session_metrics(telemetry_df, sessions_df)
    session_metrics = compute_reliability_score(session_metrics)

    # Save for future dashboard
    session_metrics.to_csv(OUT_SESSIONS_CSV, index=False)

    print("Metrics computed ✅")
    print(f"- per-session metrics: {OUT_SESSIONS_CSV}\n")
    print_summary(session_metrics)


if __name__ == "__main__":
    main()