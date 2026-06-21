"""
TradePilot v5 Telegram Alert Bot.

Sends real-time trade alerts (entries, exits, circuit breakers, daily summary)
to a Telegram chat via the Bot API.

Usage:
    python3 -m prototype.v5.telegram_bot --test
    python3 -m prototype.v5.telegram_bot --setup
"""

import json
import os
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent / "telegram_config.json"

_DEFAULT_CONFIG = {
    "bot_token": "YOUR_BOT_TOKEN_HERE",
    "chat_id": "YOUR_CHAT_ID_HERE",
    "enabled": False,
    "alert_entries": True,
    "alert_exits": True,
    "alert_circuit_breakers": True,
    "alert_daily_summary": True,
    "alert_regime_changes": True,
}

# Rate limiter: max 30 messages per 60 seconds
_MAX_MESSAGES = 30
_WINDOW_SECS = 60
_send_timestamps: deque = deque()


def _read_dotenv() -> dict:
    # Engines spawn via `nohup python3` which doesn't auto-load .env.
    # Read the file directly so TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID reach the sender.
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not env_file.exists():
        return {}
    try:
        return dict(
            line.split("=", 1)
            for line in env_file.read_text().splitlines()
            if "=" in line and not line.startswith("#")
        )
    except (IOError, ValueError):
        return {}


def _load_config() -> dict:
    # Priority: environment variables > .env file > config file
    config = _DEFAULT_CONFIG.copy()
    if CONFIG_PATH.exists():
        try:
            config.update(json.loads(CONFIG_PATH.read_text()))
        except (json.JSONDecodeError, IOError):
            pass
    dotenv = _read_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or dotenv.get("TELEGRAM_BOT_TOKEN", "").strip().strip('"')
    chat = os.environ.get("TELEGRAM_CHAT_ID") or dotenv.get("TELEGRAM_CHAT_ID", "").strip().strip('"')
    if token and token != "SET_VIA_ENV_VAR":
        config["bot_token"] = token
    if chat and chat != "SET_VIA_ENV_VAR":
        config["chat_id"] = chat
    return config


def _rate_ok() -> bool:
    """Return True if we can send another message within the rate window."""
    now = time.time()
    while _send_timestamps and now - _send_timestamps[0] > _WINDOW_SECS:
        _send_timestamps.popleft()
    return len(_send_timestamps) < _MAX_MESSAGES


def _record_send():
    _send_timestamps.append(time.time())


# ---------------------------------------------------------------------------
# Core send
# ---------------------------------------------------------------------------


