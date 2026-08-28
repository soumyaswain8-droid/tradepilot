### Task 5: Agent Floor panes

Mounts the two consoles. `src` is set on show and cleared on hide, which is what stops two one-second poll loops running behind a tab nobody is looking at — roughly 3,600 needless requests an hour against `/api/floor/live` and `/api/team/status`.

**Files:**
- Create: `prototype/static/desk/panes.js`
- Modify: `tests/test_web_routes.py`

**Interfaces:**
- Consumes: `TPRouter.register` from Task 4; the `?embed=1` URLs from Task 2.
- Produces: nothing further depends on this.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_web_routes.py`:

```python
def test_agent_floor_panes_exist(client):
    """Both panes are in the shell."""
    body = client.get("/").data
    assert b'id="view-agents-quant"' in body
    assert b'id="view-agents-floor"' in body


def test_agent_floor_frames_ship_empty(client):
    """Frames must have no src in the served HTML.

    A hardcoded src would load and start polling both consoles on every
    page load, whether or not anyone opens the section.
    """
    body = client.get("/").data
    # Assert the behaviour, not the attribute order: no framed URL may appear
    # in the served HTML at all. panes.js sets src at mount time.
    assert b"/team?embed=1" not in body
    assert b"/floor?embed=1" not in body
    assert b'id="frameQuant"' in body
    assert b'id="frameFloor"' in body


def test_panes_module_loaded(client):
    assert b"/static/desk/panes.js" in client.get("/").data
```

- [ ] **Step 2: Run to verify the third fails**

```bash
python3 -m pytest tests/test_web_routes.py -v -k "pane or frame"
```

Expected: the first two PASS (Task 4 added the markup), `test_panes_module_loaded` FAILS — the script tag exists but the file does not, so Flask serves the reference while the browser 404s. That mismatch is the point of the test.

- [ ] **Step 3: Write the panes module**

Create `prototype/static/desk/panes.js`:

```js
/* panes.js — the two Agent Floor consoles, framed.

   Why iframes: /floor and /team are self-contained documents that assume they
   own the browser. floor.html sets body{overflow:hidden}, paints scanlines via
   body::after and sizes a canvas to the viewport; team.html styles bare
   header/main/section selectors. All three stylesheets also define --bg,
   --panel and --green with DIFFERENT values, so concatenating them would let
   last-one-wins quietly restyle whichever loaded first. A frame is a document
   boundary, which is exactly the isolation those two need.

   Why unmount clears src: both poll once a second. Left mounted behind a
   hidden tab that is ~3,600 requests an hour for a screen nobody is looking
   at. about:blank tears the document down and takes its timers with it. */
(function () {
  "use strict";

  function pane(viewId, frameId, src) {
    window.TPRouter.register(viewId, {
      mount: function () {
        var f = document.getElementById(frameId);
        if (f && f.getAttribute("src") !== src) f.setAttribute("src", src);
      },
      unmount: function () {
        var f = document.getElementById(frameId);
        if (f) f.setAttribute("src", "about:blank");
      }
    });
  }

  pane("agents-quant", "frameQuant", "/team?embed=1");
  pane("agents-floor", "frameFloor", "/floor?embed=1");
})();
```

There is no `refresh` hook and no `pollMs`. The framed documents run their own poll loops; the router must not also drive them.

- [ ] **Step 4: Run every test**

```bash
python3 -m pytest tests/test_web_routes.py -v && node --test tests/js/
```

Expected: 13 pytest PASS, 12 node PASS.

- [ ] **Step 5: Verify the panes in the browser**

```bash
python3 prototype/app.py
```

1. Open `http://localhost:5050/#agents` → Quant Desk loads inside the pane, no duplicate header, no floating nav pill.
2. Click **Live Floor** → the floor console loads with its radar drawing and stats strip live.
3. Open DevTools → **Network**, filter to `floor/live`. Click back to **Quant Desk**. Expected: `api/floor/live` requests **stop entirely** within a second or two. This is the unmount working; if they continue, `src` is not being cleared.
4. Click **Desk**. Expected: both `api/floor/live` and `api/team/status` are silent.
5. Return to **Agent Floor** → the pane reloads and resumes.
6. Reload the browser on `#agents/floor` → it opens directly on Live Floor.

- [ ] **Step 6: Commit**

```bash
git add prototype/static/desk/panes.js tests/test_web_routes.py
git commit -m "feat(terminal): mount the agent floor as lazy panes

Quant Desk and Live Floor now live under one Agent Floor section. They are
framed rather than ported because both assume they own the document -- and
because desk.css, team.html and floor.html each define --bg, --panel and
--green with different values, so merging them would let last-one-wins
restyle whichever loaded first.

Hiding a pane sets src to about:blank, which tears the document down and
takes its one-second poller with it. Left mounted, the two of them are
~3,600 requests an hour against a screen nobody is looking at."
```

---

## Verification

Run both suites from the repo root:

```bash
cd ~/Documents/tinker/projects/tradepilot
python3 -m pytest tests/test_web_routes.py -v
node --test tests/js/
```

Expected: **13 pytest passing, 12 node passing, 0 failures.**

The plan is complete when, in addition, all of the following hold in a browser against `python3 prototype/app.py`:

| | Check |
|:---:|:--|
| ☐ | `/` opens on Desk with no sub-tab bar |
| ☐ | Agent Floor shows two sub-tabs and both panes load |
| ☐ | Leaving Agent Floor stops all `api/floor/live` and `api/team/status` traffic |
| ☐ | `#market/TITAN/5y` still opens the TITAN drawer at 5y |
| ☐ | `#agents/floor` deep-links straight to Live Floor |
| ☐ | `/team` and `/floor` still work standalone, with their own chrome |
| ☐ | No console errors on any tab across two poll cycles |

## Not in this plan

Plan 2 adds the Research and Portfolio sections by absorbing `/lab`, `/decisions`, `/portfolio` and `/fleet`, and converts those routes to redirects. Plan 3 extracts F&O, US Market, Trade Lab and Ask out of `index.html` — the work that shrinks `/classic` for project C — and retires `pageswitch.js`. Neither authentication nor the client redesign belongs to any of the three; those are projects B and C.
