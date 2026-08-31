### Task 4: The track record

**Files:**
- Modify: `prototype/static/app/screens.js`
- Modify: `prototype/static/app/main.js`
- Modify: `tests/test_app_screens.py`

**Interfaces:**
- Consumes: `TPScreens.rateLine` and `TPScreens.stamp` (both from earlier tasks), `TPApi.record`, `TPApi.calls`.
- Produces: `window.TPScreens.record(node, data)` where `data` is `{record, calls}`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_app_screens.py`:

```python
def test_record_screen_labels_since_as_recording_not_grading(client):
    """`since` is the first call RECORDED, not the first resolved.

    "Track record since January -- 62%" where the first call resolved in June
    overstates the record's age. The spec's Deferred section makes this a
    constraint on this screen, not on the API.
    """
    js = client.get("/static/app/screens.js").get_data(as_text=True).lower()
    assert "recording since" in js
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_app_screens.py -q
```

Expected: 1 failure — the phrase is absent.

- [ ] **Step 3: Add the renderer**

In `prototype/static/app/screens.js`, add before the exports:

```javascript
  function record(node, data) {
    node.innerHTML = "";
    var rec = data.record;

    var head = card("Track record");
    head.appendChild(rateLine(rec));
    /* "since" is the first call RECORDED, not the first resolved. Labelling it
       "recording since" keeps the page from implying the rate has been earned
       across that whole span. */
    head.appendChild(el("div", "thin", rec.since
      ? "Recording since " + rec.since
      : "Nothing recorded yet."));
    node.appendChild(head);

    var split = card("How the calls stand");
    var rows = [["Hit", rec.hit], ["Missed", rec.miss],
                ["Still open", rec.open],
                ["Ungraded (no target published)", rec.ungraded]];
    for (var i = 0; i < rows.length; i++) {
      var r = el("div", "row");
      r.appendChild(el("div", "grow muted", rows[i][0]));
      r.appendChild(el("div", null, rows[i][1]));
      split.appendChild(r);
    }
    split.appendChild(el("div", "thin",
      "Ungraded calls are excluded from the rate -- a call published without " +
      "a target has no standard to be graded against."));
    node.appendChild(split);

    var list = (data.calls && data.calls.calls) || [];
    var resolved = [];
    for (var j = 0; j < list.length; j++) {
      if (list[j].outcome === "hit" || list[j].outcome === "miss") {
        resolved.push(list[j]);
      }
    }
    var recent = card("Resolved calls");
    if (!resolved.length) {
      recent.appendChild(el("div", "empty", "Nothing has resolved yet."));
    } else {
      for (var k = 0; k < resolved.length; k++) {
        var c = resolved[k];
        var row = el("div", "row");
        var grow = el("div", "grow");
        grow.appendChild(el("div", "name", c.symbol));
        grow.appendChild(el("div", "thin", stamp(c.published_at)));
        row.appendChild(grow);
        row.appendChild(el("div", "muted " + (c.outcome === "hit" ? "up" : "down"),
                           c.outcome === "hit" ? "Hit" : "Missed"));
        recent.appendChild(row);
      }
    }
    node.appendChild(recent);
  }
```

Add `record: record` to the exports.

- [ ] **Step 4: Wire it**

In `prototype/static/app/main.js`:

```javascript
  function loadRecord() {
    var node = el("view-record");
    if (!node) return;
    node.innerHTML = "<div class='empty'>Loading…</div>";
    Promise.all([window.TPApi.record(), window.TPApi.calls(50)])
      .then(function (r) {
        window.TPScreens.record(node, { record: r[0], calls: r[1] });
      }, function () {
        node.innerHTML = "";
        node.appendChild(window.TPScreens.el(
          "div", "empty", "Could not load the record. Reload the page."));
      });
  }
```

and add `else if (section === "record") loadRecord();` to `onShow`.

- [ ] **Step 5: Run to verify it passes, then commit**

```bash
python3 -m pytest tests/ -q
git add prototype/static/app/screens.js prototype/static/app/main.js tests/test_app_screens.py
git commit -m "feat(app): the track record, labelled honestly

'Recording since' rather than a bare 'since'. The API's since field is the
first call recorded, not the first resolved, so a page saying 'since January
-- 62%' where the first call resolved in June overstates the record's age.
The spec makes that a constraint on this screen rather than on the API.

Ungraded calls are shown and explained rather than hidden: excluding them
from the rate is defensible, excluding them silently is not."
```

---