def send_alert(message: str) -> bool:
    """Send a plain-text (Markdown-parsed) message to the configured chat."""
    # Per-process kill switch so a shadow A/B engine (e.g. v5_noml) stays silent
    # and doesn't double-notify. Defaults off — live engines are unaffected.
    if os.environ.get("TELEGRAM_DISABLE") == "1":
        return False
    cfg = _load_config()
    if not cfg.get("enabled"):
        return False

    token = cfg["bot_token"]
    chat_id = cfg["chat_id"]
    if token == "YOUR_BOT_TOKEN_HERE" or chat_id == "YOUR_CHAT_ID_HERE":
        print("Telegram bot not configured. Run --setup for instructions.")
        return False

    # Rate limiting
    if not _rate_ok():
        print("Rate limit reached (30/min). Message queued — retry shortly.")
        time.sleep(2)
        if not _rate_ok():
            return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
        _record_send()
        if resp.status_code == 200:
            return True
        print(f"Telegram API error {resp.status_code}: {resp.text[:200]}")
        return False
    except requests.RequestException as exc:
        print(f"Telegram send failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _fmt_price(val) -> str:
    """Format a number as Rs X,XXX.XX."""
    try:
        return f"Rs {float(val):,.2f}"
    except (TypeError, ValueError):
        return str(val)


def _fmt_pnl(val) -> str:
    v = float(val)
    sign = "+" if v >= 0 else ""
    return f"{sign}Rs {v:,.0f}"


def alert_entry(trade: dict) -> bool:
    """Send a trade entry alert. Accepts multiple key formats."""
    cfg = _load_config()
    if not cfg.get("alert_entries"):
        return False

    side = trade.get("side") or trade.get("direction") or trade.get("position_type", "BUY")
    side = side.upper()
    icon = "\U0001f534" if side in ("SELL", "SHORT") else "\U0001f7e2"
    sym = trade.get("symbol", "?")
    pool = trade.get("pool", "-")
    score = trade.get("score", "-")
    entry = trade.get("entry") or trade.get("entry_price", 0)
    sl = trade.get("sl") or trade.get("sl_price", 0)
    tgt = trade.get("target") or trade.get("target_price", 0)
    qty = trade.get("qty", "")
    regime = trade.get("regime", "-")
    lines = [
        f"{icon} *v5 {side} {sym}*",
        f"Pool: {pool} | Score: {score}",
        f"Entry: {_fmt_price(entry)} | Qty: {qty}",
        f"SL: {_fmt_price(sl)} | Tgt: {_fmt_price(tgt)}",
        f"Regime: {regime}",
    ]
    return send_alert("\n".join(lines))


def alert_exit(trade: dict) -> bool:
    """Send a trade exit alert. Accepts multiple key formats."""
    cfg = _load_config()
    if not cfg.get("alert_exits"):
        return False

    pnl = float(trade.get("pnl", 0))
    win = pnl > 0
    icon = "\u2705" if win else "\u274c"
    tag = "WIN" if win else "LOSS"
    pct = trade.get("pct") or trade.get("pnl_pct", 0)
    ptype = trade.get("position_type", "LONG")
    reason = trade.get("reason", "-")
    lines = [
        f"{icon} *v5 {tag} {trade.get('symbol', '?')}* ({ptype})",
        f"P&L: {_fmt_pnl(pnl)} ({float(pct):+.2f}%)",
        f"Pool: {trade.get('pool', '-')} | Exit: {reason}",
    ]
    return send_alert("\n".join(lines))


def alert_circuit_breaker(details: dict) -> bool:
    """Send a circuit breaker activation alert."""
    cfg = _load_config()
    if not cfg.get("alert_circuit_breakers"):
        return False

    tier = details.get("tier", "?")
    reason = details.get("reason", "threshold reached")
    pool = details.get("pool", "-")
    lines = [
        "\u26a0\ufe0f *CIRCUIT BREAKER ACTIVATED*",
        f"Tier {tier}: {reason}",
        f"Pool: {pool} paused",
    ]
    return send_alert("\n".join(lines))


def alert_daily_summary(v5_state: dict, v4_state: dict = None) -> bool:
    """Send end-of-day summary. v5_state keys: pnl, pnl_pct, trades,
    wins, losses, win_rate, long_pnl, short_pnl, regime, vix, date."""
    cfg = _load_config()
    if not cfg.get("alert_daily_summary"):
        return False

    d = v5_state
    date_str = d.get("date", datetime.now().strftime("%b %d"))
    lines = [
        f"\U0001f4ca *v5 Daily Summary \u2014 {date_str}*",
        f"P&L: {_fmt_pnl(d.get('pnl', 0))} ({d.get('pnl_pct', '0')}%)",
        f"Trades: {d.get('trades', 0)} ({d.get('wins', 0)}W/{d.get('losses', 0)}L) | {d.get('win_rate', 0)}% win rate",
        f"Longs: {_fmt_pnl(d.get('long_pnl', 0))} | Shorts: {_fmt_pnl(d.get('short_pnl', 0))}",
        f"Regime: {d.get('regime', '-')} | VIX: {d.get('vix', '-')}",
    ]
    if v4_state:
        v4_pnl = v4_state.get("pnl", 0)
        v5_pnl = d.get("pnl", 0)
        edge = float(v5_pnl) - float(v4_pnl)
        ratio = f"{float(v5_pnl) / float(v4_pnl):.1f}x" if float(v4_pnl) else "N/A"
        lines.append("")
        lines.append(f"v4 Comparison: {_fmt_pnl(v4_pnl)}")
        lines.append(f"v5 Edge: {_fmt_pnl(edge)} ({ratio} better)")

    return send_alert("\n".join(lines))


def alert_regime_change(old_regime: str, new_regime: str) -> bool:
    """Send a regime transition alert."""
    cfg = _load_config()
    if not cfg.get("alert_regime_changes"):
        return False

    lines = [
        "\U0001f4ca *Regime Change Detected*",
        f"{old_regime} \u2192 {new_regime}",
        f"Timestamp: {datetime.now().strftime('%H:%M:%S')}",
    ]
    return send_alert("\n".join(lines))


# ---------------------------------------------------------------------------
# Command listener (/status, /summary, /regime)
# ---------------------------------------------------------------------------

_last_update_id = 0


def check_commands() -> list:
    """Poll Telegram for /commands. Returns list of command strings."""
    global _last_update_id
    cfg = _load_config()
    if not cfg.get("enabled"):
        return []
    token = cfg["bot_token"]
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        params = {"offset": _last_update_id + 1, "timeout": 1}
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code != 200:
            return []
        data = resp.json()
        commands = []
        for update in data.get("result", []):
            _last_update_id = update["update_id"]
            msg = update.get("message", {})
            text = msg.get("text", "").strip()
            if text.startswith("/"):
                commands.append(text.lower())
        return commands
    except Exception:
        return []


def handle_status_command():
    """Build and send status from all engine state files."""
    import glob
    base = Path(__file__).resolve().parent.parent.parent / "docs" / "paper-trades"
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"*TradePilot Status - {today}*\n"]

    # v4
    v4f = base / "v4" / f"{today}.json"
    if v4f.exists():
        v4 = json.loads(v4f.read_text())
        cl = v4.get("closed_trades", [])
        op = sum(1 for p in v4.get("positions", []) if p.get("status") == "open")
        w = sum(1 for t in cl if t.get("pnl", 0) > 0)
        pnl = v4.get("realized_pnl", 0)
        lines.append(f"*v4* | P&L: {_fmt_pnl(pnl)} | {len(cl)}t ({w}W) | {op} open")
    else:
        lines.append("*v4* | No trades today")

    # v5
    v5f = base / "v5" / f"{today}.json"
    if v5f.exists():
        v5 = json.loads(v5f.read_text())
        s = v5.get("summary", {})
        pnl = s.get("total_pnl", 0)
        total_open = sum(len(v5.get("pools", {}).get(p, {}).get("positions", []))
                        for p in ["INTRADAY", "SWING", "POSITIONAL", "INVESTMENT"])
        lines.append(f"*v5* | P&L: {_fmt_pnl(pnl)} | {s.get('trades',0)}t ({s.get('wins',0)}W) | {total_open} open")
        lines.append(f"  Regime: {v5.get('regime', '?')} | L:{s.get('longs',0)} S:{s.get('shorts',0)}")
    else:
        lines.append("*v5* | No trades today")

    # v5.2
    v52f = base / "v5_2" / f"{today}.json"
    if v52f.exists():
        v52 = json.loads(v52f.read_text())
        s = v52.get("summary", {})
        pnl = s.get("total_pnl", 0)
        lines.append(f"*v5.2 F&O* | P&L: {_fmt_pnl(pnl)} | {s.get('trades',0)}t")
    else:
        lines.append("*v5.2 F&O* | No trades today")

    # v5.3
    v53f = base / "v5_3" / f"{today}.json"
    if v53f.exists():
        v53 = json.loads(v53f.read_text())
        s = v53.get("summary", {})
        pnl = s.get("total_pnl", 0)
        lines.append(f"*v5.3 Staged* | P&L: {_fmt_pnl(pnl)} | {s.get('trades',0)}t")
    else:
        lines.append("*v5.3 Staged* | No trades today")

    # Carry forward balances
    lines.append("")
    for eng, cf_file in [("v4", "v4/carry_forward.json"), ("v5", "v5/carry_forward_v5.json"),
                          ("v5.2", "v5_2/carry_forward_v5_2.json"), ("v5.3", "v5_3/carry_forward_v5_3.json")]:
        cff = base / cf_file
        if cff.exists():
            cf = json.loads(cff.read_text())
            bal = cf.get("closing_balance", 1000000)
            cum = cf.get("cumulative_pnl", 0)
            lines.append(f"{eng}: Rs {bal:,.0f} ({_fmt_pnl(cum)})")

    return send_alert("\n".join(lines))


