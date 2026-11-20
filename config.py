import os
from dotenv import load_dotenv

load_dotenv()  # reads the .env file when you run on your own computer

MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

BASE_URL = "https://api.massive.com"

# Symbols we download. The last six are the pairs that DXY is built from
# (USDJPY is used twice: as its own series and inside DXY).
SYMBOLS = ["XAUUSD", "AUDUSD", "USDJPY", "EURUSD", "GBPUSD", "USDCAD", "USDSEK", "USDCHF"]

START_DATE = "2024-11-10"   # first day to download (Basic plan gives about 2 years)
PAUSE_SECONDS = 13          # wait between API calls (free plans have a per-minute limit)
OVERLAP_DAYS = 3            # re-download the last 3 days each time, in case a bar was corrected

# Massive daily bars include Sunday bars (the day the forex week opens).
# False = keep them (same as before). True = drop Saturday/Sunday bars.
DROP_WEEKENDS = False
BARS_PER_YEAR = 252 if DROP_WEEKENDS else 313   # used to turn daily volatility into yearly volatility
