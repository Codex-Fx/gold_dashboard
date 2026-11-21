# Streamlit dashboard. Run with:  streamlit run app.py
import os
import threading

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Gold vs FX dashboard", layout="wide")

# On Streamlit Cloud the keys are stored in "Secrets". Copy them to environment variables
# BEFORE importing config. On your own computer the .env file is used instead.
try:
    for key in ["MASSIVE_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]:
        if key in st.secrets:
            os.environ[key] = st.secrets[key]
except Exception:
    pass

import analysis  # noqa: E402
import db  # noqa: E402
import etl  # noqa: E402

DECIMALS = {"XAUUSD": 3, "AUDUSD": 5, "USDJPY": 3, "DXY": 3}


# ---------------- helpers ----------------
@st.cache_data(ttl=300)   # keep the data for 5 minutes, then read Supabase again
def get_data():
    prices = db.load_prices()
    if prices.empty:
        return None, None
    return analysis.prepare(prices), analysis.dropped_days(prices)


@st.cache_data(ttl=30)
def get_last_log():
    return db.get_last_log()


@st.cache_resource
def update_state():
    return {"running": False}   # shared by all visitors, so two updates never run at once


def start_update():
    state = update_state()
    if state["running"]:
        return
    state["running"] = True

    def job():
        try:
            etl.run_update()
        except Exception:
            pass   # the error is already saved in update_log
        finally:
            state["running"] = False

    threading.Thread(target=job, daemon=True).start()


# ---------------- sidebar: data updates ----------------
st.sidebar.header("Data updates")
auto_update = st.sidebar.toggle("Auto-update", value=True)
if st.sidebar.button("Update now"):
    start_update()

last_log = get_last_log()

# auto-update: if the last update is older than 6 hours, update once when the page opens
if auto_update and not st.session_state.get("auto_checked"):
    st.session_state["auto_checked"] = True
    if last_log is None:
        start_update()
    else:
        age = pd.Timestamp.now(tz="UTC") - pd.to_datetime(last_log["ran_at"])
        if age > pd.Timedelta(hours=6):
            start_update()

if update_state()["running"]:
    st.sidebar.info("Updating data now. Reload the page in a minute or two.")
if last_log is None:
    st.sidebar.caption("No update recorded yet.")
elif last_log["status"] == "OK":
    when = pd.to_datetime(last_log["ran_at"]).strftime("%Y-%m-%d %H:%M")
    st.sidebar.caption(f"Last update at {when} UTC. Next about every 6 h.")
else:
    st.sidebar.error("Last update FAILED: " + str(last_log["message"]))

# ---------------- load the data ----------------
try:
    data, dropped = get_data()
except Exception as error:
    st.error(f"Could not read the data from Database: {error}")
    st.stop()
if data is None:
    st.warning("The database is empty. Click 'Update now' in the sidebar and reload in a minute.")
    st.stop()


# ---------------- sidebar: filters ----------------
st.sidebar.header("Filters")
first_day = data.index.min().date()
last_day = data.index.max().date()

# quick range buttons: each one sets the date range below
RANGES = {
    "7 days": pd.DateOffset(days=7),
    "1 month": pd.DateOffset(months=1),
    "3 months": pd.DateOffset(months=3),
    "6 months": pd.DateOffset(months=6),
    "12 months": pd.DateOffset(months=12),
    "Whole history": None,
}


def set_range(offset, first_day, last_day):
    if offset is None:
        start = first_day
    else:
        start = max(first_day, (pd.Timestamp(last_day) - offset).date())
    st.session_state["date_range"] = (start, last_day)


# when new data arrives (the last day changes), go back to the whole history
if st.session_state.get("last_seen_day") != last_day:
    st.session_state["last_seen_day"] = last_day
    st.session_state["date_range"] = (first_day, last_day)

button_columns = st.sidebar.columns(2)
for number, (label, offset) in enumerate(RANGES.items()):
    button_columns[number % 2].button(label, key="range_" + label, on_click=set_range,
                                      args=(offset, first_day, last_day))

date_range = st.sidebar.date_input("Date range", min_value=first_day, max_value=last_day,
                                   key="date_range")
if len(date_range) != 2:
    st.info("Pick a start date and an end date.")
    st.stop()

view = data.loc[str(date_range[0]):str(date_range[1])]
if len(view) < 5:
    st.warning("Please select at least 5 days of data.")
    st.stop()

window = st.sidebar.slider("Rolling correlation window (days)", 30, 120, 60)

st.sidebar.header("Current price")
if st.sidebar.button("Reload from Database"):
    get_data.clear()
    get_last_log.clear()
    st.rerun()

# ---------------- header ----------------
st.title("Gold (XAUUSD) vs AUDUSD, USDJPY and DXY")

columns = st.columns(4)
for column, name in zip(columns, analysis.SERIES):
    latest = view[name].iloc[-1]
    previous = view[name].iloc[-2]
    change = (latest / previous - 1) * 100
    column.metric(name, f"{latest:,.{DECIMALS[name]}f}", f"{change:+.2f}% vs prev close")

st.caption(f"Prices as of {view.index[-1].date()} close")

# ---------------- tabs ----------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Overview", "Periods", "Correlation", "Rolling & lag", "Data quality"])

with tab1:
    st.subheader("Rebased to 100 at start")
    st.line_chart(analysis.rebase(view))
    st.subheader("Summary statistics")
    st.dataframe(analysis.summary_stats(view))

with tab2:
    st.caption(f"Each period counts back from the latest date, ({view.index[-1].date()}). "
               f"Whole history is from {view.index[0].date()} to {view.index[-1].date()}.")
    periods = analysis.period_table(view)
    order = list(analysis.PERIODS)

    st.subheader("Change over each period (%)")
    figure = px.bar(
        periods, x="period", y="change_pct", color="series", barmode="group",
        category_orders={"period": order, "series": analysis.SERIES},
        color_discrete_map={"XAUUSD": "#83C9FF", "AUDUSD": "#0068C9",
                            "USDJPY": "#FFABAB", "DXY": "#FF2B2B"},
        labels={"change_pct": "% change"},
    )
    st.plotly_chart(figure)

    st.subheader("Annualised volatility (%)")
    vol_table = periods.pivot(index="period", columns="series", values="volatility_ann_pct")
    st.dataframe(vol_table.loc[order].round(2))

    st.subheader("Gold's correlation with the others")
    st.dataframe(analysis.gold_correlation_table(view).round(3), hide_index=True)

    st.subheader("Full detail")
    st.dataframe(periods.round(4), hide_index=True)

with tab3:
    use = st.radio("Correlate on", ["returns", "levels"], horizontal=True)
    corr = analysis.correlation_matrix(view, use)
    figure = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
    st.plotly_chart(figure)
    st.caption("Price levels trend over time, so their correlation can look high by accident. "
               "Daily returns are the correct choice.")

with tab4:
    other = st.selectbox("Compare gold with", analysis.OTHERS, index=2)
    st.subheader(f"{window}-day rolling corr: gold vs {other}")
    if window >= len(view):
        st.info("The selected date range is shorter than the rolling window.")
    else:
        rolling = analysis.rolling_correlation(view, other, window)
        st.line_chart(rolling.rename("correlation"))

    st.subheader("Lagged correlation (lag k = other series leads gold by k days)")
    lags = analysis.lag_correlation(view, other)
    lags.index = [f"lag {k}" for k in lags.index]
    st.bar_chart(lags)

with tab5:
    st.subheader("Days dropped (a series had no price)")
    st.write(f"Days dropped because at least one series had no price: {len(dropped)}")
    if len(dropped) > 0:
        st.dataframe(dropped, hide_index=True)
    st.caption("The very first day is also removed, because it has no previous day to calculate a return from.")    

    st.subheader("Missing values per column")
    st.dataframe(view.isna().sum().rename("missing"))
    rejected = "no update recorded yet" if last_log is None else last_log["rows_rejected"]
    st.write(f"Rows rejected by Pydantic validation (last update): {rejected}")
    st.write(f"Rows in the selected range: {len(view)}")
