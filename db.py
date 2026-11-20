# All talking to Supabase happens in this file.
import pandas as pd
from supabase import create_client

import config


def get_client():
    return create_client(config.SUPABASE_URL, config.SUPABASE_KEY)


def save_prices(rows):
    """rows is a list of dicts. New rows are inserted, existing rows are updated (upsert)."""
    client = get_client()
    for i in range(0, len(rows), 500):          # send 500 rows at a time
        batch = rows[i:i + 500]
        client.table("daily_prices").upsert(batch, on_conflict="symbol,date").execute()


def load_prices():
    """Read the whole table into a DataFrame.
    Supabase sends at most 1000 rows per request, so we read page by page."""
    client = get_client()
    all_rows = []
    start = 0
    while True:
        page = (
            client.table("daily_prices")
            .select("*")
            .order("symbol")
            .order("date")
            .range(start, start + 999)
            .execute()
        )
        all_rows += page.data
        if len(page.data) < 1000:      # last page
            break
        start += 1000
    return pd.DataFrame(all_rows)


def get_last_date(symbol):
    """Newest date stored for one symbol, as 'YYYY-MM-DD', or None if the symbol has no rows."""
    client = get_client()
    result = (
        client.table("daily_prices")
        .select("date")
        .eq("symbol", symbol)
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    if len(result.data) == 0:
        return None
    return result.data[0]["date"]


def save_log(status, rows_loaded, rows_rejected, message=""):
    client = get_client()
    client.table("update_log").insert({
        "status": status,
        "rows_loaded": rows_loaded,
        "rows_rejected": rows_rejected,
        "message": message,
    }).execute()


def get_last_log():
    """The newest row of update_log as a dict, or None."""
    client = get_client()
    result = client.table("update_log").select("*").order("id", desc=True).limit(1).execute()
    if len(result.data) == 0:
        return None
    return result.data[0]
