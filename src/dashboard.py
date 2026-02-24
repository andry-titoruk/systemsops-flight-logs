import os
import pandas as pd
import streamlit as st
import plotly.express as px

DATA_PATH = "data/processed/metrics_sessions.csv"

st.set_page_config(page_title="SystemsOps Flight Logs", layout="wide")

st.title("🚁 SystemsOps Flight Logs — Reliability Dashboard")
st.caption("Synthetic telemetry → ETL → reliability metrics → risk calibration")

if not os.path.exists(DATA_PATH):
    st.error(f"File not found: {DATA_PATH}. Run: python -m src.metrics")
    st.stop()

df = pd.read_csv(DATA_PATH)

# --- Sidebar filters ---
st.sidebar.header("Filters")
risk_filter = st.sidebar.multiselect(
    "Risk class",
    options=sorted(df["risk_class"].dropna().unique()),
    default=sorted(df["risk_class"].dropna().unique()),
)

show_failed_only = st.sidebar.checkbox("Show failed sessions only", value=False)
min_score, max_score = st.sidebar.slider(
    "Reliability score range",
    float(df["reliability_score"].min()),
    float(df["reliability_score"].max()),
    (float(df["reliability_score"].min()), float(df["reliability_score"].max())),
)

filtered = df[df["risk_class"].isin(risk_filter)].copy()
filtered = filtered[(filtered["reliability_score"] >= min_score) & (filtered["reliability_score"] <= max_score)]
if show_failed_only:
    filtered = filtered[filtered["had_fail"] == 1]

# --- KPI row ---
total = len(filtered)
fails = int(filtered["had_fail"].sum()) if total else 0
failure_rate = (fails / total) if total else 0.0
mttf = filtered.loc[filtered["had_fail"] == 1, "time_to_first_fail_s"].dropna().mean()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Sessions", total)
c2.metric("Failures", fails)
c3.metric("Failure rate", f"{failure_rate:.2%}")
c4.metric("MTTF (failed only)", "N/A" if pd.isna(mttf) else f"{mttf:.1f} s")

st.divider()

# --- Charts ---
left, right = st.columns(2)

with left:
    st.subheader("Reliability score distribution")
    fig = px.histogram(filtered, x="reliability_score", nbins=20)
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Risk class distribution")
    risk_counts = filtered["risk_class"].value_counts().reset_index()
    risk_counts.columns = ["risk_class", "count"]
    fig2 = px.bar(risk_counts, x="risk_class", y="count")
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# --- Worst sessions table ---
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
worst = filtered.sort_values("reliability_score", ascending=True)[cols].head(20)
st.dataframe(worst, use_container_width=True)

# --- Drilldown ---
st.subheader("Session drilldown")
session_id = st.selectbox("Pick a session", options=filtered.sort_values("reliability_score")["session_id"].unique())

row = df[df["session_id"] == session_id].iloc[0]
st.write(
    f"**Session:** `{session_id}` | "
    f"**Risk:** `{row['risk_class']}` | "
    f"**Score:** `{row['reliability_score']:.2f}` | "
    f"**Fail:** `{int(row['had_fail'])}` | "
    f"**Reason:** `{row['fail_reason']}`"
)

st.caption("Next step: show raw telemetry timeseries for this session (voltage/temp/link over time).")