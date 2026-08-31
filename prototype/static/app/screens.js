"use strict";

/* One render function per screen. Each takes a node and a payload and builds
   DOM -- no fetching, so a renderer can be driven from a console with a
   fixture. */

(function () {
  function money(n) {
    if (n === null || n === undefined) return "--";
    var whole = Math.round(Math.abs(n));
    /* Decide the sign AFTER rounding: -0.4 rounds to 0, and "-₹0" is not a
       number anyone should be shown. */
    var neg = whole > 0 && n < 0;
    var s = whole.toString();
    /* Indian grouping: last three digits, then pairs. */
    var last3 = s.slice(-3);
    var rest = s.slice(0, -3);
    if (rest) last3 = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + last3;
    return (neg ? "-₹" : "₹") + last3;
  }

  function pct(n) {
    if (n === null || n === undefined) return "--";
    return (n > 0 ? "+" : "") + n.toFixed(1) + "%";
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }

  function card(title) {
    var c = el("div", "card");
    if (title) c.appendChild(el("h2", null, title));
    return c;
  }

  /* The rate is never shown alone. resolved and is_meaningful ship in the same
     payload precisely so a page cannot honestly print 62% without also
     printing that it is eleven calls. */
  function rateLine(rec) {
    var wrap = el("div");
    if (rec.hit_rate === null) {
      wrap.appendChild(el("div", "big", "--"));
      wrap.appendChild(el("div", "muted", rec.total
        ? "nothing has resolved yet"
        : "no calls recorded yet"));
      return wrap;
    }
    wrap.appendChild(el("div", "big " + (rec.hit_rate >= 50 ? "up" : "down"),
                        rec.hit_rate.toFixed(1) + "%"));
    wrap.appendChild(el("div", "muted",
      rec.resolved + " resolved of " + rec.total + " recorded"));
    if (!rec.is_meaningful) {
      wrap.appendChild(el("div", "thin",
        "Too few to be meaningful -- we show a rate from " +
        rec.meaningful_from + "."));
    }
    return wrap;
  }

  function callRow(c, onOpen) {
    var row = el("div", "row");
    var grow = el("div", "grow");
    grow.appendChild(el("div", "name", c.symbol));
    grow.appendChild(el("div", "thin", c.signal || ""));
    row.appendChild(grow);

    var right = el("div");
    right.style.textAlign = "right";
    right.appendChild(el("div", null, money(c.price_at_call)));
    var pill = el("span", "pill" + (c.side === "SELL" ? " sell" : ""),
                  c.side + (c.score ? " " + Math.round(c.score) : ""));
    right.appendChild(pill);
    row.appendChild(right);

    if (onOpen) {
      row.style.cursor = "pointer";
      row.addEventListener("click", function () { onOpen(c.id); });
    }
    return row;
  }

  function home(node, data) {
    node.innerHTML = "";

    var kpis = el("div", "kpis");

    var value = card(null);
    value.appendChild(el("div", "label", "Your portfolio"));
    if (data.signedOut) {
      value.appendChild(el("div", "big", "--"));
      value.appendChild(el("div", "muted", "Sign in to see your book"));
    } else if (data.bookFailed) {
      value.appendChild(el("div", "big", "--"));
      value.appendChild(el("div", "muted", "Could not load your book just now."));
    } else if (!data.book || !data.book.positions.length) {
      value.appendChild(el("div", "big", "--"));
      value.appendChild(el("div", "muted", "Log your first trade to see it here"));
    } else {
      var t = data.book.totals;
      value.appendChild(el("div", "big", money(t.value)));
      value.appendChild(el("div", "muted " + (t.pnl >= 0 ? "up" : "down"),
                           money(t.pnl) + " overall"));
      if (t.unpriced) {
        value.appendChild(el("div", "thin",
          t.unpriced + " holding(s) have no live price and are not counted"));
      }
    }
    kpis.appendChild(value);

    var rate = card(null);
    rate.appendChild(el("div", "label", "Hit rate"));
    if (data.record) {
      rate.appendChild(rateLine(data.record));
    } else {
      rate.appendChild(el("div", "big", "--"));
      rate.appendChild(el("div", "muted", "Could not load the record."));
    }
    kpis.appendChild(rate);
    node.appendChild(kpis);

    var calls = card("Today's calls");
    if (!data.calls) {
      calls.appendChild(el("div", "empty", "Could not load today's calls."));
    } else if (!data.calls.calls.length) {
      calls.appendChild(el("div", "empty", "No calls published yet."));
    } else {
      for (var i = 0; i < Math.min(data.calls.calls.length, 5); i++) {
        calls.appendChild(callRow(data.calls.calls[i], data.onOpenCall));
      }
    }
    node.appendChild(calls);
  }

  function stamp(iso) {
    if (!iso) return "";
    return iso.replace("T", " ").slice(0, 16);
  }

  function calls(node, data) {
    node.innerHTML = "";
    var c = card("Published calls");
    var list = (data.calls && data.calls.calls) || [];
    if (!list.length) {
      c.appendChild(el("div", "empty", "No calls published yet."));
    } else {
      for (var i = 0; i < list.length; i++) {
        c.appendChild(callRow(list[i], data.onOpenCall));
      }
      /* Outside market hours this list is the last session's. Saying so is
         cheaper than a support question about why it has not moved. */
      c.appendChild(el("div", "thin", "As of " + stamp(data.calls.as_of)));
    }
    node.appendChild(c);
  }

  function outcomeLine(c) {
    if (c.outcome === "open") {
      return el("div", "muted", "Still open -- no outcome yet.");
    }
    if (c.outcome === "ungraded") {
      return el("div", "muted",
        "Published without a target, so it is not graded and not counted.");
    }
    var moved = (c.outcome_price !== null && c.price_at_call)
      ? ((c.outcome_price - c.price_at_call) / c.price_at_call) * 100 : null;
    var line = el("div", "muted " + (c.outcome === "hit" ? "up" : "down"),
      (c.outcome === "hit" ? "Hit" : "Missed") +
      (c.outcome_price !== null ? " at " + money(c.outcome_price) : "") +
      (moved !== null ? " (" + pct(moved) + ")" : ""));
    return line;
  }

  function call(node, data) {
    node.innerHTML = "";
    if (data.error || !data.call) {
      var miss = card(null);
      miss.appendChild(el("div", "empty", "That call could not be found."));
      var back0 = el("button", "btn", "Back to calls");
      back0.addEventListener("click", data.onBack);
      miss.appendChild(back0);
      node.appendChild(miss);
      return;
    }
    var c = data.call;
    var head = card(null);
    head.appendChild(el("div", "label", stamp(c.published_at)));
    head.appendChild(el("div", "big", c.symbol));
    head.appendChild(el("span", "pill" + (c.side === "SELL" ? " sell" : ""),
                        c.side + (c.score ? " " + Math.round(c.score) : "")));
    head.appendChild(outcomeLine(c));
    node.appendChild(head);

    var why = card("Why it fired");
    why.appendChild(el("div", null, c.signal || "No reason recorded."));
    node.appendChild(why);

    var levels = card("Levels published with the call");
    var rows = [["Price at call", money(c.price_at_call)],
                ["Target", c.target === null ? "none published" : money(c.target)],
                ["Stop", c.stop === null ? "none published" : money(c.stop)],
                ["Horizon", c.horizon || "--"]];
    for (var i = 0; i < rows.length; i++) {
      var r = el("div", "row");
      r.appendChild(el("div", "grow muted", rows[i][0]));
      r.appendChild(el("div", null, rows[i][1]));
      levels.appendChild(r);
    }
    node.appendChild(levels);

    var back = el("button", "btn quiet", "Back to calls");
    back.addEventListener("click", data.onBack);
    node.appendChild(back);
  }

  window.TPScreens = {
    money: money, pct: pct, el: el, card: card,
    rateLine: rateLine, callRow: callRow,
    home: home,
    calls: calls, call: call, stamp: stamp
  };
})();
