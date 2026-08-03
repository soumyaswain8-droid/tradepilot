/* ═══════════════════════════════════════════════════════════════════════════
   clay-market.js — renders the claymorphic market explorer.
   2026-08-03

   Deliberately a SEPARATE FILE. On 2026-08-03 the US Market tab shipped blank
   because its JS had been appended inside a <script src="..."> tag, whose inline
   content the browser discards entirely. Keeping this out of the 7,100-line
   template removes that whole class of mistake.

   Reads the existing /api/scores — no new endpoint, no change to the engines.
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  var INDIA_INDICES = [
    { key: "NIFTY 50", sel: "nifty" },
    { key: "SENSEX", sel: "sensex" },
    { key: "BANK NIFTY", sel: "banknifty" },
    { key: "NIFTY IT", sel: "niftyit" },
    { key: "INDIA VIX", sel: "vix" }
  ];

  // Membership tiers. NIFTY 50 is the engines' actual universe, so it leads.
  var TIERS = [
    { id: "all", label: "All" },
    { id: "n50", label: "NIFTY 50" },
    { id: "gain", label: "Gainers" },
    { id: "lose", label: "Losers" },
    { id: "held", label: "Held by an engine" },
    { id: "buy", label: "BUY signal" }
  ];

  var HUES = ["#6366F1", "#8B5CF6", "#0EA5E9", "#10B981", "#F59E0B", "#EC4899", "#14B8A6", "#F43F5E"];

  function hueFor(sym) {
    var h = 0, i;
    for (i = 0; i < sym.length; i++) { h = (h * 31 + sym.charCodeAt(i)) >>> 0; }
    return HUES[h % HUES.length];
  }

  function shade(hex, amt) {
    var n = parseInt(hex.slice(1), 16);
    var r = Math.min(255, Math.max(0, (n >> 16) + amt));
    var g = Math.min(255, Math.max(0, ((n >> 8) & 255) + amt));
    var b = Math.min(255, Math.max(0, (n & 255) + amt));
    return "rgb(" + r + "," + g + "," + b + ")";
  }

  /* XSS: every row is built as an HTML string and assigned via innerHTML, so EVERY
     interpolated value must pass through esc() or a numeric formatter — no
     exceptions, including fields that "obviously" hold a ticker. /api/scores is our
     own endpoint, but it is fed by yfinance and an NSE symbol roster, and on
     2026-08-03 that exact roster turned out to contain 30 symbols nobody requested.
     A feed that can serve the wrong instruments is not a feed to trust with markup.
     Colours come from the fixed HUES palette, never from response data. */
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function num(v, d) {
    if (v == null || isNaN(v)) return "--";
    return Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
  }

  function cls(v) { return v > 0 ? "pos" : v < 0 ? "neg" : "flat"; }
  function arrow(v) { return v > 0 ? "▲" : v < 0 ? "▼" : "–"; }

  /* A deterministic sparkline. There is no intraday series on /api/scores, so this
     is shaped from the row's own numbers (change, RSI, trend) rather than random —
     a random line that redraws differently on every refresh would look like data
     and be a lie. Marked aria-hidden and never presented as a price history. */
  function spark(row) {
    var w = 88, h = 30, pts = 16, i, x, y;
    var chg = Number(row.change) || 0;
    var rsi = Number(row.rsi) || 50;
    var seed = 0, s = String(row.symbol || row.name || "");
    for (i = 0; i < s.length; i++) { seed = (seed * 33 + s.charCodeAt(i)) >>> 0; }
    var d = "", amp = Math.min(1, Math.abs(chg) / 4) * 7 + 2;
    for (i = 0; i < pts; i++) {
      seed = (seed * 1103515245 + 12345) >>> 0;
      var jitter = ((seed >>> 16) % 100) / 100 - 0.5;
      var trend = (i / (pts - 1)) * (chg / 4);
      y = h / 2 - trend * 6 - jitter * amp * 0.55 - (rsi - 50) / 50 * 2;
      y = Math.max(3, Math.min(h - 3, y));
      x = (i / (pts - 1)) * w;
      d += (i ? " L" : "M") + x.toFixed(1) + "," + y.toFixed(1);
    }
    var col = chg > 0 ? "#10B981" : chg < 0 ? "#F43F5E" : "#94A3B8";
    return '<svg class="clay-spark" viewBox="0 0 ' + w + " " + h + '" aria-hidden="true" focusable="false">'
      + '<path d="' + d + '" fill="none" stroke="' + col + '" stroke-width="1.8" '
      + 'stroke-linecap="round" stroke-linejoin="round" opacity=".85"/></svg>';
  }

  /* The column no brokerage screen can show: which of the 9 live engines currently
     holds this name, and how many agree. Consensus is the interesting signal — two
     independent strategies landing on the same stock says more than either alone —
     so the count leads when it is 2 or more. */
  function engineFor(sym, held) {
    var h = held && held[sym];
    if (!h) return '<span class="clay-eng none"><i></i>not held</span>';
    var engines = (h.engines || []).map(function (e) { return String(e).replace(/_/g, "."); });
    var n = h.consensus_count || engines.length;
    var label = engines.length ? engines.join(", ") : "held";
    return '<span class="clay-eng" title="' + esc(label) + '"><i></i>'
      + (n >= 2 ? "★" + n + " " : "") + esc(label) + "</span>";
  }

  function rowHTML(r, held) {
    var sym = r.symbol || r.name || "?";
    var c = hueFor(sym);
    var chg = Number(r.change) || 0;
    var sig = String(r.direction || "HOLD").toLowerCase();
    var sc = Number(r.score) || 0;
    var scCls = sc >= 70 ? "pos" : sc >= 50 ? "" : "neg";
    return '<div class="clay-row">'
      + '<div class="clay-name">'
      + '<div class="clay-mono" style="background-image:linear-gradient(145deg,' + shade(c, 34) + "," + c + ')">'
      + esc(sym.slice(0, 2)) + "</div>"
      + '<div class="clay-nm"><b>' + esc(r.name || sym) + "</b>"
      + '<span class="clay-tick">' + esc(sym) + " · NSE</span></div></div>"
      + spark(r)
      + '<div class="clay-px"><b>₹' + num(r.price, 2) + "</b>"
      + '<span class="' + cls(chg) + '">' + arrow(chg) + " " + num(Math.abs(chg), 2) + "%</span></div>"
      + '<div class="clay-score ' + scCls + '">' + (sc ? sc.toFixed(0) : "--") + "</div>"
      + '<span class="clay-sig ' + (sig === "buy" ? "buy" : sig === "sell" ? "sell" : "hold") + '">'
      + esc(String(r.direction || "HOLD")) + "</span>"
      + engineFor(sym, held)
      + "</div>";
  }

  function apply(rows, tier) {
    var out = rows.slice();
    if (tier === "gain") out = out.filter(function (r) { return (r.change || 0) > 0; })
      .sort(function (a, b) { return (b.change || 0) - (a.change || 0); });
    else if (tier === "lose") out = out.filter(function (r) { return (r.change || 0) < 0; })
      .sort(function (a, b) { return (a.change || 0) - (b.change || 0); });
    else if (tier === "buy") out = out.filter(function (r) { return String(r.direction).toUpperCase() === "BUY"; });
    else if (tier === "held") out = out.filter(function (r) { return window.__clayHeld && window.__clayHeld[r.symbol || r.name]; });
    else out = out.sort(function (a, b) { return (b.score || 0) - (a.score || 0); });
    return out;
  }

  function render(host, rows, tier, held) {
    var list = apply(rows, tier);
    host.querySelector(".clay-body").innerHTML = list.length
      ? list.map(function (r) { return rowHTML(r, held); }).join("")
      : '<div class="clay-empty">No stocks match this filter right now.</div>';
    var n = host.querySelector(".clay-count");
    if (n) n.textContent = list.length + " of " + rows.length;
  }

  function indicesHTML() {
    return INDIA_INDICES.map(function (i) {
      return '<div class="clay-idx" data-idx="' + esc(i.sel) + '">'
        + '<span class="clay-idx-name">' + esc(i.key) + "</span>"
        + '<span class="clay-idx-val">--</span>'
        + '<span class="clay-idx-chg flat">--</span>'
        + "</div>";
    }).join("");
  }

  function shell() {
    return '<div class="clay-wrap">'
      + '<div class="clay-indices">' + indicesHTML() + "</div>"
      + '<div class="clay-crumb"><span>India Stocks /</span> Explore</div>'
      + '<div class="clay-sec"><h3>All stocks</h3>'
      + '<span class="clay-sec-note clay-count">--</span></div>'
      + '<div class="clay-pills">' + TIERS.map(function (t, i) {
        return '<button class="clay-pill' + (i === 0 ? " on" : "") + '" data-tier="' + t.id + '">'
          + esc(t.label) + "</button>";
      }).join("") + "</div>"
      + '<div class="clay-table"><div class="clay-scroll">'
      + '<div class="clay-head"><div>Stock</div><div>Trend</div><div style="text-align:right">Price / 1D</div>'
      + '<div style="text-align:center">Score</div><div style="text-align:center">Signal</div><div>Engine</div></div>'
      + '<div class="clay-body"><div class="clay-empty">Loading market…</div></div>'
      + "</div></div></div>";
  }

  function fillIndices(host) {
    var map = { nifty: "NIFTY", sensex: "SENSEX" };
    Object.keys(map).forEach(function (k) {
      var el = host.querySelector('[data-idx="' + k + '"]');
      if (!el) return;
      // Read the values the topbar already has rather than adding a second fetch.
      var nodes = document.querySelectorAll(".idx-label");
      for (var i = 0; i < nodes.length; i++) {
        if (nodes[i].textContent.trim().toUpperCase().indexOf(map[k]) === 0) {
          var p = nodes[i].parentElement;
          var v = p.querySelector(".idx-value") || p.children[1];
          var c = p.querySelector(".idx-change") || p.children[2];
          if (v) el.querySelector(".clay-idx-val").textContent = v.textContent.trim();
          if (c) {
            var t = c.textContent.trim();
            var ch = el.querySelector(".clay-idx-chg");
            ch.textContent = t;
            ch.className = "clay-idx-chg " + (t.indexOf("-") === 0 ? "neg" : t.indexOf("+") === 0 ? "pos" : "flat");
          }
          break;
        }
      }
    });
  }

  window.clayMarket = function (hostId) {
    var host = document.getElementById(hostId);
    if (!host) return;
    host.innerHTML = shell();
    fillIndices(host);

    var rows = [], tier = "all";
    host.querySelectorAll(".clay-pill").forEach(function (b) {
      b.addEventListener("click", function () {
        host.querySelectorAll(".clay-pill").forEach(function (x) { x.classList.remove("on"); });
        b.classList.add("on");
        tier = b.getAttribute("data-tier");
        host.querySelector(".clay-sec h3").textContent =
          TIERS.filter(function (t) { return t.id === tier; })[0].label;
        render(host, rows, tier, window.__clayHeld);
      });
    });

    // Holdings resolve in ms while /api/scores takes ~15s, so they are fetched
    // independently rather than chained. A holdings failure must never blank the
    // market — it downgrades one column, it is not a market outage.
    fetch("/api/live-engine-picks")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var idx = {};
        (d.positions || []).forEach(function (p) { if (p && p.symbol) idx[p.symbol] = p; });
        window.__clayHeld = idx;
        if (rows.length) render(host, rows, tier, idx);
      })
      .catch(function () { /* column degrades to "not held"; market still renders */ });

    fetch("/api/scores")
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (d) {
        rows = Array.isArray(d) ? d : (d.stocks || d.data || []);
        render(host, rows, tier, window.__clayHeld);
      })
      .catch(function (e) {
        // Say WHY it is empty. A blank table that looks like a quiet market is the
        // same lie as a verifier that passes without verifying.
        host.querySelector(".clay-body").innerHTML =
          '<div class="clay-empty">Could not load /api/scores (' + esc(e.message)
          + "). This is a load failure, not an empty market.</div>";
      });
  };
})();
