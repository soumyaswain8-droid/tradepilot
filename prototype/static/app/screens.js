"use strict";

/* One render function per screen. Each takes a node and a payload and builds
   DOM -- no fetching, so a renderer can be driven from a console with a
   fixture. */

(function () {
  function money(n) {
    if (n === null || n === undefined) return "--";
    var neg = n < 0;
    var s = Math.round(Math.abs(n)).toString();
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

  /* A holding's live price can be missing even though the position itself
     exists -- the quote feed can be down while the book still has a cost
     basis (see shape_position in client_api.py, which marks each position
     price_unavailable rather than zero-filling it). Screens that list
     individual holdings must render through this, never through money()
     directly, so a missing quote never prints as a plain "0". */
  function priceOrUnavailable(v, unavailable) {
    if (unavailable) return el("span", "muted", "price unavailable");
    return el("span", null, money(v));
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
    rate.appendChild(rateLine(data.record));
    kpis.appendChild(rate);
    node.appendChild(kpis);

    var calls = card("Today's calls");
    if (!data.calls || !data.calls.calls.length) {
      calls.appendChild(el("div", "empty", "No calls published yet."));
    } else {
      for (var i = 0; i < Math.min(data.calls.calls.length, 5); i++) {
        calls.appendChild(callRow(data.calls.calls[i], data.onOpenCall));
      }
    }
    node.appendChild(calls);
  }

  window.TPScreens = {
    money: money, pct: pct, el: el, card: card,
    rateLine: rateLine, callRow: callRow, priceOrUnavailable: priceOrUnavailable,
    home: home
  };
})();
