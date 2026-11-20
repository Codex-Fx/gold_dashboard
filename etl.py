# ETL = Extract (API) -> Transform/Validate -> Load (Supabase)
# Run it by hand with:  python etl.py
# GitHub Actions runs the same file every 6 hours (see .github/workflows/update_data.yml)
import datetime as dt
import time

import requests
from pydantic import BaseModel, ValidationError, field_validator, model_validator

import config
import db


# ---------- Validate: every row must look like this, or it is rejected ----------
class Bar(BaseModel):
    symbol: str
    date: dt.date
    open: float
    high: float
    low: float
    close: float

    @field_validator("open", "high", "low", "close")
    @classmethod
    def price_must_be_positive(cls, value):
        if value <= 0:
            raise ValueError("price must be above 0")
        return value

    @model_validator(mode="after")
    def high_must_not_be_below_low(self):
        if self.high < self.low:
            raise ValueError("high is below low")
        return self


# ---------- Extract ----------
def extract(symbol, start, end):
    """Ask Massive for the daily bars of one symbol. Returns a list of dicts."""
    url = f"{config.BASE_URL}/v2/aggs/ticker/C:{symbol}/range/1/day/{start}/{end}"
    params = {"adjusted": "true", "sort": "asc", "limit": 50000}
    headers = {"Authorization": f"Bearer {config.MASSIVE_API_KEY}"}
    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()                 # stops with an error if the API said no (403, 429 ...)
    return response.json().get("results", [])   # no bars -> empty list


# ---------- Transform + Validate ----------
def validate(symbol, raw_bars):
    """Turn raw API bars into clean rows. Returns (good_rows, number_rejected)."""
    good_rows = []
    rejected = 0
    for bar in raw_bars:
        try:
            # 't' is the start of the day in milliseconds (UTC)
            day = dt.datetime.fromtimestamp(bar["t"] / 1000, tz=dt.timezone.utc).date()
            if config.DROP_WEEKENDS and day.weekday() >= 5:   # 5 = Saturday, 6 = Sunday
                continue
            row = Bar(symbol=symbol, date=day, open=bar["o"], high=bar["h"],
                      low=bar["l"], close=bar["c"])
            good_rows.append(row.model_dump(mode="json"))     # date becomes 'YYYY-MM-DD' text
        except (ValidationError, KeyError, TypeError):
            rejected += 1
    return good_rows, rejected


def find_start_date(symbol):
    """First update: download from START_DATE. Later updates: only the newest days."""
    last = db.get_last_date(symbol)
    if last is None:
        return config.START_DATE
    last_day = dt.date.fromisoformat(last)
    return (last_day - dt.timedelta(days=config.OVERLAP_DAYS)).isoformat()


# ---------- Load ----------
def run_update():
    """Download, validate and save every symbol. Writes one line to update_log."""
    today = dt.date.today().isoformat()
    all_rows = []
    total_rejected = 0
    try:
        for symbol in config.SYMBOLS:
            start = find_start_date(symbol)
            raw = extract(symbol, start, today)
            rows, rejected = validate(symbol, raw)
            print(f"{symbol}: {len(rows)} rows OK, {rejected} rejected (from {start})")
            all_rows += rows
            total_rejected += rejected
            time.sleep(config.PAUSE_SECONDS)
        db.save_prices(all_rows)
        db.save_log("OK", len(all_rows), total_rejected)
        print(f"Saved {len(all_rows)} rows.")
    except Exception as error:
        db.save_log("FAILED", 0, total_rejected, str(error)[:300])
        raise   # lets GitHub Actions show a red cross when something breaks


if __name__ == "__main__":
    run_update()
