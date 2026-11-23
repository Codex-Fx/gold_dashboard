# Gold (XAUUSD) vs AUDUSD, USDJPY and DXY: ETL + EDA dashboard with Supabase

**Live app:** https://forex-gold-relations.streamlit.app/

In this project I study how gold (XAUUSD) moves compared with the Australian dollar (AUDUSD), the Japanese yen (USDJPY) and the US Dollar Index (DXY). I download daily prices from the Massive.com API, check them, store them in a Supabase database, and show the analysis in a Streamlit dashboard. A scheduled job on GitHub keeps the data up to date by itself.

```
Massive.com API  --etl.py-->  Supabase (daily_prices)  --app.py-->  Streamlit dashboard
   (Extract)     (validate with Pydantic, Load)          (pandas analysis + charts)
                      ^
        GitHub Actions runs etl.py every 6 hours
```

## What the project does

- **Extract:** `etl.py` calls the Massive REST API for 8 forex and gold pairs (XAUUSD, AUDUSD, USDJPY, EURUSD, GBPUSD, USDCAD, USDSEK, USDCHF). The data covers about 2 years of daily bars.
- **Transform and validate:** every row is checked with a Pydantic class (`Bar`). Prices must be above 0 and the high must not be below the low. Bad rows are counted and not saved. In `analysis.py`, pandas builds one column per symbol, calculates the DXY, and computes the log returns.
- **Load:** `db.py` saves the rows into the Supabase table `daily_prices` with an upsert, so running the update twice never creates duplicate rows (the primary key is symbol + date).
- **EDA and dashboard:** `app.py` shows the analysis in Streamlit with 5 tabs: Overview, Periods, Correlation, Rolling & lag, and Data quality.

## Files

| File | What it does |
| --- | --- |
| `config.py` | Settings: symbols, start date, keys read from `.env` |
| `etl.py` | Extract from Massive, validate each row with Pydantic, load into Supabase |
| `db.py` | Every Supabase read and write (save rows, read all rows page by page, update log) |
| `analysis.py` | pandas: DXY formula, log returns, period table, correlations, rolling and lag, dropped days |
| `app.py` | Streamlit page: sidebar, live gold price, price tiles, 5 tabs |
| `schema.sql` | Creates the two Supabase tables (`daily_prices` and `update_log`) |
| `.github/workflows/update_data.yml` | Runs `etl.py` every 6 hours |

## The dashboard

- **Live gold price:** the top of the page shows the live XAUUSD price from goldapi.dev, with the time of its last update. I keep the result for 60 seconds, so the API is called at most once a minute for all visitors. If the live price is not available, the page shows the last Massive close instead.
- **Price tiles:** XAUUSD, AUDUSD, USDJPY and DXY with the change against the previous close.
- **Sidebar:** quick buttons (7 days, 1 month, 3 months, 6 months, 12 months, whole history), a date range, and the rolling correlation window. It also has the "Update now" button and the "Auto-update" switch.
- **Overview tab:** the four series rebased to 100 at the start, plus summary statistics.
- **Periods tab:** the change over each period, the annualised volatility, and gold's correlation with the others.
- **Correlation tab:** a correlation matrix on returns or on price levels.
- **Rolling & lag tab:** the rolling correlation of gold with another series, and the lagged correlation.
- **Data quality tab:** the days dropped because a series had no price, the missing values, the rows rejected by validation, and the number of rows in the selected range.

## How the automatic update works

- `etl.py` looks up the newest stored date for each symbol, downloads only the days since then (plus 3 days of overlap), validates them, and upserts them.
- Every run writes one line to the table `update_log` (OK or FAILED, rows loaded, rows rejected). The sidebar and the Data quality tab read it. If a run fails, the GitHub Action shows a red cross.
- The dashboard reads Supabase again every 5 minutes, so new rows appear without restarting anything.
- The "Update now" button and the "Auto-update" switch start the same `etl.py` code in the background. The switch only starts it when the last update is older than 6 hours.
- Supabase pauses free projects after about a week with little activity ([Supabase docs](https://supabase.com/docs/guides/platform/free-project-pausing)). An update every 6 hours counts as activity.

## Data notes

- **DXY** is calculated from six pairs with the formula from [Wikipedia: U.S. Dollar Index](https://en.wikipedia.org/wiki/U.S._Dollar_Index). AUD is not part of the DXY.
- **Sunday bars:** Massive's daily bars include a short Sunday bar, the day the forex week opens ([Massive knowledge base](https://massive.com/knowledge-base/article/how-far-back-does-massives-forex-and-gold-history-go-and-are-there-gaps)). That is why I have about 6 bars a week. Setting `DROP_WEEKENDS = True` in `config.py` removes them and uses 252 bars a year for the volatility.
- **Close price:** Massive's daily bar covers one UTC day (00:00 to 24:00 UTC), so its close can differ a little from a chart that uses another closing time.
- **Days dropped:** if one series has no price on a day, that day is removed so all series line up. The Data quality tab shows how many days were removed and which series was missing.
- **Supabase paging:** Supabase returns at most 1000 rows per request, so `db.load_prices()` reads the table in pages.

## How to run it

1. **Supabase:** create a free project, open the SQL Editor, paste `schema.sql` and click Run. Then open Project Settings, then API Keys, and copy the project URL and the secret key.
2. **My computer:** run `pip install -r requirements.txt`. Create a `.env` file with `MASSIVE_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY` and `GOLD_API_KEY`.
3. **First load:** run `python etl.py`. It takes about 2 minutes because it waits 13 seconds between the 8 API calls (`PAUSE_SECONDS` in `config.py`).
4. **Dashboard:** run `python -m streamlit run app.py`.
5. **Automatic updates:** push the folder to a GitHub repository. In Settings, then Secrets and variables, then Actions, add `MASSIVE_API_KEY`, `SUPABASE_URL` and `SUPABASE_KEY` as secrets. In the Actions tab, run "Update data" once to test. After that it runs every 6 hours.
6. **Online:** the app is deployed on Streamlit Community Cloud. The four keys are pasted in its Secrets box:
   ```
   MASSIVE_API_KEY = "..."
   SUPABASE_URL = "..."
   SUPABASE_KEY = "..."
   GOLD_API_KEY = "..."
   ```

## Keys

I never write a key inside a `.py` file and never upload `.env` (it is in `.gitignore`). The Supabase secret key can read and write everything, so it only lives in `.env`, the GitHub Actions secrets and the Streamlit Secrets box.

## How I explain each step

1. **Extract:** `extract()` in `etl.py` calls the Massive endpoint `/v2/aggs/ticker/C:SYMBOL/range/1/day/from/to`.
2. **Validate:** the `Bar` class checks every row. Bad rows are counted, not saved.
3. **Load:** `db.save_prices()` upserts the rows into Supabase in batches of 500.
4. **Transform:** `analysis.prepare()` pivots to one column per symbol, builds the DXY, and computes the log returns.
5. **EDA:** every chart in `app.py` uses one function from `analysis.py`.
6. **Why log returns:** price levels trend over time, so their correlation can look high by accident. Daily returns give a fair comparison.
