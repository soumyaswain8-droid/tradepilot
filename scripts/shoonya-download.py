#!/usr/bin/env python3
"""
TradePilot — Shoonya Historical Data Downloader
=================================================
Downloads 1 year of 1-min candle data for all Nifty 50 stocks.
Requires active Shoonya account with API credentials.

Setup:
    1. Open free account at shoonya.com
    2. Email apisupport@shoonya.com for API key + vendor code
    3. Enable TOTP: Login -> User ID -> Security -> TOTP
    4. pip install NorenRestApiPy pyotp pandas
    5. Fill in credentials below or in shoonya_config.json
    6. Run: python3 scripts/shoonya-download.py

Usage:
    python3 scripts/shoonya-download.py                 # Download all Nifty 50
    python3 scripts/shoonya-download.py --symbol RELIANCE  # Single stock
    python3 scripts/shoonya-download.py --setup         # Print setup guide
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PROTO_DIR = PROJECT_ROOT / "prototype"
DATA_DIR = PROTO_DIR / "data" / "intraday_1min"
CONFIG_FILE = PROTO_DIR / "v5" / "shoonya_config.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(PROTO_DIR))

from v4.config import NIFTY_50_SYMBOLS

# Default config template
CONFIG_TEMPLATE = {
    "user_id": "YOUR_USER_ID",
    "password": "YOUR_PASSWORD",
    "totp_secret": "YOUR_TOTP_SECRET",
    "vendor_code": "YOUR_VENDOR_CODE",
    "api_key": "YOUR_API_KEY",
    "imei": "tradepilot_v5",
}


def print_setup():
    print("""
================================================================
  Shoonya Account Setup Guide (FREE — Rs 0 cost)
================================================================

  STEP 1: Open Account (2-4 hours)
  --------------------------------
  1. Go to shoonya.com
  2. Register with mobile + email
  3. KYC: PAN + Aadhaar (DigiLocker)
  4. Selfie + signature
  5. Select "Equity" segment
  6. UPI verification (Rs 1 debited & refunded)
  7. Wait for activation (few hours)

  STEP 2: Get API Access (1-2 days)
  ----------------------------------
  1. Email: apisupport@shoonya.com
     Subject: "API Access Request"
     Body: "Please enable API access for my account [YOUR_USER_ID]"
  2. They'll reply with: API Key + Vendor Code

  STEP 3: Enable TOTP
  --------------------
  1. Login to shoonya.com
  2. Click your User ID (top-right)
  3. Go to Security -> TOTP
  4. Copy the TOTP secret key
  5. Add to Google Authenticator (for manual login)

  STEP 4: Configure
  ------------------
  1. Edit: prototype/v5/shoonya_config.json
  2. Fill in: user_id, password, totp_secret, vendor_code, api_key
  3. Test: python3 scripts/shoonya-download.py --symbol RELIANCE

  STEP 5: Download
  -----------------
  python3 scripts/shoonya-download.py
  (Downloads 1 year of 1-min candles for all 50 Nifty stocks)

================================================================
  Total cost: Rs 0
  Total time: 1-2 days (account activation + API approval)
  Data you get: 1 year of 1-min candles = ~375,000 candles/stock
