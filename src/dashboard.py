import os
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ----- paths -----
METRICS_CSV = "data/processed/metrics_sessions.csv"
DB_PATH = "data/processed/telemetry.db"

# ----- thresholds (must match src/metrics.py assumptions) -----
BATTERY_WARN_V = 13.2
LINK_WARN_Q = 0.45
TEMP_WARN_C = 85.0

st.set_page_config(page_title="SystemsOps Flight Logs", layout="wide")

st.title("🚁 SystemsOps Flight Logs — Reliability Dashboard")
st.caption("Synthetic telemetry → ETL → reliability metrics → calibrated risk scoring → telemetry drilldown")

# ----- guards -----
if not os.path.exists(METRICS_CSV):
    st.error(f"Missing {METRICS_CSV}. Run: python -m src.metrics")
    st.stop()

if not os.path.exists(DB_PATH):
    st.error(f"Missing {DB_PATH}. Run: python -m src.etl")
    st.stop()

df = pd.read_csv(METRICS_CSV)

# ----- sidebar -----
st.sidebar.header("Filters")

risk_options = sorted(df["risk_class"].dropna().unique())
risk_filter = st.sidebar.multiselect("Risk class", options=risk_options, default=risk_options)

show_failed_only = st.sidebar.checkbox("Show failed sessions only", value=False)

min_score, max_score = st.sidebar.slider(
    "Reliability score range",
    float(df["reliability_score"].min()),
    float(df["reliability_score"].max()),
    (float(df["reliability_score"].min()), float(df["reliability_score"].max())),
)

fail_reason_options = sorted([x for x in df["fail_reason"].dropna().unique() if str(x).strip() != ""])
fail_reason_filter = st.sidebar.multiselect(
    "Fail reason (optional)",
    options=fail_reason_options,
    default=[],
)

# Filter df
filtered = df[df["risk_class"].isin(risk_filter)].copy()
filtered = filtered[(filtered["reliability_score"] >= min_score) & (filtered["reliability_score"] <= max_score)]
if show_failed_only:
    filtered = filtered[filtered["had_fail"] == 1]
if fail_reason_filter:
    filtered = filtered[filtered["fail_reason"].isin(fail_reason_filter)]

# ----- KPI row -----
total = len(filtered)
fails = int(filtered["had_fail"].sum()) if total else 0
failure_rate = (fails / total) if total else 0.0
mttf = filtered.loc[filtered["had_fail"] == 1, "time_to_first_fail_s"].dropna().mean()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Sessions", total)
c2.metric("Failures", fails)
c3.metric("Failure rate", f"{failure_rate:.2%}")
c4.metric("MTTF (failed only)", "N/A" if pd.isna(mttf) else f"{mttf:.1f} s")
c5.metric("Worst score", "N/A" if total == 0 else f"{filtered['reliability_score'].min():.2f}")

st.divider()

# ----- charts -----
left, right = st.columns(2)

with left:
    st.subheader("Reliability score distribution")
    fig = px.histogram(filtered, x="reliability_score", nbins=25)
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Risk class distribution")
    risk_counts = filtered["risk_class"].value_counts().reset_index()
    risk_counts.columns = ["risk_class", "count"]
    fig2 = px.bar(risk_counts, x="risk_class", y="count")
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ----- worst sessions table -----
st.subheader("Worst sessions (lowest reliability score)")
cols = [
    "session_id",
    "risk_class",
    "reliability_score",
    "had_fail",
    "fail_reason",
    "time_to_first_fail_s",
    "warning_density",
    "battery_sag_pct",
    "link_drop_pct",
    "overheat_pct",
]
worst = filtered.sort_values("reliability_score", ascending=True)[cols].head(30)
st.dataframe(worst, use_container_width=True, hide_index=True)

st.divider()

# =============================================================================
# TELEMETRY DRILLDOWN (from SQLite)
# =============================================================================
st.subheader("📡 Telemetry drilldown (from SQLite)")

if total == 0:
    st.info("No sessions match current filters.")
    st.stop()

# Choose session: show worst first for convenience
session_options = filtered.sort_values("reliability_score")["session_id"].unique()
session_id = st.selectbox("Pick a session", options=session_options)

