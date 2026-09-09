"""Load the JSON/markdown evidence on disk into the append-only ledger.

    python3 -m ledger.migrate_json [--since YYYY-MM-DD] [--dry-run] [--root DIR]

Sources (relative to --root, default: repo root):
  docs/paper-trades/<engine>/<date>.json   closed trades -> calls (synthesised, pre_registered=false)
                                           + outcomes (one per closed trade, linked by call hash)
  docs/research/daygain/baseline/*.json    files with an `eod` block -> baselines (rule top10_gainers_0935)
  docs/research/shadows/armband/*.json     -> verdicts PENDING, test_id armband-shadow
  docs/research/shadows/regime/*.json      -> verdicts PENDING, test_id regime-shadow
  docs/research/daygain/phase0-holdout-*.md -> verdicts KILL,   test_id daygain-phase0

Re-runnable: a row whose row_hash already exists in its table is skipped. prev_hash links each
row to the previous row of the same table in insertion order. After loading, one Merkle root per
(tenant, ledger_date) is inserted into ledger_roots for every closed business date (< today) that
has no root yet; an existing root that differs from the recomputed one is reported loudly and
left untouched (ledger_roots is append-only too).
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from . import TABLES, db
from .hashing import canonical_json, merkle_root, row_hash, sanitize

REPO_ROOT = Path(__file__).resolve().parent.parent
TENANT = "tradepilot"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
US_ENGINES = {"us_v1"}
BASELINE_RULE = "top10_gainers_0935"
MARKET_TZ = {"NSE": "Asia/Kolkata", "US": "America/New_York"}  # exchange-local wall time on disk


# ----------------------------------------------------------------------------- readers
def closed_trades(day: dict) -> list[tuple[str, dict]]:
    """[(pool, trade)] across the shapes on disk (mirrors scripts/eod-comparison-report.py,
    plus the top-level `closed` / `closed_positions` lists of the older engines)."""
    out = []
    pools = day.get("pools") or {}
    if isinstance(pools, dict) and pools:
        for pname, pool in pools.items():
            if not isinstance(pool, dict):
                continue
            for t in pool.get("closed_trades") or pool.get("closed") or []:
                if isinstance(t, dict):
                    out.append((t.get("pool") or pname, t))
        return out
    for key in ("closed_trades", "closed", "closed_positions"):
        for t in day.get(key) or []:
            if isinstance(t, dict):
                out.append((t.get("pool") or "MAIN", t))
        if out:
            break
    return out


def _side(t: dict) -> str | None:
    pt = t.get("position_type") or t.get("dir")
    if pt:
        return str(pt).upper()
    d = str(t.get("direction") or t.get("action") or "").upper()
    return {"BUY": "LONG", "SELL": "SHORT"}.get(d)


def _symbol(t: dict) -> str | None:
    """Equity engines carry `symbol`; the F&O engine (v5_2) carries instrument/strike/option_type."""
    if t.get("symbol"):
        return t["symbol"]
    if t.get("instrument"):
        return f"{t['instrument']}{t.get('strike', '')}{t.get('option_type', '')}"
    return None


def _split_ts(value, fallback_date: str | None) -> tuple[str | None, str | None]:
    """'2026-08-13T19:00:26' -> ('2026-08-13', '19:00:26'); '09:43:28' -> (fallback, '09:43:28').
    No value at all -> (fallback, None); callers pass fallback=None when the date is unknown."""
    if not value:
        return fallback_date, None
    s = str(value)
    if "T" in s or " " in s:
        d, _, tm = s.replace(" ", "T").partition("T")
        return (d if DATE_RE.match(d) else fallback_date), (tm[:8] or None)
    return fallback_date, s[:8]


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def trade_rows(engine: str, file_date: str, pool: str, t: dict) -> tuple[dict, dict]:
    """(call_payload, outcome_payload) for one closed trade."""
    entry_raw = t.get("entry_time") or t.get("entry_ts") or t.get("entry_at")
    # Unknown entry timestamp (us_v1, some v5_god rows): keep it unknown rather than stamping the
    # file date -- us_v1 repeats closed trades across day files and must hash identically.
    entry_date, entry_time = _split_ts(entry_raw, (t.get("entry_date") or file_date) if entry_raw else None)
    exit_date, exit_time = _split_ts(t.get("exit_time") or t.get("exit_ts") or t.get("exit_at"),
                                     t.get("exit_date") or file_date)
    market = "US" if engine in US_ENGINES else "NSE"
    call = {
        "kind": "call",
        "engine": engine,
        "symbol": _symbol(t),
        "market": market,
        "side": _side(t),
        "pool": pool,
        "entry_price": _num(t.get("entry_price", t.get("entry_premium"))),
        "qty": _num(t.get("qty")),
        "entry_date": entry_date,
        "entry_time": entry_time,
        "score": _num(t.get("score", t.get("v4_score"))),
        "sl_price": _num(t.get("sl_price")),
        "target_price": _num(t.get("target_price")),
        "reasons": t.get("reasons"),
        "pre_registered": False,
        "pre_registration_hash": None,
        "ledger_date": entry_date or exit_date,  # unknown entry: first evidenced on the exit date
        "synthesised_from": "closed_trade",
    }
    outcome = {
        "kind": "outcome",
        "engine": engine,
        "symbol": _symbol(t),
        "pool": pool,
        "trade_date": exit_date,
        "exit_time": exit_time,
        "entry_price": _num(t.get("entry_price")),
        "exit_price": _num(t.get("exit_price", t.get("exit_premium"))),
        "qty": _num(t.get("qty")),
        "pnl_gross": _num(t.get("pnl_gross", t.get("pnl"))),
        "pnl_net": _num(t.get("pnl_net", t.get("pnl"))),
        "pnl_net_source": "pnl_net" if "pnl_net" in t else "pnl",
        "pnl_pct": _num(t.get("pnl_pct")),
        "cost": _num(t.get("cost")),
        "cost_delivery": _num(t.get("cost_delivery")),
        "pnl_net_delivery": _num(t.get("pnl_net_delivery")),
        "reason": t.get("reason", t.get("exit_reason")),
        "call_hash": None,  # filled after the call payload is hashed
        "ledger_date": exit_date,
    }
    call = sanitize(call)
    outcome = sanitize(outcome)
    outcome["call_hash"] = row_hash(call)
    return call, outcome


def iter_trade_files(root: Path, since: str | None):
    for f in sorted(glob.glob(str(root / "docs" / "paper-trades" / "*" / "????-??-??.json"))):
        p = Path(f)
        d = p.stem
        if not DATE_RE.match(d) or (since and d < since):
            continue
        yield p.parent.name, d, p


def load_trades(root: Path, since: str | None) -> tuple[list[dict], list[dict], list[str]]:
    calls, outcomes, errors = [], [], []
    for engine, date, path in iter_trade_files(root, since):
        try:
            day = json.loads(path.read_text())
        except Exception as e:  # unreadable file: report, never guess
            errors.append(f"{path}: {e}")
            continue
        if not isinstance(day, dict):
            continue
        for pool, t in closed_trades(day):
            c, o = trade_rows(engine, date, pool, t)
            calls.append(c)
            outcomes.append(o)
    return calls, outcomes, errors


def load_baselines(root: Path, since: str | None) -> list[dict]:
    out = []
    for f in sorted(glob.glob(str(root / "docs" / "research" / "daygain" / "baseline" / "*.json"))):
        p = Path(f)
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        if not isinstance(d, dict) or "eod" not in d:
            continue
        date = d.get("date") or p.stem
        if since and date < since:
            continue
        eod = d["eod"] or {}
        out.append(sanitize({
            "kind": "baseline",
            "rule": BASELINE_RULE,
            "period_date": date,
            "net": _num(eod.get("net")),
            "gross": _num(eod.get("gross")),
            "cost": _num(eod.get("cost")),
            "priced": eod.get("priced"),
            "stops": eod.get("stops"),
            "capital": d.get("capital"),
            "decision": d.get("decision"),
            "rows": eod.get("rows"),
            "source": str(p.relative_to(root)),
            "ledger_date": date,
        }))
    return out


def load_shadow_verdicts(root: Path, since: str | None) -> list[dict]:
    out = []
    for sub, test_id in (("armband", "armband-shadow"), ("regime", "regime-shadow")):
        for f in sorted(glob.glob(str(root / "docs" / "research" / "shadows" / sub / "*.json"))):
            p = Path(f)
            try:
                d = json.loads(p.read_text())
            except Exception:
                continue
            if not isinstance(d, dict):
                continue
            date = d.get("date") or p.stem
            if since and date < since:
                continue
            out.append(sanitize({
                "kind": "verdict",
                "test_id": test_id,
                "hypothesis": f"{sub} shadow ledger for {date}: alternative parameters run side-by-side with live",
                "result": "PENDING",
                "author": "shadow-runner",
                "date": date,
                "data": d,
                "source": str(p.relative_to(root)),
                "ledger_date": date,
            }))
    return out


def load_phase0_verdicts(root: Path, since: str | None) -> list[dict]:
    out = []
    for f in sorted(glob.glob(str(root / "docs" / "research" / "daygain" / "phase0-holdout-*.md"))):
        p = Path(f)
        m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
        date = m.group(1) if m else None
        if since and date and date < since:
            continue
        text = p.read_text()
        title = next((ln.lstrip("# ").strip() for ln in text.splitlines() if ln.startswith("#")), p.stem)
        out.append({
            "kind": "verdict",
            "test_id": "daygain-phase0",
            "hypothesis": title,
            "result": "KILL",
            "author": "daygain-phase0-harness",
            "date": date,
            "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "content": text,
            "source": str(p.relative_to(root)),
            "ledger_date": date,
        })
    return out


# ----------------------------------------------------------------------------- writer
class Writer:
    def __init__(self, conn, schema: str, dry_run: bool):
        self.conn, self.schema, self.dry_run = conn, schema, dry_run
        self.counts = {t: {"inserted": 0, "skipped": 0} for t in TABLES}
        self._existing: dict[str, set[str]] = {}
        self._last_hash: dict[str, str | None] = {}
        self.call_ids: dict[str, str] = {}

    def _prime(self, table: str):
        if table in self._existing:
            return
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT row_hash FROM {self.schema}.{table}")
            self._existing[table] = {r[0] for r in cur.fetchall()}
            cur.execute(f"SELECT row_hash FROM {self.schema}.{table} ORDER BY seq DESC LIMIT 1")
            r = cur.fetchone()
            self._last_hash[table] = r[0] if r else None

    def insert(self, table: str, payload: dict, typed: dict, tenant: str = TENANT, jurisdiction: str = "IN") -> str:
        """Insert unless the hash exists. Returns the row_hash."""
        self._prime(table)
        h = row_hash(payload)
        if h in self._existing[table]:
            self.counts[table]["skipped"] += 1
            return h
        self._existing[table].add(h)
        prev = self._last_hash[table]
        self._last_hash[table] = h
        self.counts[table]["inserted"] += 1
        if self.dry_run:
            return h
        cols = ["tenant", "jurisdiction", "payload", "row_hash", "prev_hash"] + list(typed)
        vals = [tenant, jurisdiction, canonical_json(payload), h, prev] + list(typed.values())
        sql = (f"INSERT INTO {self.schema}.{table} ({', '.join(cols)}) VALUES "
               f"(%s, %s, %s::jsonb, %s, %s{', %s' * len(typed)}) RETURNING id")
        with self.conn.cursor() as cur:
            cur.execute(sql, vals)
            rid = cur.fetchone()[0]
        if table == "calls":
            self.call_ids[h] = str(rid)
        return h

    def call_id_for(self, call_hash: str) -> str | None:
        if call_hash in self.call_ids:
            return self.call_ids[call_hash]
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT id FROM {self.schema}.calls WHERE row_hash = %s", (call_hash,))
            r = cur.fetchone()
        if r:
            self.call_ids[call_hash] = str(r[0])
        return self.call_ids.get(call_hash)


def write_all(w: Writer, calls, outcomes, baselines, verdicts):
    for c, o in zip(calls, outcomes):
        jur = "US" if c["market"] == "US" else "IN"
        ch = w.insert("calls", c, {
            "symbol": c["symbol"], "market": c["market"], "side": c["side"], "engine": c["engine"],
            "published_at": (f"{c['entry_date']} {c['entry_time'] or '00:00:00'} {MARKET_TZ[c['market']]}"
                             if c["entry_date"] else None),
            "pre_registered": False, "pre_registration_hash": None,
        }, jurisdiction=jur)
        call_id = None if w.dry_run else w.call_id_for(ch)
        w.insert("outcomes", o, {
            "call_id": call_id, "engine": o["engine"], "trade_date": o["trade_date"],
            "realized_net": o["pnl_net"], "cost": o["cost"],
        }, jurisdiction=jur)
    for b in baselines:
        w.insert("baselines", b, {"period_date": b["period_date"], "rule": b["rule"], "net": b["net"]})
    for v in verdicts:
        w.insert("verdicts", v, {"test_id": v["test_id"], "hypothesis": v["hypothesis"],
                                 "result": v["result"], "author": v["author"]})


# ----------------------------------------------------------------------------- roots
def compute_roots(conn, schema: str, tenant: str, today: dt.date) -> dict[str, tuple[str, int, dict]]:
    """{ledger_date: (merkle_root, row_count, per_table_counts)} over closed dates (< today).
    Leaves are the row hashes of every table for that date, sorted, so the root is independent
    of insertion order and of the file a row was first seen in."""
    per_date: dict[str, list[str]] = {}
    per_table: dict[str, dict[str, int]] = {}
    with conn.cursor() as cur:
        for table in TABLES:
            if table == "ledger_roots":
                continue
            cur.execute(f"SELECT payload->>'ledger_date', row_hash FROM {schema}.{table} WHERE tenant = %s",
                        (tenant,))
            for d, h in cur.fetchall():
                if not d or not DATE_RE.match(d) or dt.date.fromisoformat(d) >= today:
                    continue
                per_date.setdefault(d, []).append(h)
                per_table.setdefault(d, {}).setdefault(table, 0)
                per_table[d][table] += 1
    return {d: (merkle_root(sorted(hs)), len(hs), per_table[d]) for d, hs in per_date.items()}


def upsert_roots(w: Writer, tenant: str, today: dt.date) -> dict:
    roots = compute_roots(w.conn, w.schema, tenant, today)
    with w.conn.cursor() as cur:
        cur.execute(f"SELECT root_date::text, merkle_root FROM {w.schema}.ledger_roots WHERE tenant = %s", (tenant,))
        existing = dict(cur.fetchall())
    report = {"inserted": 0, "unchanged": 0, "mismatch": []}
    for d in sorted(roots):
        mr, n, tables = roots[d]
        if d in existing:
            if existing[d] == mr:
                report["unchanged"] += 1
            else:
                report["mismatch"].append({"date": d, "stored": existing[d], "recomputed": mr, "rows": n})
            continue
        payload = {"kind": "ledger_root", "tenant": tenant, "root_date": d, "merkle_root": mr,
                   "row_count": n, "tables": tables, "ledger_date": d}
        w.insert("ledger_roots", payload, {"root_date": d, "merkle_root": mr, "row_count": n}, tenant=tenant)
        report["inserted"] += 1
    return report


# ----------------------------------------------------------------------------- entry
def run(root: Path | str = REPO_ROOT, since: str | None = None, dry_run: bool = False,
        conn=None, schema: str | None = None, today: dt.date | None = None, tenant: str = TENANT) -> dict:
    root = Path(root)
    schema = schema or db.schema()
    today = today or dt.date.today()
    calls, outcomes, errors = load_trades(root, since)
    baselines = load_baselines(root, since)
    verdicts = load_shadow_verdicts(root, since) + load_phase0_verdicts(root, since)

    own = conn is None
    if own:
        conn = db.connect()
    try:
        db.apply_migration(conn, schema)
        w = Writer(conn, schema, dry_run)
        write_all(w, calls, outcomes, baselines, verdicts)
        roots = None if dry_run else upsert_roots(w, tenant, today)
        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    finally:
        if own:
            conn.close()
    return {"dry_run": dry_run, "parsed": {"calls": len(calls), "outcomes": len(outcomes),
                                          "baselines": len(baselines), "verdicts": len(verdicts)},
            "tables": w.counts, "roots": roots, "errors": errors}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", help="only sources dated >= YYYY-MM-DD")
    ap.add_argument("--dry-run", action="store_true", help="parse + count, roll back, write nothing")
    ap.add_argument("--root", default=str(REPO_ROOT), help="tree containing docs/ (default: repo root)")
    a = ap.parse_args(argv)
    if a.since and not DATE_RE.match(a.since):
        ap.error("--since must be YYYY-MM-DD")
    try:
        r = run(a.root, a.since, a.dry_run)
    except Exception as e:
        print(f"ledger: cannot run migration: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    mode = "DRY-RUN (nothing written)" if r["dry_run"] else "written"
    print(f"ledger migrate_json — {mode}; parsed: {r['parsed']}")
    for t in TABLES:
        c = r["tables"][t]
        print(f"  {t:<13} inserted={c['inserted']:>6}  skipped(dup/existing)={c['skipped']:>6}")
    if r["roots"] is not None:
        print(f"  roots: inserted={r['roots']['inserted']} unchanged={r['roots']['unchanged']}")
        for m in r["roots"]["mismatch"]:
            print(f"  !! ROOT MISMATCH {m['date']}: stored {m['stored'][:12]}… != recomputed {m['recomputed'][:12]}… "
                  f"({m['rows']} rows) — ledger_roots is append-only; investigate before trusting this date")
    for e in r["errors"]:
        print(f"  ! unreadable: {e}")
    return 1 if (r["roots"] and r["roots"]["mismatch"]) else 0


if __name__ == "__main__":
    sys.exit(main())
