# All the pandas calculations. No Streamlit code here, so each function is easy to test.
import numpy as np
import pandas as pd

import config

SERIES = ["XAUUSD", "AUDUSD", "USDJPY", "DXY"]
OTHERS = ["AUDUSD", "USDJPY", "DXY"]

PERIODS = {
    "Last 7 days": pd.DateOffset(days=7),
    "Last 3 months": pd.DateOffset(months=3),
    "Last 6 months": pd.DateOffset(months=6),
    "Last 12 months": pd.DateOffset(months=12),
    "Whole history": None,
}


def prepare(prices):
    """Long table from Supabase (symbol, date, close ...) -> one wide table:
    columns XAUUSD, AUDUSD, USDJPY, DXY (prices) and XAUUSD_ret ... DXY_ret (daily log returns)."""
    wide = prices.pivot(index="date", columns="symbol", values="close")   # one column per symbol
    wide.index = pd.to_datetime(wide.index)

    # DXY is not downloaded. It is calculated from six pairs (formula from Wikipedia, "U.S. Dollar Index").
    wide["DXY"] = (
        50.14348112
        * wide["EURUSD"] ** -0.576
        * wide["USDJPY"] ** 0.136
        * wide["GBPUSD"] ** -0.119
        * wide["USDCAD"] ** 0.091
        * wide["USDSEK"] ** 0.042
        * wide["USDCHF"] ** 0.036
    )

    wide = wide[SERIES].dropna()                 # keep only days where every series has a price
    returns = np.log(wide / wide.shift(1))       # daily log return
    returns.columns = [name + "_ret" for name in returns.columns]
    return wide.join(returns).dropna()           # the first day has no return, so it is dropped


def rebase(data):
    """Every series starts at 100, so different price scales can share one chart."""
    prices = data[SERIES]
    return prices / prices.iloc[0] * 100


def summary_stats(data):
    levels = data[SERIES].describe().T
    returns = data[[name + "_ret" for name in SERIES]].describe().T
    return pd.concat([levels, returns], keys=["levels", "daily_log_returns"])


def get_window(data, offset):
    """The last part of the data (trailing window). offset None = everything."""
    if offset is None:
        return data
    start = data.index[-1] - offset
    return data[data.index >= start]


def period_table(data):
    """One row per period and series: start, end, change, high, low, yearly volatility."""
    rows = []
    for period_name, offset in PERIODS.items():
        window = get_window(data, offset)
        for name in SERIES:
            start_price = window[name].iloc[0]
            end_price = window[name].iloc[-1]
            daily_std = window[name + "_ret"].std()
            rows.append({
                "period": period_name,
                "series": name,
                "from": window.index[0].date(),
                "to": window.index[-1].date(),
                "start": start_price,
                "end": end_price,
                "change_pct": (end_price / start_price - 1) * 100,
                "high": window[name].max(),
                "low": window[name].min(),
                "volatility_ann_pct": daily_std * np.sqrt(config.BARS_PER_YEAR) * 100,
                "days": len(window),
            })
    return pd.DataFrame(rows)


def gold_correlation_table(data):
    """Correlation of gold's daily returns with the other series, for each period."""
    rows = []
    for period_name, offset in PERIODS.items():
        window = get_window(data, offset)
        row = {"period": period_name, "days": len(window)}
        for name in OTHERS:
            row["gold vs " + name] = window["XAUUSD_ret"].corr(window[name + "_ret"])
        rows.append(row)
    return pd.DataFrame(rows)


def correlation_matrix(data, use):
    """use = 'returns' or 'levels'."""
    if use == "returns":
        table = data[[name + "_ret" for name in SERIES]]
        table.columns = SERIES
    else:
        table = data[SERIES]
    return table.corr()


def rolling_correlation(data, other, window):
    return data["XAUUSD_ret"].rolling(window).corr(data[other + "_ret"]).dropna()


def lag_correlation(data, other, max_lag=5):
    """lag k: gold's return today vs the other series' return k days earlier
    (the other series 'leads' gold by k days)."""
    values = {}
    for k in range(max_lag + 1):
        values[k] = data["XAUUSD_ret"].corr(data[other + "_ret"].shift(k))
    return pd.Series(values, name="correlation")

def dropped_days(prices):
    """Days that have a price for some symbols but not for all of them.
    prepare() removes these days, so we list them here."""
    wide = prices.pivot(index="date", columns="symbol", values="close")
    gaps = wide[config.SYMBOLS].isna()          # True where a price is missing
    gaps = gaps[gaps.any(axis=1)]               # keep only the days with a gap
    rows = []
    for day, row in gaps.iterrows():
        rows.append({"date": day, "missing": ", ".join(row.index[row])})
    return pd.DataFrame(rows, columns=["date", "missing"])
