### Task 3: Calls and call detail

**Files:**
- Modify: `prototype/static/app/screens.js`
- Modify: `prototype/static/app/main.js`
- Modify: `tests/test_app_screens.py`

**Interfaces:**
- Consumes: `TPScreens.callRow`, `TPScreens.card`, `TPApi.calls`, `TPApi.call`.
- Produces:
  - `window.TPScreens.calls(node, data)` where `data` is `{calls, onOpenCall}`
  - `window.TPScreens.call(node, data)` where `data` is `{call, onBack}` or `{error: true}`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app_screens.py`:

```python
def test_calls_screen_stamps_the_data_it_is_showing(client):
    """Outside market hours the list is stale; the page must say when."""
    js = client.get("/static/app/screens.js").get_data(as_text=True)
    assert "as_of" in js


def test_call_detail_distinguishes_open_from_resolved(client):
    """A live call must not imply an outcome that has not happened."""
    js = client.get("/static/app/screens.js").get_data(as_text=True)
    for token in ("outcome", "hit", "miss", "ungraded"):
        assert token in js, token
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_app_screens.py -q
```

Expected: 2 failures — `as_of` and the outcome tokens are absent.

- [ ] **Step 3: Add both renderers**

In `prototype/static/app/screens.js`, add before the `window.TPScreens = {...}` assignment:

```javascript
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
```

Then add `calls: calls, call: call, stamp: stamp` to the `window.TPScreens` object.

- [ ] **Step 4: Wire both screens**

In `prototype/static/app/main.js`, add these loaders beside `loadHome`, and extend `onShow`:

```javascript
  function loadCalls() {
    var node = el("view-calls");
    if (!node) return;
    node.innerHTML = "<div class='empty'>Loading…</div>";
    window.TPApi.calls(50).then(function (c) {
      window.TPScreens.calls(node, {
        calls: c,
        onOpenCall: function (id) { window.TPApp.go("call", [id]); }
      });
    }, function () {
      node.innerHTML = "";
      node.appendChild(window.TPScreens.el(
        "div", "empty", "Could not load calls. Reload the page."));
    });
  }

  function loadCall(id) {
    var node = el("view-call");
    if (!node) return;
    var back = function () { window.TPApp.go("calls", []); };
    if (!id) { window.TPScreens.call(node, { error: true, onBack: back }); return; }
    node.innerHTML = "<div class='empty'>Loading…</div>";
    window.TPApi.call(id).then(function (c) {
      window.TPScreens.call(node, { call: c, onBack: back });
    }, function () {
      window.TPScreens.call(node, { error: true, onBack: back });
    });
  }
```

and in `onShow`:

```javascript
    onShow: function (section, rest) {
      if (section === "home") loadHome();
      else if (section === "calls") loadCalls();
      else if (section === "call") loadCall(rest && rest[0]);
    }
```

- [ ] **Step 5: Run to verify they pass, then commit**

```bash
python3 -m pytest tests/ -q
git add prototype/static/app/screens.js prototype/static/app/main.js tests/test_app_screens.py
git commit -m "feat(app): the calls list and one call's reasoning

A live call says it is still open rather than implying an outcome. An
ungraded call says it was published without a target and is not counted --
the same distinction the record endpoint makes, surfaced where a client can
see it rather than buried in an aggregate.

The list carries an as-of stamp because outside market hours it is the last
session's, and saying so is cheaper than the support question."
```

---

