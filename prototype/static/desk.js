/* ═══════════════════════════════════════════════════════════════════════════
   desk.js — TradePilot Terminal logic.
   2026-08-11

   SEPARATE FILE on purpose: on 2026-08-03 a tab shipped blank because its JS
   was appended inside a <script src> tag, whose inline content the browser
   discards entirely. Never again.

   PERFORMANCE CONTRACT (the reason this shell exists):
   - Every fetch is parallel and owns exactly one card. A failure or a slow
     feed degrades ITS card to a stale/warming chip — it never blocks a sibling.
   - Every fetch has a hard timeout. A spinner that can spin forever is a bug.
   - Polling pauses when the tab is hidden (document.visibilitychange).

   XSS: every interpolated value passes esc() or a numeric formatter. The score
   feed is our own, but it is fed by yfinance plus an NSE roster which has
   already served 30 symbols nobody asked for — a feed that can serve the wrong
   instruments is not a feed to trust with markup.
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  /* ── utils ─────────────────────────────────────────────────────────── */
  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function inr(v, d) {
    if (v == null || isNaN(v)) return "--";
    return Number(v).toLocaleString("en-IN", {
      minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 });
  }
  function sgn(v, d) {
    if (v == null || isNaN(v)) return "--";
    return (v > 0 ? "+" : "") + inr(v, d);
  }
  function cls(v) { return v > 0 ? "pos" : v < 0 ? "neg" : "flat"; }

  function jget(url, timeoutMs) {
    var ctl = new AbortController();
    var t = setTimeout(function () { ctl.abort(); }, timeoutMs || 6000);
    return fetch(url, { signal: ctl.signal }).then(function (r) {
      clearTimeout(t);
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json().then(function (j) { return { j: j, h: r.headers }; });
    });
  }

  /* ── clock + session pill ──────────────────────────────────────────── */
  function tickClock() {
    var now = new Date();
    var ist = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
    var hh = String(ist.getHours()).padStart(2, "0");
    var mm = String(ist.getMinutes()).padStart(2, "0");
    var ss = String(ist.getSeconds()).padStart(2, "0");
    $("clock").textContent = hh + ":" + mm + ":" + ss + " IST";
    var mins = ist.getHours() * 60 + ist.getMinutes();
    var wk = ist.getDay() >= 1 && ist.getDay() <= 5;
    var pill = $("sessPill");
    if (wk && mins >= 555 && mins < 930) {        // 09:15–15:30
      pill.textContent = "LIVE"; pill.className = "pill live";
    } else if (wk && mins >= 530 && mins < 555) { // 08:50 fleet launch → open
      pill.textContent = "PRE-OPEN"; pill.className = "pill pre";
    } else {
      pill.textContent = "CLOSED"; pill.className = "pill closed";
    }
  }

  /* ── index strip ───────────────────────────────────────────────────── */
  var IDX = [["nifty", "NIFTY 50"], ["sensex", "SENSEX"], ["banknifty", "BANK NIFTY"],
             ["niftyit", "NIFTY IT"], ["vix", "INDIA VIX"]];
  function loadIndices() {
    jget("/api/indices", 8000).then(function (res) {
      IDX.forEach(function (pair) {
        var el = $("idx-" + pair[0]);
        if (!el) return;
        var row = res.j[pair[0]];
        if (!row) return;
        el.classList.toggle("stale", !!row.stale);
        var v = el.querySelector(".v");
        v.classList.remove("skel");        // skel paints text transparent — a value
        v.textContent = inr(row.price, 2); // set under it stays invisible forever
        var c = el.querySelector(".c");
        c.textContent = sgn(row.changePct, 2) + "%";
        c.className = "c num " + cls(row.changePct);
        if (row.stale) el.title = "STALE — " + (row.source || "?") +
          (row.prevCloseDate ? " · prev close " + row.prevCloseDate : "");
      });
    }).catch(function () { /* strip keeps last values; skeleton if never loaded */ });
  }

  /* ── desk view ─────────────────────────────────────────────────────── */
  function loadDesk() {
    jget("/api/desk", 8000).then(function (res) {
      var d = res.j;
      var f = d.fleet || {};
      var sess = d.is_live_session ? "today" : "last session " + d.session;

      $("kpiNet").innerHTML = '<span class="num ' + cls(f.net) + '">₹' + sgn(f.net) + "</span>";
      $("kpiNetSub").textContent = "fleet net · " + sess + " · modelled fees ₹" + inr(f.fees);
      $("kpiTrades").innerHTML = '<span class="num">' + inr(f.trades) + "</span>";
      $("kpiTradesSub").textContent = "closed trades · turnover ₹" + inr(f.turnover);

      var ex = d.experiment || {};
      var pct = Math.min(100, (ex.cum_trades / (ex.target || 300)) * 100);
      $("kpiExp").innerHTML = '<span class="num">' + inr(ex.cum_trades) +
        '</span><span style="color:var(--dim);font-size:15px"> / ' + inr(ex.target) + "</span>";
      $("kpiExpSub").textContent = "v5_size trades to significance · median ₹" +
        inr(ex.median_pos) + " · fee " + (ex.fee_pct != null ? ex.fee_pct + "%" : "--") +
        (ex.control_fee_pct ? " vs " + ex.control_fee_pct + "%" : "");
      $("expBar").style.width = pct + "%";

      var g = d.guards || {};
      var tg = g.telegram_entries_muted;
      $("kpiGuards").innerHTML =
        '<span class="chip ' + (tg ? "ok" : "err") + '">alerts ' + (tg ? "muted" : "ON!") + "</span> " +
        '<span class="chip ok">disk gate</span> ' +
        '<span class="chip ok">session guard</span>';
      $("kpiGuardsSub").textContent = "session guard: " + (g.session_guard || []).join(", ") +
        " · first live run at next 08:50";

      /* leaderboard */
      var rows = d.engines || [];
      renderLeaderboard(rows);

      /* open positions */
      var op = d.open_positions || [];
      var ob = $("openBody");
      if (!op.length) {
        ob.innerHTML = '<div class="empty">No open positions</div>';
      } else {
        ob.innerHTML = '<div class="scrollbox"><table class="tbl"><thead><tr>' +
          "<th>Symbol</th><th>Engine</th><th class=\"r\">Qty</th><th class=\"r\">Entry</th>" +
          "<th class=\"r\">Value</th></tr></thead><tbody>" +
          op.map(function (p) {
            return "<tr><td class=\"sym\">" + esc(p.symbol) +
              (p.side === "SHORT" ? ' <span class="chip err">S</span>' : "") +
              "</td><td class=\"eng\">" + esc(p.engine) +
              "</td><td class=\"r num\">" + inr(p.qty) +
              "</td><td class=\"r num\">" + inr(p.entry, 2) +
              "</td><td class=\"r num\">" + inr(p.value) + "</td></tr>";
          }).join("") + "</tbody></table></div>";
      }
      $("openCount").textContent = op.length + " open";

      /* exits feed */
      var exd = d.recent_exits || [];
      var eb = $("exitBody");
      if (!exd.length) {
        eb.innerHTML = '<div class="empty">No closed trades in ' + esc(d.session) + "</div>";
      } else {
        eb.innerHTML = '<div class="scrollbox" style="max-height:300px"><table class="tbl"><thead><tr>' +
          "<th>Time</th><th>Symbol</th><th>Engine</th><th class=\"r\">P&L ₹</th>" +
          "<th class=\"r\">%</th><th>Exit</th></tr></thead><tbody>" +
          exd.map(function (x) {
            var rc = (x.reason === "TARGET" || x.reason === "STOPLOSS" ||
                      x.reason === "SIGNAL_FLIP") ? x.reason : "other";
            return "<tr><td class=\"num\">" + esc((x.exit_time || "").slice(0, 5)) +
              "</td><td class=\"sym\">" + esc(x.symbol) +
              "</td><td class=\"eng\">" + esc(x.engine) +
              "</td><td class=\"r num " + cls(x.pnl) + "\">" + sgn(x.pnl) +
              "</td><td class=\"r num " + cls(x.pnl_pct) + "\">" + sgn(x.pnl_pct, 2) +
              "</td><td><span class=\"rsn " + rc + "\">" + esc(x.reason) + "</span></td></tr>";
          }).join("") + "</tbody></table></div>";
      }

      $("deskAsOf").textContent = "session " + d.session + " · updated " + d.generated_at;
      $("deskStale").className = "chip " + (d.is_live_session ? "ok" : "dim");
      $("deskStale").textContent = d.is_live_session ? "live" : "last session";
    }).catch(function () {
      $("deskStale").className = "chip warn";
      $("deskStale").textContent = "offline · retrying";
    });
  }

  var sortKey = "net", sortDir = -1;
  var lastRows = [];
  function renderLeaderboard(rows) {
    if (rows) lastRows = rows;
    rows = lastRows.slice().sort(function (a, b) {
      var x = a[sortKey], y = b[sortKey];
      if (typeof x === "string") return sortDir * x.localeCompare(y);
      return sortDir * ((x || 0) - (y || 0));
    });
    var COLS = [["name", "Engine"], ["trades", "Trades", 1], ["win_pct", "Win %", 1],
                ["median_pos", "Median Pos", 1], ["gross", "Gross ₹", 1],
                ["fees", "Fees ₹", 1], ["net", "Net ₹", 1], ["open", "Open", 1]];
    var html = '<div class="scrollbox"><table class="tbl"><thead><tr>' +
      COLS.map(function (c) {
        return "<th class=\"" + (c[2] ? "r " : "") + (sortKey === c[0] ? "sorted" : "") +
          "\" data-k=\"" + c[0] + "\">" + c[1] +
          (sortKey === c[0] ? (sortDir < 0 ? " ↓" : " ↑") : "") + "</th>";
      }).join("") + "</tr></thead><tbody>" +
      rows.map(function (r) {
        var hot = r.name === "v5_size" ? ' style="background:var(--acc-bg)"' : "";
        return "<tr" + hot + "><td class=\"sym\">" + esc(r.name) +
          (r.name === "v5" ? ' <span class="chip dim">control</span>' : "") +
          (r.name === "v5_size" ? ' <span class="chip acc">experiment</span>' : "") +
          "</td><td class=\"r num\">" + inr(r.trades) +
          "</td><td class=\"r num\">" + inr(r.win_pct) + "%" +
          "</td><td class=\"r num\">" + inr(r.median_pos) +
          "</td><td class=\"r num " + cls(r.gross) + "\">" + sgn(r.gross) +
          "</td><td class=\"r num\">" + inr(r.fees) +
          "</td><td class=\"r num " + cls(r.net) + "\"><b>" + sgn(r.net) + "</b>" +
          "</td><td class=\"r num\">" + inr(r.open) + "</td></tr>";
      }).join("") + "</tbody></table></div>";
    $("lbBody").innerHTML = html;
    $("lbBody").querySelectorAll("th").forEach(function (th) {
      th.addEventListener("click", function () {
        var k = th.getAttribute("data-k");
        if (sortKey === k) sortDir = -sortDir; else { sortKey = k; sortDir = -1; }
        renderLeaderboard(null);
      });
    });
  }

  /* ── market view ───────────────────────────────────────────────────── */
  var mktRows = [], mktFilter = "all", mktQuery = "";
  var held = {};

  function loadMarket() {
    jget("/api/scores", 9000).then(function (res) {
      if (res.h.get("X-Warming") === "1" || !res.j.length) {
        $("mktAsOf").textContent = "scores warming — first compute takes ~2 min after a restart";
        setTimeout(loadMarket, 20000);
        return;
      }
      mktRows = res.j;
      var asof = res.h.get("X-As-Of");
      $("mktAsOf").textContent = "scores as of " +
        (asof ? new Date(asof * 1000).toLocaleTimeString("en-IN", { hour12: false }) : "now") +
        (res.h.get("X-Stale") === "1" ? " · cached" : "");
      renderMarket();
    }).catch(function () {
      $("mktAsOf").textContent = "scores offline · retrying";
      setTimeout(loadMarket, 15000);
    });
    jget("/api/live-engine-picks", 6000).then(function (res) {
      held = {};
      (res.j.held || res.j.picks || []).forEach(function (s) {
        held[(s.symbol || s).toUpperCase ? (s.symbol || s).toUpperCase() : s] = true;
      });
    }).catch(function () {});
  }

  function renderMarket() {
    var rows = mktRows.filter(function (r) {
      var sym = (r.symbol || "").toUpperCase();
      if (mktQuery && sym.indexOf(mktQuery) === -1) return false;
      if (mktFilter === "gain") return (r.change || 0) > 0;
      if (mktFilter === "lose") return (r.change || 0) < 0;
      if (mktFilter === "buy") return (r.signal || "").toUpperCase() === "BUY";
      if (mktFilter === "held") return !!held[sym];
      return true;
    });
    rows.sort(function (a, b) { return (b.score || 0) - (a.score || 0); });
    $("mktCount").textContent = rows.length + " of " + mktRows.length;
    if (!rows.length) {
      $("mktBody").innerHTML = '<div class="empty">Nothing matches</div>';
      return;
    }
    $("mktBody").innerHTML = '<div class="scrollbox" style="max-height:66vh"><table class="tbl"><thead><tr>' +
      "<th>Symbol</th><th class=\"r\">Price</th><th class=\"r\">1D %</th>" +
      "<th class=\"r\">Score</th><th>Signal</th><th></th></tr></thead><tbody>" +
      rows.slice(0, 250).map(function (r) {
        var sig = (r.signal || "HOLD").toUpperCase();
        var sc = sig === "BUY" ? "ok" : sig === "SELL" || sig === "AVOID" ? "err" : "dim";
        return "<tr class=\"click\" data-sym=\"" + esc(r.symbol) + "\">" +
          "<td class=\"sym\">" + esc(r.symbol) + "</td>" +
          "<td class=\"r num\">" + inr(r.price, 2) + "</td>" +
          "<td class=\"r num " + cls(r.change) + "\">" + sgn(r.change, 2) + "%</td>" +
          "<td class=\"r num\">" + inr(r.score, 1) + "</td>" +
          "<td><span class=\"chip " + sc + "\">" + esc(sig) + "</span></td>" +
          "<td>" + (held[(r.symbol || "").toUpperCase()] ? '<span class="chip acc">held</span>' : "") +
          "</td></tr>";
      }).join("") + "</tbody></table></div>";
    $("mktBody").querySelectorAll("tr.click").forEach(function (tr) {
      tr.addEventListener("click", function () { openDrawer(tr.getAttribute("data-sym")); });
    });
  }

  /* ── drawer (stock detail) ─────────────────────────────────────────── */
  function openDrawer(sym) {
    var row = null;
    for (var i = 0; i < mktRows.length; i++)
      if (mktRows[i].symbol === sym) { row = mktRows[i]; break; }
    $("dTitle").textContent = sym;
    $("dPrice").textContent = row ? "₹" + inr(row.price, 2) : "…";
    $("dPrice").className = "price num";
    $("dMeta").textContent = row
      ? sgn(row.change, 2) + "% today · score " + inr(row.score, 1) + " · " + esc(row.signal || "")
      : "";
    $("dSrc").textContent = "loading intraday…";
    var cv = $("dChart"), ctx = cv.getContext("2d");
    ctx.clearRect(0, 0, cv.width, cv.height);
    $("drawer").classList.add("open");
    $("overlay").classList.add("open");
    jget("/api/stock/" + encodeURIComponent(sym) + "/spark", 12000).then(function (res) {
      drawSpark(cv, res.j.bars || []);
      $("dSrc").textContent = (res.j.bars || []).length + " × 5m bars · source: " + esc(res.j.source);
    }).catch(function () {
      $("dSrc").textContent = "intraday unavailable";
    });
  }
  function closeDrawer() {
    $("drawer").classList.remove("open");
    $("overlay").classList.remove("open");
  }

  function drawSpark(cv, bars) {
    var dpr = window.devicePixelRatio || 1;
    var W = cv.clientWidth * dpr, H = cv.clientHeight * dpr;
    cv.width = W; cv.height = H;
    var ctx = cv.getContext("2d");
    ctx.clearRect(0, 0, W, H);
    if (bars.length < 2) return;
    var vals = bars.map(function (b) { return b[1]; });
    var mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals);
    if (mx - mn < 1e-9) { mn -= 1; mx += 1; }
    var up = vals[vals.length - 1] >= vals[0];
    var col = up ? "#16c784" : "#ea3943";
    var pad = 6 * dpr;
    function X(i) { return pad + (W - 2 * pad) * i / (vals.length - 1); }
    function Y(v) { return pad + (H - 2 * pad) * (1 - (v - mn) / (mx - mn)); }
    // faint gridline at the open
    ctx.strokeStyle = "#242d3d"; ctx.lineWidth = 1; ctx.setLineDash([4 * dpr, 4 * dpr]);
    ctx.beginPath(); ctx.moveTo(pad, Y(vals[0])); ctx.lineTo(W - pad, Y(vals[0])); ctx.stroke();
    ctx.setLineDash([]);
    // area fill
    var g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, up ? "rgba(22,199,132,.22)" : "rgba(234,57,67,.22)");
    g.addColorStop(1, "rgba(0,0,0,0)");
    ctx.beginPath(); ctx.moveTo(X(0), Y(vals[0]));
    for (var i = 1; i < vals.length; i++) ctx.lineTo(X(i), Y(vals[i]));
    ctx.lineTo(X(vals.length - 1), H); ctx.lineTo(X(0), H); ctx.closePath();
    ctx.fillStyle = g; ctx.fill();
    // line + endpoint
    ctx.beginPath(); ctx.moveTo(X(0), Y(vals[0]));
    for (i = 1; i < vals.length; i++) ctx.lineTo(X(i), Y(vals[i]));
    ctx.strokeStyle = col; ctx.lineWidth = 1.6 * dpr; ctx.stroke();
    ctx.beginPath();
    ctx.arc(X(vals.length - 1), Y(vals[vals.length - 1]), 3 * dpr, 0, 7);
    ctx.fillStyle = col; ctx.fill();
  }

  /* ── tabs ──────────────────────────────────────────────────────────── */
  function switchTab(name) {
    document.querySelectorAll(".nav a[data-tab]").forEach(function (a) {
      a.classList.toggle("on", a.getAttribute("data-tab") === name);
    });
    document.querySelectorAll(".view").forEach(function (v) {
      v.classList.toggle("on", v.id === "view-" + name);
    });
    if (name === "market" && !mktRows.length) loadMarket();
  }

  /* ── boot ──────────────────────────────────────────────────────────── */
  document.addEventListener("DOMContentLoaded", function () {
    tickClock(); setInterval(tickClock, 1000);
    loadIndices(); loadDesk();

    // Deep links: /#market opens the tab, /#market/RELIANCE opens the drawer too.
    var h = (location.hash || "").replace(/^#/, "").split("/");
    if (h[0] === "market") {
      switchTab("market");
      if (h[1]) {
        var want = h[1].toUpperCase();
        var tries = 0, iv = setInterval(function () {
          if (mktRows.length || ++tries > 40) {
            clearInterval(iv);
            if (mktRows.length) openDrawer(want);
          }
        }, 500);
      }
    }

    document.querySelectorAll(".nav a[data-tab]").forEach(function (a) {
      a.addEventListener("click", function (e) {
        e.preventDefault(); switchTab(a.getAttribute("data-tab"));
      });
    });
    $("overlay").addEventListener("click", closeDrawer);
    $("dClose").addEventListener("click", closeDrawer);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeDrawer();
    });
    $("mktSearch").addEventListener("input", function () {
      mktQuery = this.value.trim().toUpperCase(); renderMarket();
    });
    document.querySelectorAll(".fpill").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll(".fpill").forEach(function (x) { x.classList.remove("on"); });
        b.classList.add("on");
        mktFilter = b.getAttribute("data-f");
        renderMarket();
      });
    });

    // polling — paused while the tab is hidden
    setInterval(function () {
      if (document.hidden) return;
      loadDesk();
    }, 30000);
    setInterval(function () {
      if (document.hidden) return;
      loadIndices();
      if ($("view-market").classList.contains("on")) loadMarket();
    }, 60000);
  });
})();
