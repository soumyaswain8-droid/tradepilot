### Task 2: The API client and the Home screen

**Files:**
- Create: `prototype/static/app/api.js`
- Create: `prototype/static/app/screens.js`
- Modify: `prototype/static/app/main.js` (wire `onShow`)
- Modify: `tests/test_app_screens.py`

**Interfaces:**
- Consumes: `window.TPApp.onShow`, mount point `view-home`.
- Produces:
  - `window.TPApi.calls(limit)` → promise of `{calls, limit, as_of}`
  - `window.TPApi.call(id)` → promise of one call, rejects on 404
  - `window.TPApi.record()` → promise of the record object
  - `window.TPApi.positions()` → promise of `{positions, totals}`, rejects with `{status: 401}` when signed out
  - `window.TPApi.addPosition(body)` / `window.TPApi.removePosition(id)`
  - `window.TPScreens.home(node, data)` where `data` is `{record, calls, book, signedOut}`
  - `window.TPScreens.money(n)` → `"₹12,48,300"`, and `window.TPScreens.pct(n)` → `"3.5%"`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app_screens.py`:

```python
def test_api_module_names_every_endpoint_it_needs(client):
    """A screen that calls a path the module never defines fails silently."""
    js = client.get("/static/app/api.js").get_data(as_text=True)
    for path in ("/api/app/calls", "/api/app/record", "/api/app/positions"):
        assert path in js, path


def test_api_module_is_the_only_place_fetch_appears(client):
    """Keeping fetch out of the renderers is what makes them inspectable."""
    screens = client.get("/static/app/screens.js").get_data(as_text=True)
    main = client.get("/static/app/main.js").get_data(as_text=True)
    assert "fetch(" not in screens
    assert "fetch(" not in main


def test_screens_module_handles_the_unavailable_price_flag(client):
    """A missing quote must never render as zero."""
    js = client.get("/static/app/screens.js").get_data(as_text=True)
    assert "price_unavailable" in js


def test_screens_module_never_prints_a_bare_hit_rate(client):
    """The spec forbids a rate without its sample size."""
    js = client.get("/static/app/screens.js").get_data(as_text=True)
    assert "resolved" in js
    assert "is_meaningful" in js
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_app_screens.py -q
```

Expected: failures — `/static/app/api.js` and `screens.js` 404.

- [ ] **Step 3: Write the API client**

Create `prototype/static/app/api.js`:

```javascript
"use strict";

/* The only place fetch appears. Every screen takes a payload and renders it,
   which keeps the rendering inspectable from a console with a fixture. */

(function () {
  function json(url, opts) {
    return fetch(url, opts || {}).then(function (r) {
      if (r.status === 401) return Promise.reject({ status: 401 });
      if (!r.ok) return Promise.reject({ status: r.status });
      return r.json();
    });
  }

  function post(url, body) {
    return json(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  }

  window.TPApi = {
    calls: function (limit) {
      return json("/api/app/calls?limit=" + (limit || 50));
    },
    call: function (id) {
      return json("/api/app/calls/" + encodeURIComponent(id));
    },
    record: function () {
      return json("/api/app/record");
    },
    positions: function () {
      return json("/api/app/positions");
    },
    addPosition: function (body) {
      return post("/api/app/positions", body);
    },
    removePosition: function (id) {
      return fetch("/api/app/positions/" + encodeURIComponent(id),
                   { method: "DELETE" }).then(function (r) {
        if (r.status === 401) return Promise.reject({ status: 401 });
        if (!r.ok && r.status !== 204) return Promise.reject({ status: r.status });
        return true;
      });
    }
  };
})();
```

- [ ] **Step 4: Write the screens module with Home**

Create `prototype/static/app/screens.js`:

```javascript
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
    rateLine: rateLine, callRow: callRow, home: home
  };
})();
```

- [ ] **Step 5: Wire Home into the router**

At the bottom of `prototype/static/app/main.js`, before the closing `})();`, replace `window.TPApp = { ... }` with the same object plus this loader, and set `onShow`:

```javascript
  function loadHome() {
    var node = el("view-home");
    if (!node) return;
    node.innerHTML = "<div class='empty'>Loading…</div>";
    Promise.all([
      window.TPApi.record(),
      window.TPApi.calls(5),
      window.TPApi.positions().then(
        function (b) { return { book: b, signedOut: false }; },
        function (e) { return { book: null, signedOut: e && e.status === 401 }; })
    ]).then(function (r) {
      window.TPScreens.home(node, {
        record: r[0], calls: r[1], book: r[2].book,
        signedOut: r[2].signedOut,
        onOpenCall: function (id) { window.TPApp.go("call", [id]); }
      });
    }, function () {
      node.innerHTML = "";
      node.appendChild(window.TPScreens.el(
        "div", "empty", "Could not load. Reload the page."));
    });
  }

  window.TPApp = {
    SECTIONS: SECTIONS, go: go, boot: boot,
    onShow: function (section) {
      if (section === "home") loadHome();
    }
  };
```

Note the positions promise is caught individually rather than letting a 401 reject the whole `Promise.all` — a signed-out visitor must still see the calls and the hit rate, because that is the entire acquisition surface.

- [ ] **Step 6: Run to verify they pass**

```bash
python3 -m pytest tests/test_app_screens.py -q
```

Expected: 12 passed.

- [ ] **Step 7: Confirm the whole suite passes, then commit**

```bash
python3 -m pytest tests/ -q
git add prototype/static/app/api.js prototype/static/app/screens.js prototype/static/app/main.js tests/test_app_screens.py
git commit -m "feat(app): the API client and the Home screen

Three states, not two: signed out, signed in with an empty book, and signed
in with holdings. A signed-out visitor still sees the calls and the hit rate
-- the positions promise is caught on its own rather than being allowed to
reject the whole batch, because that half is the acquisition surface.

The rate is never rendered alone. resolved, total and is_meaningful ship in
the same payload so the page cannot print a percentage without also printing
how few calls it stands on."
```

---