# Session summary card
row = df[df["session_id"] == session_id].iloc[0]

st.markdown(
    f"""
**Session:** `{session_id}`  
**Risk:** `{row['risk_class']}` | **Score:** `{row['reliability_score']:.2f}`  
**Fail:** `{int(row['had_fail'])}` | **Reason:** `{row['fail_reason']}` | **Time to first fail:** `{row['time_to_first_fail_s']}`  
**Warn density:** `{row['warning_density']:.4f}` | **Battery sag:** `{row['battery_sag_pct']:.4f}` | **Link drop:** `{row['link_drop_pct']:.4f}` | **Overheat:** `{row['overheat_pct']:.4f}`
"""
)

# Load telemetry for selected session
@st.cache_data(show_spinner=False)
def load_telemetry_for_session(db_path: str, sid: str) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        q = """
        SELECT
          session_id,
          t_s,
          voltage_v,
          current_a,
          temp_c,
          cpu_load_pct,
          link_q,
          event,
          fail_reason
        FROM telemetry
        WHERE session_id = ?
        ORDER BY t_s
        """
        out = pd.read_sql(q, conn, params=(sid,))
    return out

telemetry = load_telemetry_for_session(DB_PATH, session_id)

if telemetry.empty:
    st.warning("No telemetry rows found for this session in SQLite.")
    st.stop()

# Identify fail start time (if exists)
fail_rows = telemetry[telemetry["event"] == "FAIL"]
fail_t = int(fail_rows["t_s"].min()) if not fail_rows.empty else None

# Time window slider
t_min = int(telemetry["t_s"].min())
t_max = int(telemetry["t_s"].max())

window = st.slider(
    "Time window (seconds)",
    min_value=t_min,
    max_value=t_max,
    value=(t_min, t_max),
)

telemetry_win = telemetry[(telemetry["t_s"] >= window[0]) & (telemetry["t_s"] <= window[1])].copy()

# Helper: add threshold + fail marker
def add_threshold_and_fail_marker(fig: go.Figure, y_threshold: float, x_fail: int | None, name: str):
    fig.add_hline(y=y_threshold, line_dash="dash", annotation_text=name, annotation_position="top left")
    if x_fail is not None and window[0] <= x_fail <= window[1]:
        fig.add_vline(x=x_fail, line_dash="dot", annotation_text="FAIL start", annotation_position="top right")

# Voltage chart
st.markdown("### Voltage (V)")
fig_v = px.line(telemetry_win, x="t_s", y="voltage_v")
add_threshold_and_fail_marker(fig_v, BATTERY_WARN_V, fail_t, f"BATTERY_WARN_V={BATTERY_WARN_V}")
st.plotly_chart(fig_v, use_container_width=True)

# Temperature chart
st.markdown("### Temperature (°C)")
fig_t = px.line(telemetry_win, x="t_s", y="temp_c")
add_threshold_and_fail_marker(fig_t, TEMP_WARN_C, fail_t, f"TEMP_WARN_C={TEMP_WARN_C}")
st.plotly_chart(fig_t, use_container_width=True)

# Link quality chart
st.markdown("### Link quality (0..1)")
fig_l = px.line(telemetry_win, x="t_s", y="link_q")
add_threshold_and_fail_marker(fig_l, LINK_WARN_Q, fail_t, f"LINK_WARN_Q={LINK_WARN_Q}")
st.plotly_chart(fig_l, use_container_width=True)

# Optional: show event timeline counts in window
st.markdown("### Event summary (selected window)")
event_counts = telemetry_win["event"].value_counts().reset_index()
event_counts.columns = ["event", "count"]
st.dataframe(event_counts, use_container_width=True, hide_index=True)

# Telemetry table (slice)
st.markdown("### Raw telemetry (slice)")
st.caption("Tip: narrow the time window to inspect around WARN/FAIL transition.")
st.dataframe(
    telemetry_win[["t_s", "event", "voltage_v", "temp_c", "link_q", "cpu_load_pct", "current_a", "fail_reason"]],
    use_container_width=True,
    hide_index=True,
)