"use strict";

/* One render function per screen. Each takes a node and a payload and builds
   DOM -- no fetching, so a renderer can be driven from a console with a
   fixture. Markup follows docs/design/2026-09-05-redesign/*.dc.html: a
   desktop table (.tbl) and a phone stack (.rows) are both rendered from the
   same list and CSS shows one of them per breakpoint -- the one component
   written twice, on purpose, so neither layout is an afterthought. */

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

  /* Prices carry paise; totals do not. Same grouping, two decimals. */
  function price(n) {
    if (n === null || n === undefined) return "--";
    var abs = Math.abs(n);
    var whole = Math.floor(abs);
    var paise = Math.round((abs - whole) * 100);
    if (paise === 100) { whole += 1; paise = 0; }
    var s = whole.toString();
    var last3 = s.slice(-3);
    var rest = s.slice(0, -3);
    if (rest) last3 = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + last3;
    var neg = n < 0 && (whole > 0 || paise > 0);
    return (neg ? "-₹" : "₹") + last3 + "." + (paise < 10 ? "0" : "") + paise;
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

  /* Appends a list of children and returns the parent, to keep the screen
     builders readable. */
  function add(parent, kids) {
    for (var i = 0; i < kids.length; i++) if (kids[i]) parent.appendChild(kids[i]);
    return parent;
  }

  function link(href, cls, text) {
    var a = el("a", cls, text);
    a.href = href;
    return a;
  }

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function stamp(iso) {
    if (!iso) return "";
    return iso.replace("T", " ").slice(0, 16);
  }

  /* "4 Sep" from an ISO date or datetime. Falls back to the raw string when
     the shape is not what we expect rather than inventing a date. */
  function day(iso) {
    if (!iso) return "";
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
    if (!m) return String(iso);
    return parseInt(m[3], 10) + " " + MONTHS[parseInt(m[2], 10) - 1];
  }

  /* "4 Sep 10:24" */
  function when(iso) {
    if (!iso) return "";
    var d = day(iso);
    var t = /T(\d{2}:\d{2})/.exec(iso);
    return t ? d + " " + t[1] : d;
  }

  function clock(iso) {
    var t = /T(\d{2}:\d{2})/.exec(iso || "");
    return t ? t[1] : "";
  }

  /* Home and Book both render this when their book fetch failed for a reason
     other than being signed out. One constant so the two screens cannot say
     it differently -- disagreeing wording here is exactly how a transient 500
     once read as "Nothing logged yet.", a positive claim about a holding that
     the failed request never actually disproved. */
  var BOOK_LOAD_FAILED_TEXT = "Could not load your book just now.";

  /* Record's "Resolved calls" card renders this when calls(50) failed. NOT
     unified with Home's "Could not load today's calls." -- that string names
     Home's own card (today's live/published calls, a different endpoint
     call, a different meaning) and would read as a category error sitting
     under a heading about resolved history. Kept as its own constant for the
     same reason BOOK_LOAD_FAILED_TEXT exists: one string, so this card and
     any future caller cannot drift into saying it two ways. */
  var CALLS_LOAD_FAILED_TEXT = "Could not load the resolved calls list just now.";

  /* ---- Chips ---------------------------------------------------------- */

  function sideChip(c, lg) {
    var sell = c.side === "SELL";
    return el("span", "chip " + (sell ? "sell" : "buy") + (lg ? " lg" : ""),
              sell ? "SELL" : "BUY");
  }

  /* The outcome chip. outcome.js is the single source of truth for what an
     outcome means; this only picks the colour. Anything it does not
     recognise is "not recorded", never a loss. */
  function outcomeChip(c, lg) {
    var o = c && c.outcome;
    var cls, text;
    if (o === "open") { cls = "open"; text = "OPEN"; }
    else if (o === "hit") { cls = "hit"; text = "HIT"; }
    else if (o === "miss") { cls = "miss"; text = "MISS"; }
    else if (o === "ungraded") { cls = "ung"; text = "UNGRADED"; }
    else { cls = "ung"; text = "NOT RECORDED"; }
    return el("span", "chip " + cls + (lg ? " lg" : ""), text);
  }

  /* ---- Hit rate ------------------------------------------------------- */

  function progress(n, of, lg) {
    var wrap = el("div", "progress" + (lg ? " lg" : ""));
    var fill = el("div", "fill");
    var w = of > 0 ? Math.max(0, Math.min(100, (n / of) * 100)) : 0;
    fill.style.width = w + "%";
    wrap.appendChild(fill);
    return wrap;
  }

  /* The rate is never shown alone. resolved and is_meaningful ship in the same
     payload precisely so a page cannot honestly print 62% without also
     printing that it is eleven calls. With nothing resolved there is no rate
     at all: the screen says "Not yet" and shows how far along the sample is,
     never a dash that could be read as zero. */
  function rateLine(rec, lg) {
    var wrap = el("div", "card-body col");
    wrap.style.display = "flex";
    wrap.style.flexDirection = "column";
    wrap.style.gap = "8px";
    var from = rec.meaningful_from || 0;

    if (rec.hit_rate === null || rec.hit_rate === undefined) {
      wrap.appendChild(el("div", "notyet" + (lg ? " lg" : ""), "Not yet"));
      var line = el("div", "muted");
      line.appendChild(el("span", "num strong", rec.resolved || 0));
      line.appendChild(document.createTextNode(
        (rec.resolved === 1 ? " call resolved" : " calls resolved") +
        (rec.since ? " · recording since " + day(rec.since) : "") +
        ". We publish a hit rate from "));
      line.appendChild(el("span", "num strong", from));
      line.appendChild(document.createTextNode(
        lg ? " resolved calls, because a percentage over a handful of trades " +
             "is the easiest number in finance to fool yourself with."
           : "."));
      wrap.appendChild(line);
      wrap.appendChild(progress(rec.resolved || 0, from, lg));
      var foot = el("div", "progress-foot mut num");
      foot.appendChild(el("span", null, (rec.resolved || 0) + " resolved"));
      foot.appendChild(el("span", null, from));
      wrap.appendChild(foot);
      return wrap;
    }

    wrap.appendChild(el("div", "big " + (rec.hit_rate >= 50 ? "up" : "down"),
                        rec.hit_rate.toFixed(1) + "%"));
    wrap.appendChild(el("div", "muted",
      rec.resolved + " resolved of " + rec.total + " recorded"));
    if (!rec.is_meaningful) {
      wrap.appendChild(el("div", "thin",
        "Too few to be meaningful -- we show a rate from " + from + "."));
      wrap.appendChild(progress(rec.resolved, from, lg));
      var foot2 = el("div", "progress-foot mut num");
      foot2.appendChild(el("span", null, rec.resolved + " resolved"));
      foot2.appendChild(el("span", null, from));
      wrap.appendChild(foot2);
    }
    return wrap;
  }

  /* ---- Calls: table + rows -------------------------------------------- */

  function th(text, right) {
    return el("th", right ? "r" : null, text);
  }

  function td(cls, text) {
    return el("td", cls, text);
  }

  /* Desktop table of calls: Stock · Why · Score · Price at call · Outcome. */
  function callTable(list, onOpen) {
    var t = el("table", "tbl");
    var head = el("thead");
    add(head, [add(el("tr"), [th("Stock"), th("Why"), th("Score", true),
                              th("Price at call", true), th("Outcome", true)])]);
    t.appendChild(head);
    var body = el("tbody");
    for (var i = 0; i < list.length; i++) {
      var c = list[i];
      var tr = el("tr", onOpen ? "click" : null);
      var stock = td(null);
      stock.style.width = "170px";
      stock.appendChild(el("span", "sym", c.symbol));
      stock.appendChild(document.createTextNode(" "));
      stock.appendChild(sideChip(c));
      stock.appendChild(el("div", "num mut stamp", clock(c.published_at)));
      tr.appendChild(stock);
      tr.appendChild(td("why", c.signal || "No reason recorded."));
      var score = td("r num", c.score ? Math.round(c.score) : "--");
      score.style.width = "70px";
      tr.appendChild(score);
      var px = td("r num", price(c.price_at_call));
      px.style.width = "120px";
      tr.appendChild(px);
      var oc = td("r");
      oc.style.width = "110px";
      oc.appendChild(outcomeChip(c));
      tr.appendChild(oc);
      if (onOpen) tr.addEventListener("click", opener(onOpen, c.id));
      body.appendChild(tr);
    }
    t.appendChild(body);
    return t;
  }

  function opener(onOpen, id) {
    return function () { onOpen(id); };
  }

  /* Phone row for one call -- the same data as one table row. */
  function callRow(c, onOpen) {
    var row = el("div", "row" + (onOpen ? " click" : ""));
    var grow = el("div", "grow");
    var top = el("div", "top");
    top.appendChild(el("span", "sym", c.symbol));
    top.appendChild(sideChip(c));
    top.appendChild(el("span", "num", price(c.price_at_call)));
    grow.appendChild(top);
    grow.appendChild(el("div", "why", c.signal || "No reason recorded."));
    row.appendChild(grow);
    row.appendChild(outcomeChip(c));
    if (onOpen) row.addEventListener("click", opener(onOpen, c.id));
    return row;
  }

  function callRows(list, onOpen) {
    var wrap = el("div", "rows");
    for (var i = 0; i < list.length; i++) wrap.appendChild(callRow(list[i], onOpen));
    return wrap;
  }

  /* Both renderings of a call list, side by side; CSS shows one. */
  function callList(list, onOpen) {
    var frag = document.createDocumentFragment();
    frag.appendChild(callTable(list, onOpen));
    frag.appendChild(callRows(list, onOpen));
    return frag;
  }

  /* ---- Home ----------------------------------------------------------- */

  function home(node, data) {
    node.innerHTML = "";

    var grid = el("div", "grid2");

    var book = el("div", "card col");
    book.appendChild(el("div", "label", "Your book"));
    if (data.signedOut) {
      book.appendChild(el("div", "notyet", "Signed out"));
      book.appendChild(el("div", "muted", "Sign in to see your book"));
      var inA = el("div", "actions");
      inA.appendChild(link("/app/login", "btn sm", "Sign in"));
      book.appendChild(inA);
    } else if (data.bookFailed) {
      book.appendChild(el("div", "notyet", "--"));
      book.appendChild(el("div", "muted", BOOK_LOAD_FAILED_TEXT));
    } else if (!data.book || !data.book.positions.length) {
      book.appendChild(el("div", "notyet", "Empty"));
      book.appendChild(el("div", "muted", "Log your first trade to see it here"));
      var a0 = el("div", "actions");
      a0.appendChild(link("#book", "btn sm", "Add a trade"));
      book.appendChild(a0);
    } else if (!data.book.totals.priced) {
      /* Holdings exist but none could be priced. Showing ₹0 here would state
         the book is worthless; it only means we could not value it. */
      book.appendChild(el("div", "notyet", "--"));
      book.appendChild(el("div", "muted", "No live prices right now."));
      book.appendChild(el("div", "thin", data.book.positions.length +
        " holding(s) have no live price"));
      var a1 = el("div", "actions");
      a1.appendChild(link("#book", "btn sm", "Add a trade"));
      a1.appendChild(link("#book", "btn ghost sm", "Open book"));
      book.appendChild(a1);
    } else {
      var t = data.book.totals;
      book.appendChild(el("div", "big", money(t.value)));
      var line = el("div", "line");
      line.appendChild(el("span", "num " + (t.pnl >= 0 ? "up" : "down"),
                          money(t.pnl)));
      line.appendChild(el("span", "mut", "overall"));
      if (t.unpriced) {
        line.appendChild(el("span", "mut", "·"));
        line.appendChild(el("span", "mut", t.unpriced + " price unavailable"));
      }
      book.appendChild(line);
      var a2 = el("div", "actions");
      a2.appendChild(link("#book", "btn sm", "Add a trade"));
      a2.appendChild(link("#book", "btn ghost sm", "Open book"));
      book.appendChild(a2);
    }
    grid.appendChild(book);

    var rate = el("div", "card col");
    rate.appendChild(el("div", "label", "Track record"));
    if (data.record) {
      rate.appendChild(rateLine(data.record, false));
    } else {
      rate.appendChild(el("div", "notyet", "--"));
      rate.appendChild(el("div", "muted", "Could not load the record."));
    }
    grid.appendChild(rate);
    node.appendChild(grid);

    var calls = el("div", "card flush");
    var head = el("div", "card-head");
    head.appendChild(el("h2", null, "Today's calls"));
    if (data.calls && data.calls.calls.length) {
      head.appendChild(el("span", "mut sub",
        data.calls.calls.length + " published · as of " + stamp(data.calls.as_of)));
    }
    head.appendChild(link("#calls", "more", "See all"));
    calls.appendChild(head);
    if (!data.calls) {
      calls.appendChild(el("div", "empty", "Could not load today's calls."));
    } else if (!data.calls.calls.length) {
      calls.appendChild(el("div", "empty", "No calls published yet."));
    } else {
      calls.appendChild(callList(data.calls.calls.slice(0, 5), data.onOpenCall));
    }
    node.appendChild(calls);
  }

  /* ---- Calls ---------------------------------------------------------- */

  var FILTERS = [
    { id: "all", label: "All" }, { id: "open", label: "Open" },
    { id: "hit", label: "Hit" }, { id: "miss", label: "Miss" },
    { id: "ungraded", label: "Ungraded" }
  ];

  function countBy(list, outcome) {
    var n = 0;
    for (var i = 0; i < list.length; i++) if (list[i].outcome === outcome) n++;
    return n;
  }

  function calls(node, data) {
    node.innerHTML = "";
    var list = (data.calls && data.calls.calls) || [];
    var filter = "all";

    var head = el("div", "pagehead");
    var titles = el("div", "grow");
    titles.appendChild(el("h1", "h1", "Calls"));
    titles.appendChild(el("div", "sub", list.length
      ? list.length + " published · as of " + stamp(data.calls.as_of)
      : "Nothing published yet"));
    head.appendChild(titles);
    var chips = el("div", "fchips");
    head.appendChild(chips);
    node.appendChild(head);

    var c = el("div", "card flush");
    node.appendChild(c);

    function draw() {
      chips.innerHTML = "";
      for (var i = 0; i < FILTERS.length; i++) {
        var f = FILTERS[i];
        var n = f.id === "all" ? list.length : countBy(list, f.id);
        var b = el("button", "fchip" + (filter === f.id ? " on" : ""),
                   f.label + " " + n);
        b.type = "button";
        b.addEventListener("click", pick(f.id));
        chips.appendChild(b);
      }
      c.innerHTML = "";
      var shown = [];
      for (var j = 0; j < list.length; j++) {
        if (filter === "all" || list[j].outcome === filter) shown.push(list[j]);
      }
      if (!list.length) {
        c.appendChild(el("div", "empty", "No calls published yet."));
      } else if (!shown.length) {
        c.appendChild(el("div", "empty", "No " + filter + " calls in this list."));
      } else {
        c.appendChild(callList(shown, data.onOpenCall));
      }
    }
    function pick(id) {
      return function () { filter = id; draw(); };
    }
    draw();

    if (list.length) {
      /* Outside market hours this list is the last session's. Saying so is
         cheaper than a support question about why it has not moved. */
      var note = el("div", "card tint note");
      note.appendChild(infoIcon());
      note.appendChild(el("div", "thin",
        "A call is a published idea with a target and a stop. It becomes HIT " +
        "or MISS only when price reaches one of them. Nothing here is a " +
        "recommendation to buy or sell. As of " + stamp(data.calls.as_of) + "."));
      node.appendChild(note);
    }
  }

  var SVG_NS = "http://www.w3.org/2000/svg";
  function infoIcon() {
    var svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("class", "ic");
    svg.setAttribute("viewBox", "0 0 24 24");
    var circle = document.createElementNS(SVG_NS, "circle");
    circle.setAttribute("cx", "12"); circle.setAttribute("cy", "12");
    circle.setAttribute("r", "9");
    var path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", "M12 8v5M12 16h.01");
    svg.appendChild(circle); svg.appendChild(path);
    return svg;
  }

  /* ---- Call detail ---------------------------------------------------- */

  function outcomeLine(c) {
    var text = window.TPOutcome.outcomeText(c);
    var kind = window.TPOutcome.outcomeKind(c);
    if (!kind) return el("span", "mut", text);
    var moved = (c.outcome_price !== null && c.outcome_price !== undefined && c.price_at_call)
      ? ((c.outcome_price - c.price_at_call) / c.price_at_call) * 100 : null;
    return el("span", "num " + kind,
      text + (c.outcome_price !== null && c.outcome_price !== undefined
                ? " at " + price(c.outcome_price) : "") +
      (moved !== null ? " · " + pct(moved) : ""));
  }

  function levelTile(label, value, entry, dir) {
    var tile = el("div", "card tint kpi");
    tile.appendChild(el("div", "label", label));
    if (value === null || value === undefined) {
      tile.appendChild(el("div", "mut", "none published"));
      return tile;
    }
    var v = el("div", "num big sm" + (dir ? " " + dir : ""));
    v.appendChild(document.createTextNode(price(value)));
    if (entry && dir) {
      var d = el("span", null, " " + pct(((value - entry) / entry) * 100));
      d.style.fontSize = "12px";
      v.appendChild(d);
    }
    tile.appendChild(v);
    return tile;
  }

  function call(node, data) {
    node.innerHTML = "";
    var backLink = el("a", "back", "← All calls");
    backLink.href = "#calls";
    backLink.addEventListener("click", function (e) {
      e.preventDefault(); data.onBack();
    });
    node.appendChild(backLink);

    if (data.error || !data.call) {
      var miss = card(null);
      miss.appendChild(el("div", "empty", "That call could not be found."));
      node.appendChild(miss);
      return;
    }
    var c = data.call;
    var grid = el("div", "grid2 wide");
    var left = el("div", "stack");
    var right = el("div", "stack");

    var head = el("div", "card col");
    head.style.gap = "14px";
    var hl = el("div", "headline");
    hl.appendChild(el("h1", "h1", c.symbol));
    hl.appendChild(sideChip(c, true));
    hl.appendChild(outcomeChip(c, true));
    hl.appendChild(el("span", "when num", "Published " + when(c.published_at)));
    head.appendChild(hl);
    var base = el("div", "baseline");
    base.appendChild(el("span", "big md", price(c.price_at_call)));
    base.appendChild(el("span", "mut", "price at call"));
    base.appendChild(outcomeLine(c));
    head.appendChild(base);
    var tiles = el("div", "grid3");
    /* Green means the win, red means the loss -- for a SELL the target sits
       below entry and is still the win, so the colour follows the role of
       the level, not its direction. */
    tiles.appendChild(levelTile("Entry", c.price_at_call, null, null));
    tiles.appendChild(levelTile("Target", c.target, c.price_at_call, "up"));
    tiles.appendChild(levelTile("Stop", c.stop, c.price_at_call, "down"));
    head.appendChild(tiles);
    left.appendChild(head);

    var why = el("div", "card col");
    why.style.gap = "10px";
    why.appendChild(el("h2", null, "Why this call"));
    var p = el("p", "body", c.signal || "No reason recorded.");
    p.style.margin = "0";
    why.appendChild(p);
    if (c.score) {
      var s = el("div", "mut");
      s.appendChild(document.createTextNode("Score "));
      s.appendChild(el("span", "num strong", Math.round(c.score)));
      s.appendChild(document.createTextNode(
        " out of 100 — the higher the score, the more of our checks lined up."));
      why.appendChild(s);
    }
    left.appendChild(why);

    var tl = el("div", "card col");
    tl.style.gap = "12px";
    tl.appendChild(el("div", "label", "Timeline"));
    var pub = el("div", "kv");
    pub.appendChild(el("span", "pip on"));
    var pubText = el("div");
    pubText.appendChild(el("div", "k", "Published"));
    pubText.appendChild(el("div", "v num",
      when(c.published_at) + " · " + price(c.price_at_call)));
    pub.appendChild(pubText);
    tl.appendChild(pub);
    var out = el("div", "kv");
    var resolved = c.outcome === "hit" || c.outcome === "miss";
    out.appendChild(el("span", "pip" + (resolved ? " on" : "")));
    var outText = el("div");
    outText.appendChild(el("div", "k" + (resolved ? "" : " mut"), "Outcome"));
    if (resolved) {
      outText.appendChild(el("div", "v num",
        window.TPOutcome.outcomeText(c) +
        (c.outcome_at ? " · " + when(c.outcome_at) : "") +
        (c.outcome_price !== null && c.outcome_price !== undefined
          ? " · " + price(c.outcome_price) : "")));
    } else {
      outText.appendChild(el("div", "v", window.TPOutcome.outcomeText(c)));
    }
    out.appendChild(outText);
    tl.appendChild(out);
    if (c.horizon) {
      tl.appendChild(el("div", "thin", "Horizon: " + c.horizon));
    }
    right.appendChild(tl);

    right.appendChild(link("#book", "btn ghost", "Add to my book"));

    grid.appendChild(left);
    grid.appendChild(right);
    node.appendChild(grid);
  }

  /* ---- Record --------------------------------------------------------- */

  function barRow(label, n, total, cls) {
    var row = el("div", "bar-row");
    row.appendChild(el("span", "k", label));
    var track = el("div", "track");
    var fill = el("div", "fill " + cls);
    fill.style.width = (total > 0 ? Math.round((n / total) * 100) : 0) + "%";
    track.appendChild(fill);
    row.appendChild(track);
    row.appendChild(el("span", "n num", n));
    return row;
  }

  function resolvedTable(list) {
    var t = el("table", "tbl");
    var head = el("thead");
    add(head, [add(el("tr"), [th("Stock"), th("Published"), th("Price at call", true),
                              th("Target", true), th("Stop", true),
                              th("Resolved at", true), th("Outcome", true)])]);
    t.appendChild(head);
    var body = el("tbody");
    for (var i = 0; i < list.length; i++) {
      var c = list[i];
      var tr = el("tr");
      var stock = td(null);
      stock.appendChild(el("span", "sym", c.symbol));
      stock.appendChild(document.createTextNode(" "));
      stock.appendChild(sideChip(c));
      tr.appendChild(stock);
      tr.appendChild(td("mut num", when(c.published_at)));
      tr.appendChild(td("r num", price(c.price_at_call)));
      tr.appendChild(td("r num", c.target === null ? "—" : price(c.target)));
      tr.appendChild(td("r num", c.stop === null ? "—" : price(c.stop)));
      tr.appendChild(td("r num",
        (c.outcome_price === null || c.outcome_price === undefined ? "—" : price(c.outcome_price)) +
        (c.outcome_at ? " · " + clock(c.outcome_at) : "")));
      var oc = td("r");
      oc.appendChild(outcomeChip(c));
      tr.appendChild(oc);
      body.appendChild(tr);
    }
    t.appendChild(body);
    return t;
  }

  function resolvedRows(list) {
    var wrap = el("div", "rows");
    for (var i = 0; i < list.length; i++) {
      var c = list[i];
      var row = el("div", "row");
      var grow = el("div", "grow");
      var top = el("div", "top");
      top.appendChild(el("span", "sym", c.symbol));
      top.appendChild(sideChip(c));
      top.appendChild(el("span", "num", price(c.price_at_call)));
      grow.appendChild(top);
      grow.appendChild(el("div", "why", when(c.published_at) +
        (c.outcome_price !== null && c.outcome_price !== undefined
          ? " → " + price(c.outcome_price) : "")));
      row.appendChild(grow);
      row.appendChild(outcomeChip(c));
      wrap.appendChild(row);
    }
    return wrap;
  }

  function record(node, data) {
    node.innerHTML = "";
    var rec = data.record;

    var head = el("div", "pagehead");
    var titles = el("div", "grow");
    titles.appendChild(el("h1", "h1", "Track record"));
    titles.appendChild(el("div", "sub",
      "Every call we publish is graded against its own target and stop. " +
      "Nothing is removed."));
    head.appendChild(titles);
    node.appendChild(head);

    var grid = el("div", "grid2 even");

    var rate = el("div", "card col");
    rate.style.gap = "10px";
    rate.appendChild(el("div", "label", "Hit rate"));
    rate.appendChild(rateLine(rec, true));
    /* "since" is the first call RECORDED, not the first resolved. Labelling it
       "recording since" keeps the page from implying the rate has been earned
       across that whole span. */
    rate.appendChild(el("div", "thin", rec.since
      ? "Recording since " + day(rec.since)
      : "Nothing recorded yet."));
    grid.appendChild(rate);

    var split = el("div", "card col");
    split.style.gap = "14px";
    var lbl = el("div", "label");
    lbl.appendChild(document.createTextNode("All calls so far · "));
    lbl.appendChild(el("span", "num", rec.total));
    split.appendChild(lbl);
    var bars = el("div", "bars");
    bars.appendChild(barRow("Hit", rec.hit, rec.total, "hit"));
    bars.appendChild(barRow("Miss", rec.miss, rec.total, "miss"));
    bars.appendChild(barRow("Ungraded", rec.ungraded, rec.total, "ung"));
    bars.appendChild(barRow("Open", rec.open, rec.total, "open"));
    var counted = rec.hit + rec.miss + rec.open + rec.ungraded;
    if (counted !== rec.total) {
      /* Stays invisible unless the sums disagree. If they ever do, the screen
         says so rather than quietly showing four numbers that do not add up
         to the total printed above them. */
      bars.appendChild(barRow("Not accounted for", rec.total - counted, rec.total, "ung"));
    }
    split.appendChild(bars);
    split.appendChild(el("div", "thin",
      "Ungraded calls are excluded from the rate -- a call published without " +
      "a target has no standard to be graded against."));
    grid.appendChild(split);
    node.appendChild(grid);

    /* outcomeKind is the single source of truth for hit/miss colouring --
       reusing it here keeps this list from drifting from outcomeLine's. */
    var list = (data.calls && data.calls.calls) || [];
    var resolved = [];
    for (var j = 0; j < list.length; j++) {
      var k0 = window.TPOutcome.outcomeKind(list[j]);
      if (k0 === "up" || k0 === "down") resolved.push(list[j]);
    }
    var graded = rec.hit + rec.miss;
    var recent = el("div", "card flush");
    var rh = el("div", "card-head");
    rh.appendChild(el("h2", "sm", "Resolved calls"));
    rh.appendChild(el("span", "mut sub", "newest first"));
    recent.appendChild(rh);
    if (data.callsFailed) {
      /* The tally above (rec.hit / rec.miss) already loaded successfully --
         this card must not claim "Nothing has resolved yet." underneath it
         just because ITS fetch failed. That claim would contradict the tally
         a few pixels above it. */
      recent.appendChild(el("div", "empty", CALLS_LOAD_FAILED_TEXT));
    } else if (!resolved.length) {
      recent.appendChild(el("div", "empty", "Nothing has resolved yet."));
    } else {
      recent.appendChild(resolvedTable(resolved));
      recent.appendChild(resolvedRows(resolved));
      /* The tally above counts every call ever recorded; this list is drawn
         from the most recent fifty. Saying which is which costs one line and
         stops the heading implying completeness it does not have. */
      var foot = el("div", "thin", resolved.length < graded
        ? "Showing the " + resolved.length + " most recent of " + graded +
          " resolved calls."
        : "All " + graded + " resolved calls.");
      foot.style.padding = "10px 0 12px";
      recent.appendChild(foot);
    }
    node.appendChild(recent);
  }

  /* ---- Book ----------------------------------------------------------- */

  function removeButton(p, onRemove) {
    var rm = el("button", "rm", "Remove");
    rm.type = "button";
    rm.addEventListener("click", function (e) {
      e.stopPropagation();
      onRemove(p.id, p.symbol);
    });
    return rm;
  }

  function pnlCell(p) {
    var cell = el("span", "num " + (p.pnl >= 0 ? "up" : "down"));
    cell.style.fontWeight = "700";
    cell.appendChild(document.createTextNode(money(p.pnl) + " "));
    var pc = el("span", "mut", pct(p.pnl_pct));
    pc.style.fontWeight = "400";
    cell.appendChild(pc);
    return cell;
  }

  function positionTable(list, onRemove, withHead) {
    var t = el("table", "tbl");
    if (withHead) {
      var head = el("thead");
      add(head, [add(el("tr"), [th("Stock"), th("Since"), th("Qty", true), th("Avg", true),
                                th("Last", true), th("P&L", true), th("", true)])]);
      t.appendChild(head);
    }
    var body = el("tbody");
    for (var i = 0; i < list.length; i++) {
      var p = list[i];
      var tr = el("tr");
      var sym = td("sym", p.symbol);
      sym.style.width = "170px";
      tr.appendChild(sym);
      tr.appendChild(td("mut", day(p.opened_at)));
      tr.appendChild(td("r num", p.qty));
      tr.appendChild(td("r num", price(p.avg_price)));
      if (p.price_unavailable) {
        /* Never zero. A silent numeric fallback renders a real holding as
           worthless -- say so instead. */
        tr.appendChild(td("r mut", "price unavailable"));
        tr.appendChild(td("r mut", "—"));
      } else {
        tr.appendChild(td("r num", price(p.last_price)));
        var pl = td("r");
        pl.appendChild(pnlCell(p));
        tr.appendChild(pl);
      }
      var act = td("r");
      act.appendChild(removeButton(p, onRemove));
      tr.appendChild(act);
      body.appendChild(tr);
    }
    t.appendChild(body);
    return t;
  }

  /* Phone row for one position -- the same data as one table row. */
  function positionRow(p, onRemove) {
    var row = el("div", "row");
    var grow = el("div", "grow");
    var top = el("div", "top");
    top.appendChild(el("span", "sym", p.symbol));
    if (p.price_unavailable) {
      /* Never zero. A silent numeric fallback renders a real holding as
         worthless -- show the cost basis instead. */
      top.appendChild(el("span", "num mut", "price unavailable"));
      grow.appendChild(top);
      grow.appendChild(el("div", "why",
        p.qty + " @ " + price(p.avg_price) + " · since " + day(p.opened_at)));
    } else {
      top.appendChild(el("span", "num", money(p.value)));
      grow.appendChild(top);
      grow.appendChild(el("div", "why " + (p.pnl >= 0 ? "up" : "down"),
        money(p.pnl) + " (" + pct(p.pnl_pct) + ") · " + p.qty + " @ " +
        price(p.avg_price)));
    }
    row.appendChild(grow);
    row.appendChild(removeButton(p, onRemove));
    return row;
  }

  function positionRows(list, onRemove) {
    var wrap = el("div", "rows");
    for (var i = 0; i < list.length; i++) wrap.appendChild(positionRow(list[i], onRemove));
    return wrap;
  }

  /* A titled section of the positions card: a heading with its count, then
     the table and the phone rows, or a one-line empty state. */
  function positionSection(title, list, onRemove, withHead, emptyText) {
    var frag = document.createDocumentFragment();
    var head = el("div", "card-head");
    head.appendChild(el("h2", "sm", title));
    head.appendChild(el("span", "mut sub",
      list.length + (list.length === 1 ? " position" : " positions")));
    frag.appendChild(head);
    if (!list.length) {
      var e = el("div", "thin", emptyText);
      e.style.padding = "4px 0 12px";
      frag.appendChild(e);
    } else {
      frag.appendChild(positionTable(list, onRemove, withHead));
      frag.appendChild(positionRows(list, onRemove));
    }
    return frag;
  }

  /* No Close action here on purpose. Marking a position shut would hide it
     from /api/app/positions -- the only endpoint that can discover its id --
     so closing is unrecoverable through the API, and no closed-positions
     view exists to reach it afterward. Add and Remove only until that
     view exists. */
  function book(node, data) {
    node.innerHTML = "";
    if (data.signedOut) {
      var gate = card(null);
      gate.appendChild(el("div", "empty", "Sign in to see your book."));
      var ga = el("div", "actions");
      ga.style.justifyContent = "center";
      ga.appendChild(link("/app/login", "btn sm", "Sign in"));
      gate.appendChild(ga);
      node.appendChild(gate);
      return;
    }
    /* Same shape as Home's book-load failure, and the same words (see
       BOOK_LOAD_FAILED_TEXT). Returning here, before Positions or the Add
       form exist, means a failed fetch can never render a form whose
       onAdd was never wired -- there is nothing to add to anyway. */
    if (data.failed) {
      var fail = card(null);
      fail.appendChild(el("div", "empty", BOOK_LOAD_FAILED_TEXT));
      node.appendChild(fail);
      return;
    }

    var list = (data.book && data.book.positions) || [];
    var totals = (data.book && data.book.totals) || {};
    var anyPriced = totals.priced > 0;

    var head = el("div", "pagehead");
    var titles = el("div", "grow");
    titles.appendChild(el("h1", "h1", "Your book"));
    titles.appendChild(el("div", "sub", list.length
      ? list.length + (list.length === 1 ? " position" : " positions") +
        (anyPriced ? " · marked to the last available price" : "")
      : "Nothing logged yet"));
    head.appendChild(titles);
    node.appendChild(head);

    var grid = el("div", "grid2 wide");
    var left = el("div", "stack");

    /* Gate on whether anything is PRICED, not on whether positions exist.
       totals.value is a sum over the priced set, so an entirely unpriced book
       yields 0 -- and a large green ₹0 above rows that each say "price
       unavailable" contradicts every one of them. */
    var kpis = el("div", "grid3");
    var kv = el("div", "card kpi");
    kv.appendChild(el("div", "label", "Value"));
    kv.appendChild(el("div", anyPriced ? "big sm" : "notyet", anyPriced ? money(totals.value) : "--"));
    if (list.length && !anyPriced) kv.appendChild(el("div", "thin", "No live prices right now."));
    kpis.appendChild(kv);
    var kp = el("div", "card kpi");
    kp.appendChild(el("div", "label", "Overall"));
    kp.appendChild(el("div", anyPriced ? "big sm " + (totals.pnl >= 0 ? "up" : "down") : "notyet",
                      anyPriced ? money(totals.pnl) : "--"));
    kpis.appendChild(kp);
    var kn = el("div", "card kpi");
    kn.appendChild(el("div", "label", "Priced"));
    var pn = el("div", "big sm");
    pn.appendChild(document.createTextNode(String(totals.priced || 0) + " "));
    var of = el("span", "mut", "of " + list.length);
    of.style.fontSize = "13px"; of.style.fontWeight = "600";
    pn.appendChild(of);
    kn.appendChild(pn);
    if (totals.unpriced) {
      kn.appendChild(el("div", "thin", totals.unpriced +
        " holding(s) have no live price and are not included in the total"));
    }
    kpis.appendChild(kn);
    left.appendChild(kpis);

    var c = el("div", "card flush");
    if (!list.length) {
      c.appendChild(el("div", "empty", "Nothing logged yet."));
    } else {
      /* Split by provenance: a position that carries a call_id came from a
         published call; anything else the client logged on their own. */
      var fromCalls = [], own = [];
      for (var i = 0; i < list.length; i++) {
        if (list[i].call_id) fromCalls.push(list[i]); else own.push(list[i]);
      }
      c.appendChild(positionSection("From calls", fromCalls, data.onRemove, true,
        "Nothing from a call yet."));
      c.appendChild(positionSection("Logged by you", own, data.onRemove, !fromCalls.length,
        "Nothing of your own yet."));
    }
    left.appendChild(c);
    grid.appendChild(left);

    /* The Book screen IS the add-a-trade form: it sits beside the list on
       desktop and below it on phone. */
    var form = el("div", "card sticky form");
    form.appendChild(el("h2", null, "Add a trade"));
    form.appendChild(el("div", "thin",
      "Log something you bought on your own, outside a call. It joins your " +
      "book at the price you paid."));
    var fSym = el("div", "field");
    fSym.appendChild(el("span", "label", "Stock"));
    var sym = el("input", "input"); sym.placeholder = "NSE symbol, e.g. CIPLA";
    sym.autocomplete = "off";
    fSym.appendChild(sym);
    form.appendChild(fSym);
    var pair = el("div", "pair");
    var fQty = el("div", "field");
    fQty.appendChild(el("span", "label", "Quantity"));
    var qty = el("input", "input num"); qty.placeholder = "0"; qty.type = "number";
    qty.min = "1"; qty.step = "1"; qty.inputMode = "numeric";
    fQty.appendChild(qty);
    var fPx = el("div", "field");
    fPx.appendChild(el("span", "label", "Price paid"));
    var px = el("input", "input num"); px.placeholder = "₹0.00"; px.type = "number";
    px.min = "0"; px.step = "0.01"; px.inputMode = "decimal";
    fPx.appendChild(px);
    pair.appendChild(fQty); pair.appendChild(fPx);
    form.appendChild(pair);
    var addBtn = el("button", "btn", "Add to book");
    addBtn.type = "button";
    var err = el("div", "err");
    addBtn.addEventListener("click", function () {
      err.textContent = "";
      data.onAdd({ symbol: sym.value.trim().toUpperCase(), qty: Number(qty.value),
                   avg_price: Number(px.value) }, function (message) {
        err.textContent = message;
      });
    });
    form.appendChild(addBtn);
    form.appendChild(err);
    form.appendChild(el("div", "thin",
      "No orders are placed. Your book is a record, not a broker."));
    grid.appendChild(form);
    node.appendChild(grid);
  }

  window.TPScreens = {
    money: money, price: price, pct: pct, el: el, card: card,
    rateLine: rateLine, callRow: callRow, callTable: callTable,
    sideChip: sideChip, outcomeChip: outcomeChip,
    home: home,
    calls: calls, call: call, stamp: stamp, day: day, when: when,
    record: record,
    book: book, positionRow: positionRow, positionTable: positionTable
  };
})();
