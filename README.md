# Gold (XAUUSD) vs AUDUSD, USDJPY and DXY: ETL + EDA dashboard (Supabase version)

Same dashboard as before (sidebar, price tiles, 5 tabs). The data now lives in a **Supabase** database
and a scheduled job updates it automatically.

```
Massive.com API  --etl.py-->  Supabase (daily_prices)  --app.py-->  Streamlit dashboard
   (Extract)     (validate with Pydantic, Load)          (pandas analysis + charts)
                      ^
        GitHub Actions runs etl.py every 6 hours
```

## Files

| File | What it does |
| --- | --- |
| `config.py` | Settings: symbols, start date, keys read from `.env` |
| `etl.py` | **E**xtract from Massive, validate each row with Pydantic, **L**oad into Supabase |
| `db.py` | Every Supabase read/write (save rows, read all rows page by page, update log) |
| `analysis.py` | pandas: DXY formula, log returns, period table, correlations, rolling and lag |
| `app.py` | Streamlit page: sidebar, price tiles, 5 tabs |
| `schema.sql` | Creates the two Supabase tables (run once) |
| `.github/workflows/update_data.yml` | Runs `etl.py` every 6 hours |

## Setup (about 20 minutes)

1. **Supabase**: create a free project. Open *SQL Editor*, paste `schema.sql`, click *Run*.
   Then open *Project Settings -> API* and copy the project URL and the **service_role** (or *secret*) key.
2. **On your computer**: `pip install -r requirements.txt`, copy `.env.example` to `.env`, and fill in
   `MASSIVE_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`.
3. **First load**: `python etl.py`. It takes about 2 minutes because it waits 13 seconds between the 8 API calls
   (free plans limit calls per minute; lower `PAUSE_SECONDS` in `config.py` if your plan allows).
4. **Dashboard**: `streamlit run app.py`.
5. **Automatic updates**: put the folder in a GitHub repository, then *Settings -> Secrets and variables -> Actions*
   and add the same three keys as secrets. Open the *Actions* tab, choose *Update data*, click *Run workflow*
   once to test. After that it runs every 6 hours by itself.
6. **Optional, put it online**: deploy `app.py` on Streamlit Community Cloud and paste the three keys into its
   *Secrets* box:
   ```
   MASSIVE_API_KEY = "..."
   SUPABASE_URL = "..."
   SUPABASE_KEY = "..."
   ```

**Keys:** never write a key inside a `.py` file and never upload `.env`. The service key can read and write
everything. Use a private repository.

## How the automatic update works

- `etl.py` looks up the newest stored date for each symbol, downloads only the days since then
  (plus 3 days of overlap), validates them, and **upserts** them. An upsert inserts new days and
  overwrites existing ones, so running it twice never makes duplicates (primary key = symbol + date).
- Every run writes one line to `update_log` (OK or FAILED, rows loaded, rows rejected). The sidebar and the
  *Data quality* tab read it. If a run fails, the GitHub Action shows a red cross.
- The dashboard re-reads Supabase every 5 minutes, so new rows appear without restarting anything.
- The **Update now** button and the **Auto-update** toggle start the same `etl.py` code in the background
  (the toggle only starts it when the last update is older than 6 hours).
- Supabase pauses free projects after about a week with little database activity
  ([Supabase docs](https://supabase.com/docs/guides/platform/free-project-pausing)). An update every 6 hours
  counts as activity.

## What is different from the old version

- Data is stored in Supabase instead of a local file.
- DXY is calculated from the six pairs with the formula from
  [Wikipedia: U.S. Dollar Index](https://en.wikipedia.org/wiki/U.S._Dollar_Index).
- The old "Current price: auto refresh every 5 minutes" control only re-read the same end-of-day close.
  It is replaced by a caption and a "Reload from Supabase now" button.
- Massive's daily bars include a short **Sunday bar** (the day the forex week opens)
  ([Massive knowledge base](https://massive.com/knowledge-base/article/how-far-back-does-massives-forex-and-gold-history-go-and-are-there-gaps)).
  That is why you have about 6 bars a week. They are kept so the numbers stay the same. Set
  `DROP_WEEKENDS = True` in `config.py` to drop them and use 252 bars a year.
- The Periods tab uses the selected date range (the caption says so).

## Be ready to explain (viva)

1. **Extract:** `extract()` in `etl.py` calls the Massive REST endpoint `/v2/aggs/ticker/C:SYMBOL/range/1/day/from/to`.
2. **Validate:** the `Bar` class checks every row (prices above 0, high not below low). Bad rows are counted, not saved.
3. **Load:** `db.save_prices()` upserts the rows into Supabase in batches of 500.
4. **Transform:** `analysis.prepare()` pivots to one column per symbol, builds DXY, and computes log returns.
5. **EDA:** every chart in `app.py` calls one function from `analysis.py`.
6. **Why Supabase paging?** Supabase returns at most 1000 rows per request, so `db.load_prices()` reads in pages.

## Not tested

I tested the pipeline and the dashboard with a fake Massive API and a fake Supabase (including the
1000-row limit). I did **not** run it against the real Massive and Supabase services, because I have no
keys. On your first run, watch the output of `python etl.py` and tell me about any error.