def handle_regime_command():
    """Send current regime status."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from v5.regime_detector import detect_regime
        r = detect_regime()
        lines = [
            f"*Market Regime*",
            f"State: *{r.get('regime', '?')}* (score {r.get('score', 0)})",
            f"Allocation: {r.get('allocation', 0.75):.0%}",
            f"Confidence: {r.get('confidence', 0):.0%}",
        ]
        for ind in r.get("indicators", []):
            lines.append(f"  {ind.get('name', '?')}: {ind.get('value', '?')} ({ind.get('vote', 0):+d})")
        return send_alert("\n".join(lines))
    except Exception as e:
        return send_alert(f"Regime check failed: {e}")


def run_command_listener():
    """Run a polling loop that listens for /commands from Telegram."""
    print("Telegram command listener started. Listening for /status, /summary, /regime...")
    while True:
        try:
            commands = check_commands()
            for cmd in commands:
                if cmd.startswith("/status"):
                    handle_status_command()
                elif cmd.startswith("/regime"):
                    handle_regime_command()
                elif cmd.startswith("/summary"):
                    handle_status_command()  # same as status for now
                elif cmd.startswith("/help"):
                    send_alert("*TradePilot Commands:*\n/status — All engine P&L\n/regime — Market regime\n/help — This message")
            time.sleep(3)  # Poll every 3 seconds
        except KeyboardInterrupt:
            break
        except Exception:
            time.sleep(5)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_SETUP_TEXT = """
