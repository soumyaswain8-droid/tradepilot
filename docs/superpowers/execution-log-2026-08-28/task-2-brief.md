### Task 2: Embed mode for /floor and /team

The two Agent Floor screens supply their own brand chrome, which is redundant once the terminal frames them. `team.html` additionally loads `pageswitch.js` — the floating operator nav — which must not appear inside a pane. `floor.html` does **not** load `pageswitch.js`; only its brand span needs hiding, and its stats strip (ticks, rate, escalations, armed, gaps) must be kept because that data is the point of the screen.

**Files:**
- Modify: `prototype/app.py:121-125` (the `/floor` handler) and `prototype/app.py:3094-3098` (the `/team` handler)
- Modify: `prototype/templates/floor.html` (the `.bar` block near the top of `<body>`)
- Modify: `prototype/templates/team.html` (the `<header>` block, and line 249)
- Modify: `tests/test_web_routes.py`

**Interfaces:**
- Consumes: the `client` fixture from Task 1.
- Produces: `GET /floor?embed=1` and `GET /team?embed=1` render without brand chrome. Task 5's iframes point at exactly these URLs.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_web_routes.py`:

```python
def test_floor_embed_hides_brand(client):
    """?embed=1 drops the brand span; the stats strip must survive."""
    r = client.get("/floor?embed=1")
    assert r.status_code == 200
    assert b"AGENT FLOOR</span>" not in r.data
    assert b'id="sTicks"' in r.data          # stats strip kept


def test_floor_without_embed_keeps_brand(client):
    """The standalone page is unchanged."""
    r = client.get("/floor")
    assert b"AGENT FLOOR</span>" in r.data


def test_team_embed_hides_header_and_pageswitch(client):
    """?embed=1 drops the header and must not load the operator nav."""
    r = client.get("/team?embed=1")
    assert r.status_code == 200
    # Match the <h1>, not the bare string: team.html:5 also carries
    # "TradePilot Quant Desk" in its <title>, which embed mode keeps.
    assert b"<h1>TradePilot Quant Desk</h1>" not in r.data
    assert b"pageswitch.js" not in r.data


def test_team_without_embed_keeps_header(client):
    """The standalone page is unchanged."""
    r = client.get("/team")
    assert b"<h1>TradePilot Quant Desk</h1>" in r.data
    assert b"pageswitch.js" in r.data
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_web_routes.py -v -k embed
```

Expected: `test_floor_embed_hides_brand` and `test_team_embed_hides_header_and_pageswitch` FAIL (the brand and pageswitch are still present — `?embed=1` is currently ignored). The two `without_embed` tests PASS.

- [ ] **Step 3: Pass the flag from Flask**

In `prototype/app.py`, replace the `/floor` handler:

```python
@app.route("/floor")
def floor_view():
    """Live console for the agent floor -- what each agent is watching, right now.

    ?embed=1 strips the brand span so the console can be framed inside the
    terminal, which supplies its own chrome. The stats strip stays: it is the
    point of the screen.
    """
    return render_template("floor.html", embed=request.args.get("embed") == "1")
```

and the `/team` handler:

```python
@app.route("/team")
def team_view():
    """Quant desk -- agent roster, pending tasks, audit log.

    ?embed=1 strips the header and skips pageswitch.js, which must never
    render inside a terminal pane.
    """
    return render_template("team.html", embed=request.args.get("embed") == "1")
```

`request` is already imported at `prototype/app.py:6`. If the existing `/team` handler body differs from the above, keep its original `render_template` arguments and add only the `embed=` keyword.

- [ ] **Step 4: Guard the markup**

In `prototype/templates/floor.html`, wrap the brand span inside the `.bar` div:

```jinja
{% if not embed %}<span class="brand">TRADE<b>PILOT</b> · AGENT FLOOR</span>{% endif %}
```

In `prototype/templates/team.html`, wrap the whole `<header>` element:

```jinja
{% if not embed %}
<header>
  <h1>TradePilot Quant Desk</h1>
  <div class="meta">
    <span id="ts">—</span>
    &nbsp;·&nbsp;
    <a class="nav-link" href="/team/sarathi">Sarathi Ledger</a>
    &nbsp;·&nbsp;
    <a class="nav-link" href="/live">Live Engines</a>
  </div>
</header>
{% endif %}
```

`team.html` writes a timestamp into `#ts`, which no longer exists in embed mode. At line 249, guard the pageswitch include and leave the page's own script untouched:

```jinja
{% if not embed %}<script src="/static/pageswitch.js"></script>{% endif %}
```

`team.html:233` writes to `#ts` unconditionally. Replace that exact line:

```js
    document.getElementById("ts").textContent = fmt(j.ts);
```

with:

```js
    var tsEl = document.getElementById("ts");
    if (tsEl) tsEl.textContent = fmt(j.ts);
```

Only the null guard is new — `fmt(j.ts)` is unchanged. Without this the poll tick throws a TypeError every second in embed mode and the pane stops updating, which presents as "the pane loaded once and froze".

- [ ] **Step 5: Run the tests to verify they pass**

```bash
python3 -m pytest tests/test_web_routes.py -v
```

Expected: all seven PASS.

- [ ] **Step 6: Verify in the browser**

```bash
python3 prototype/app.py
```

Open `http://localhost:5050/team?embed=1`. Expected: no header, no floating nav pill, KPI strip and agent grid render normally, and the browser console shows **no errors** across at least two poll ticks (roughly 20 seconds). Then open `http://localhost:5050/team` and confirm the header and nav pill are back. Repeat for `/floor?embed=1` — the stats strip must still update.

- [ ] **Step 7: Commit**

```bash
git add prototype/app.py prototype/templates/floor.html prototype/templates/team.html tests/test_web_routes.py
git commit -m "feat(floor,team): embed mode for framing inside the terminal

?embed=1 drops the brand chrome each page supplies for itself, and stops
team.html loading the operator nav pill -- which has no business rendering
inside a pane. floor.html keeps its stats strip: ticks, rate, escalations
and armed are the screen, not decoration.

Also null-guards team.html's #ts write, which the header guard removes."
```

---

