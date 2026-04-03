"""
TradePilot Analytics -- Track user behavior for training and improvement.
Uses SQLite for lightweight persistent storage.
"""
import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "tradepilot_analytics.db")


def get_db():
    """Get SQLite connection with WAL mode for concurrency."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create analytics tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            first_seen TEXT DEFAULT (datetime('now')),
            last_seen TEXT DEFAULT (datetime('now')),
            device TEXT,
            user_agent TEXT,
            total_visits INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS page_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            page TEXT,
            timestamp TEXT DEFAULT (datetime('now')),
            duration_sec REAL
        );

        CREATE TABLE IF NOT EXISTS stock_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            symbol TEXT,
            score REAL,
            direction TEXT,
            timestamp TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS swipe_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            symbol TEXT,
            action TEXT,  -- 'buy' or 'skip'
            score REAL,
            price REAL,
            quantity INTEGER,
            timestamp TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            symbol TEXT,
            action TEXT,  -- 'buy' or 'sell'
            quantity INTEGER,
            price REAL,
            pnl REAL,
            source TEXT,  -- 'swipe', 'voice', 'chat', 'manual'
            timestamp TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS voice_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            command TEXT,
            parsed_action TEXT,
            success INTEGER,
            timestamp TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS wizard_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            budget REAL,
            category TEXT,
            results_count INTEGER,
            recommended_count INTEGER,
            timestamp TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            type TEXT,  -- 'bug', 'feature', 'general'
            message TEXT,
            page TEXT,
            timestamp TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


def track_visit(user_id, device=None, user_agent=None):
    """Track a user visit."""
    conn = get_db()
    conn.execute("""
        INSERT INTO users (id, device, user_agent)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            last_seen = datetime('now'),
            total_visits = total_visits + 1
    """, (user_id, device, user_agent))
    conn.commit()
    conn.close()


def track_page_view(user_id, page):
    conn = get_db()
    conn.execute("INSERT INTO page_views (user_id, page) VALUES (?, ?)", (user_id, page))
    conn.commit()
    conn.close()


def track_stock_view(user_id, symbol, score=None, direction=None):
    conn = get_db()
    conn.execute("INSERT INTO stock_views (user_id, symbol, score, direction) VALUES (?, ?, ?, ?)",
                 (user_id, symbol, score, direction))
    conn.commit()
    conn.close()


def track_swipe(user_id, symbol, action, score=None, price=None, quantity=None):
    conn = get_db()
    conn.execute("INSERT INTO swipe_actions (user_id, symbol, action, score, price, quantity) VALUES (?, ?, ?, ?, ?, ?)",
                 (user_id, symbol, action, score, price, quantity))
    conn.commit()
    conn.close()


def track_paper_trade(user_id, symbol, action, quantity, price, pnl=None, source="manual"):
    conn = get_db()
    conn.execute("INSERT INTO paper_trades (user_id, symbol, action, quantity, price, pnl, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (user_id, symbol, action, quantity, price, pnl, source))
    conn.commit()
    conn.close()


def track_wizard_search(user_id, budget, category, results_count, recommended_count):
    conn = get_db()
    conn.execute("INSERT INTO wizard_searches (user_id, budget, category, results_count, recommended_count) VALUES (?, ?, ?, ?, ?)",
                 (user_id, budget, category, results_count, recommended_count))
    conn.commit()
    conn.close()


def track_feedback(user_id, feedback_type, message, page=None):
    conn = get_db()
    conn.execute("INSERT INTO feedback (user_id, type, message, page) VALUES (?, ?, ?, ?)",
                 (user_id, feedback_type, message, page))
    conn.commit()
    conn.close()


def get_dashboard_stats():
    """Get analytics dashboard stats."""
    conn = get_db()
    stats = {
        "total_users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "active_today": conn.execute("SELECT COUNT(*) FROM users WHERE last_seen >= date('now')").fetchone()[0],
        "total_page_views": conn.execute("SELECT COUNT(*) FROM page_views").fetchone()[0],
        "total_stock_views": conn.execute("SELECT COUNT(*) FROM stock_views").fetchone()[0],
        "total_swipes": conn.execute("SELECT COUNT(*) FROM swipe_actions").fetchone()[0],
        "total_paper_trades": conn.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0],
        "total_wizard_searches": conn.execute("SELECT COUNT(*) FROM wizard_searches").fetchone()[0],
        "buy_swipes": conn.execute("SELECT COUNT(*) FROM swipe_actions WHERE action='buy'").fetchone()[0],
        "skip_swipes": conn.execute("SELECT COUNT(*) FROM swipe_actions WHERE action='skip'").fetchone()[0],
        "top_viewed_stocks": [dict(r) for r in conn.execute(
            "SELECT symbol, COUNT(*) as views FROM stock_views GROUP BY symbol ORDER BY views DESC LIMIT 10"
        ).fetchall()],
        "top_swiped_stocks": [dict(r) for r in conn.execute(
            "SELECT symbol, action, COUNT(*) as count FROM swipe_actions GROUP BY symbol, action ORDER BY count DESC LIMIT 10"
        ).fetchall()],
        "feedback": [dict(r) for r in conn.execute(
            "SELECT * FROM feedback ORDER BY timestamp DESC LIMIT 20"
        ).fetchall()],
    }
    conn.close()
    return stats


# Initialize DB on import
init_db()