TradePilot Telegram Bot Setup:
1. Open Telegram, search @BotFather
2. Send /newbot, name it "TradePilot Alerts"
3. Copy the bot token
4. Send any message to your new bot
5. Visit https://api.telegram.org/bot<TOKEN>/getUpdates
6. Find your chat_id from the response
7. Edit {config_path} with token + chat_id
8. Set "enabled": true
9. Test: python3 -m prototype.v5.telegram_bot --test
""".strip()


def _cli():
    _load_config()  # ensure config file exists

    if "--setup" in sys.argv:
        print(_SETUP_TEXT.format(config_path=CONFIG_PATH))
        return

    if "--test" in sys.argv:
        cfg = _load_config()
        if not cfg.get("enabled"):
            print("Bot is disabled. Set 'enabled': true in config first.")
            print(f"Config: {CONFIG_PATH}")
            return
        ok = send_alert(
            "\u2705 *TradePilot v5 Alert Bot*\nTest message received. Bot is active."
        )
        if ok:
            print("Test message sent successfully.")
        else:
            print("Failed to send test message. Check config and network.")
        return

    if "--listen" in sys.argv:
        run_command_listener()
        return

    print("Usage:")
    print("  python3 -m prototype.v5.telegram_bot --setup   Show setup instructions")
    print("  python3 -m prototype.v5.telegram_bot --test    Send test message")
    print("  python3 -m prototype.v5.telegram_bot --listen  Listen for /commands")


if __name__ == "__main__":
    _cli()