================================================================
""")


def load_config():
    if not CONFIG_FILE.exists():
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(CONFIG_TEMPLATE, f, indent=2)
        print(f"Created config template: {CONFIG_FILE}")
        print("Fill in your credentials and run again.")
        print("Run --setup for full guide.")
        return None
    with open(CONFIG_FILE) as f:
        cfg = json.load(f)
    if cfg.get("user_id", "").startswith("YOUR"):
        print(f"Config not filled in: {CONFIG_FILE}")
        print("Run --setup for guide.")
        return None
    return cfg


def login(cfg):
    try:
        from NorenRestApiPy import NorenApi
        import pyotp
    except ImportError:
        print("Install: pip3 install NorenRestApiPy pyotp")
        return None

    class ShoonyaApi(NorenApi):
        def __init__(self):
            NorenApi.__init__(self,
                              host="https://api.shoonya.com/NorenWClientTP/",
                              websocket="wss://api.shoonya.com/NorenWSTP/")

    api = ShoonyaApi()
    otp = pyotp.TOTP(cfg["totp_secret"]).now()
    ret = api.login(
        userid=cfg["user_id"],
        password=cfg["password"],
        twoFA=otp,
        vendor_code=cfg["vendor_code"],
        api_secret=cfg["api_key"],
        imei=cfg.get("imei", "tradepilot"),
    )
    if ret and ret.get("stat") == "Ok":
        print(f"Logged in as {cfg['user_id']}")
        return api
    print(f"Login failed: {ret}")
    return None


def load_scrip_master():
    """Load NSE token map from scrip master."""
    import urllib.request
    import zipfile
    import io

    url = "https://api.shoonya.com/NSE_symbols.txt.zip"
    cache = DATA_DIR.parent / "shoonya_nse_symbols.csv"

    # Refresh daily
    if cache.exists() and (datetime.now() - datetime.fromtimestamp(cache.stat().st_mtime)).days < 1:
        import pandas as pd
        df = pd.read_csv(cache)
        return dict(zip(df["Symbol"], df["Token"].astype(str)))

    print("Downloading NSE scrip master...")
    try:
        resp = urllib.request.urlopen(url, timeout=30)
        z = zipfile.ZipFile(io.BytesIO(resp.read()))
        fname = z.namelist()[0]
        import pandas as pd
        df = pd.read_csv(z.open(fname))
        # Filter equity segment
        eq = df[df["Instrument"] == "EQ"][["Symbol", "Token"]].drop_duplicates("Symbol")
        eq.to_csv(cache, index=False)
        return dict(zip(eq["Symbol"], eq["Token"].astype(str)))
    except Exception as e:
        print(f"Failed to load scrip master: {e}")
        return {}


def download_stock(api, token, symbol, interval=1, days=365):
    """Download historical candles in 90-day chunks."""
    import pandas as pd

    end = datetime.now()
    start = end - timedelta(days=days)
    all_data = []
    current = start

    while current < end:
        chunk_end = min(current + timedelta(days=89), end)
        st = int(current.timestamp())
        et = int(chunk_end.timestamp())

        try:
            ret = api.get_time_price_series(
                exchange="NSE", token=token,
                starttime=st, endtime=et, interval=interval
            )
            if ret and isinstance(ret, list):
                all_data.extend(ret)
                print(f"    {current.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}: {len(ret)} candles")
        except Exception as e:
            print(f"    Chunk failed: {e}")

        current = chunk_end + timedelta(days=1)
        time.sleep(1)  # Rate limit

    if not all_data:
        return None

    df = pd.DataFrame(all_data)
    outfile = DATA_DIR / f"{symbol}_1min.csv"
    df.to_csv(outfile, index=False)
    print(f"  Saved: {outfile} ({len(df)} candles, {len(df)//375:.0f} trading days)")
    return df


def main():
    if "--setup" in sys.argv:
        print_setup()
        return

    cfg = load_config()
    if not cfg:
        return

    api = login(cfg)
    if not api:
        return

    tokens = load_scrip_master()
    if not tokens:
        print("Failed to load scrip master")
        return

    symbols = NIFTY_50_SYMBOLS
    if "--symbol" in sys.argv:
        idx = sys.argv.index("--symbol")
        if idx + 1 < len(sys.argv):
            symbols = [sys.argv[idx + 1]]

    print(f"\nDownloading 1-min candles for {len(symbols)} stocks (1 year)...")
    print("=" * 60)

    success, failed = 0, []
    for i, sym in enumerate(symbols, 1):
        token = tokens.get(sym)
        if not token:
            print(f"[{i}/{len(symbols)}] {sym}: token not found, skipping")
            failed.append(sym)
            continue

        print(f"[{i}/{len(symbols)}] {sym} (token={token})...")
        df = download_stock(api, token, sym)
        if df is not None and len(df) > 0:
            success += 1
        else:
            failed.append(sym)
        time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"Done: {success}/{len(symbols)} stocks downloaded")
    if failed:
        print(f"Failed: {failed}")
    print(f"Data at: {DATA_DIR}")


if __name__ == "__main__":
    main()
