### Task 5: The book

**Files:**
- Modify: `prototype/static/app/screens.js`
- Modify: `prototype/static/app/main.js`
- Modify: `prototype/client_api.py` (one line — drop `user_id` from the payload)
- Modify: `tests/test_app_screens.py`
- Modify: `tests/test_client_api_positions.py`

**Interfaces:**
- Consumes: `TPApi.positions`, `TPApi.addPosition`, `TPApi.removePosition`.
- Produces: `window.TPScreens.book(node, data)` where `data` is `{book, signedOut, onAdd, onRemove}`.

**There is deliberately no close action.** `PATCH {"closed_at": ...}` hides a position from the only endpoint that can discover its id, and no closed-positions view exists — so closing is unrecoverable through the API. Add and Remove only. This is a recorded controller decision; do not add a Close button.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app_screens.py`:

```python
def test_book_never_renders_a_missing_price_as_zero(client):
    js = client.get("/static/app/screens.js").get_data(as_text=True)
    assert "price unavailable" in js.lower()


def test_book_shows_provenance_for_each_position(client):
    """Which holdings came from a call, and which were the client's own."""
    js = client.get("/static/app/screens.js").get_data(as_text=True)
    assert "call_id" in js
    assert "your own" in js.lower()


def test_book_has_no_close_action(client):
    """Closing hides the only id that could reopen it. Add and Remove only."""
    js = client.get("/static/app/screens.js").get_data(as_text=True).lower()
    assert "closed_at" not in js
```

And append to `tests/test_client_api_positions.py`:

```python
def test_positions_do_not_leak_the_internal_user_id(client, store):
    """A client has no use for their own internal identifier.

    Harmless while it is a stub; once accounts land it is the app's internal
    key for that person, handed to the browser for no reason any screen needs.
    """
    _post(client)
    pos = client.get("/api/app/positions").get_json()["positions"][0]
    assert "user_id" not in pos
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_app_screens.py tests/test_client_api_positions.py -q
```

Expected: 4 failures.

- [ ] **Step 3: Drop `user_id` from the API payload**

In `prototype/client_api.py`, remove `"user_id"` from `POSITION_FIELDS` so it reads:

```python
POSITION_FIELDS = ("id", "symbol", "qty", "avg_price", "opened_at",
                   "closed_at", "exit_price", "source", "broker_ref", "call_id")
```

Queries still scope by `user_id` — only the response stops carrying it.

- [ ] **Step 4: Add the renderer**

In `prototype/static/app/screens.js`, add before the exports:

```javascript
  function positionRow(p, onRemove) {
    var row = el("div", "row");
    var grow = el("div", "grow");
    grow.appendChild(el("div", "name", p.symbol));
    grow.appendChild(el("div", "thin",
      p.call_id ? "from a TradePilot call" : "your own idea"));
    row.appendChild(grow);

    var right = el("div");
    right.style.textAlign = "right";
    if (p.price_unavailable) {
      /* Never zero. A silent 0.0 renders a real holding as worthless. */
      right.appendChild(el("div", "muted", "price unavailable"));
      right.appendChild(el("div", "thin",
        p.qty + " @ " + money(p.avg_price)));
    } else {
      right.appendChild(el("div", null, money(p.value)));
      right.appendChild(el("div", "thin " + (p.pnl >= 0 ? "up" : "down"),
                           money(p.pnl) + " (" + pct(p.pnl_pct) + ")"));
    }
    row.appendChild(right);

    var rm = el("button", "btn quiet", "Remove");
    rm.addEventListener("click", function () { onRemove(p.id, p.symbol); });
    row.appendChild(rm);
    return row;
  }

  function book(node, data) {
    node.innerHTML = "";
    if (data.signedOut) {
      var gate = card(null);
      gate.appendChild(el("div", "empty", "Sign in to see your book."));
      node.appendChild(gate);
      return;
    }

    var list = (data.book && data.book.positions) || [];
    var totals = (data.book && data.book.totals) || {};

    var head = card(null);
    head.appendChild(el("div", "label", "Your portfolio"));
    head.appendChild(el("div", "big", list.length ? money(totals.value) : "--"));
    if (list.length) {
      head.appendChild(el("div", "muted " + (totals.pnl >= 0 ? "up" : "down"),
                           money(totals.pnl) + " overall"));
      if (totals.unpriced) {
        head.appendChild(el("div", "thin", totals.unpriced +
          " holding(s) have no live price and are not included in this total"));
      }
    }
    node.appendChild(head);

    var c = card("Positions");
    if (!list.length) {
      c.appendChild(el("div", "empty", "Nothing logged yet."));
    } else {
      for (var i = 0; i < list.length; i++) {
        c.appendChild(positionRow(list[i], data.onRemove));
      }
    }
    node.appendChild(c);

    var form = card("Log a trade");
    var sym = el("input", "btn"); sym.placeholder = "Symbol, e.g. CIPLA";
    var qty = el("input", "btn"); qty.placeholder = "Quantity"; qty.type = "number";
    var px = el("input", "btn"); px.placeholder = "Average price"; px.type = "number";
    var add = el("button", "btn primary", "Add to my book");
    var err = el("div", "thin");
    add.addEventListener("click", function () {
      err.textContent = "";
      data.onAdd({ symbol: sym.value, qty: Number(qty.value),
                   avg_price: Number(px.value) }, function (message) {
        err.textContent = message;
      });
    });
    form.appendChild(sym); form.appendChild(qty);
    form.appendChild(px); form.appendChild(add); form.appendChild(err);
    node.appendChild(form);
  }
```

Add `book: book, positionRow: positionRow` to the exports.

- [ ] **Step 5: Wire it**

In `prototype/static/app/main.js`:

```javascript
  function loadBook() {
    var node = el("view-book");
    if (!node) return;
    node.innerHTML = "<div class='empty'>Loading…</div>";
    window.TPApi.positions().then(function (b) {
      window.TPScreens.book(node, {
        book: b, signedOut: false,
        onAdd: function (body, onError) {
          if (!body.symbol || !(body.qty > 0) || !(body.avg_price > 0)) {
            onError("Enter a symbol, a positive quantity and a positive price.");
            return;
          }
          window.TPApi.addPosition(body).then(loadBook, function () {
            onError("That could not be added. Check the values and try again.");
          });
        },
        onRemove: function (id, symbol) {
          if (!window.confirm("Remove " + symbol + " from your book?")) return;
          window.TPApi.removePosition(id).then(loadBook, function () {
            window.alert("That could not be removed. Reload and try again.");
          });
        }
      });
    }, function (e) {
      window.TPScreens.book(node, { signedOut: e && e.status === 401 });
    });
  }
```

and add `else if (section === "book") loadBook();` to `onShow`.

- [ ] **Step 6: Run to verify they pass, then commit**

```bash
python3 -m pytest tests/ -q
git add prototype/static/app/screens.js prototype/static/app/main.js prototype/client_api.py tests/test_app_screens.py tests/test_client_api_positions.py
git commit -m "feat(app): the book, with provenance and no unrecoverable action

Every position says whether it came from a TradePilot call or was the
client's own idea -- the split the spec calls the most valuable number in the
product, now visible rather than merely derivable.

A holding with no live quote reads 'price unavailable' and shows its cost
basis. It never reads zero, and the portfolio total says how many holdings it
left out.

There is no Close button. Closing hides the only id that could reopen the
position and no closed-positions view exists, so it is unrecoverable through
the API. Add and Remove only until that view exists.

Also drops user_id from the positions payload: a client has no use for their
own internal identifier, and once accounts land it is a real key."
```

---

