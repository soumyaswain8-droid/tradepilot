### Task 6: The shell knows who you are

Populates the `#who` element the dashboard review flagged as dead, using `/api/app/me` — the one endpoint no screen consumed. Then updates the manual checklist, whose signed-out procedure is now obsolete.

**Files:**
- Modify: `prototype/static/app/api.js` (add `me`)
- Modify: `prototype/static/app/main.js` (populate `#who` at boot)
- Modify: `prototype/static/app.css` (one rule for the sign-out button)
- Modify: `docs/APP_MANUAL_CHECKS.md`
- Test: `tests/test_app_screens.py`

**Interfaces:**
- Consumes: `GET /api/app/me` returning `{"user_id": ..., "plan": ...}` or 401; `TPApi` (the object in `api.js`); `TPApp.boot`
- Produces: nothing other tasks consume

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app_screens.py`:

```python
def test_the_api_client_can_ask_who_is_signed_in(client):
    js = client.get("/static/app/api.js").get_data(as_text=True)
    assert "/api/app/me" in js


def test_the_shell_fills_the_who_element(client):
    js = client.get("/static/app/main.js").get_data(as_text=True)
    assert "\"who\"" in js or "'who'" in js


def test_the_shell_offers_a_way_in_and_a_way_out(client):
    js = client.get("/static/app/main.js").get_data(as_text=True)
    assert "/app/login" in js
    assert "/app/logout" in js
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_app_screens.py -q`
Expected: FAIL on all three.

- [ ] **Step 3: Add `me` to the API client**

In `prototype/static/app/api.js`, alongside the existing methods:

```javascript
me: function () { return get("/api/app/me"); },
```

Use whatever the file's existing internal helper is named — read it first. Do not introduce a second `fetch` call site.

- [ ] **Step 4: Populate `#who` at boot**

In `prototype/static/app/main.js`, add this function and call it from `boot`:

```javascript
function loadWho() {
  var node = el("who");
  if (!node) return;
  window.TPApi.me().then(function (m) {
    node.innerHTML = "";
    var name = window.TPScreens.el("span", "thin", m.user_id);
    var out = document.createElement("form");
    out.method = "post";
    out.action = "/app/logout";
    out.style.display = "inline";
    var b = document.createElement("button");
    b.type = "submit";
    b.className = "who-out";
    b.textContent = "Sign out";
    out.appendChild(b);
    node.appendChild(name);
    node.appendChild(out);
  }, function () {
    /* 401 is the ordinary signed-out case, not an error worth shouting about.
       Anything else lands here too, and the honest rendering is the same:
       offer the way in, claim nothing about who they are. */
    node.innerHTML = "";
    var a = document.createElement("a");
    a.href = "/app/login";
    a.textContent = "Sign in";
    node.appendChild(a);
  });
}
```

Sign-out is a form POST, not a link: a `GET /app/logout` could be triggered by any image tag on any page.

`app.css` has a `.who` rule but nothing for a button inside it, so add one — otherwise Sign out renders as a chunky default button in a 12px text header:

```css
.who-out {
  background: none; border: 0; padding: 0 0 0 0.5rem;
  font: inherit; color: var(--accent); cursor: pointer;
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_app_screens.py -q`
Expected: PASS.

- [ ] **Step 6: Verify ES5 and the single fetch site**

Run:

```bash
grep -nE "=>|\bconst \b|\blet \b|\`" prototype/static/app/main.js prototype/static/app/api.js
grep -rln "fetch(" prototype/static/app/
```

Expected: the first prints nothing outside comments; the second prints only `api.js`.

- [ ] **Step 7: Replace the obsolete section of the manual checklist**

In `docs/APP_MANUAL_CHECKS.md`, delete the procedure that instructs the reader to edit `prototype/client_auth.py` and revert it, including its bold warning. Replace it with:

```markdown
### Signing out

Click **Sign out** in the header. To sign back in, use the **Sign in** link,
or go to `/app/login` directly.

::: {.checklist}

| | Verification |
|:---:|:-------------|
| ☐ | The header shows your email and a Sign out control when signed in |
| ☐ | The header shows a Sign in link when signed out |
| ☐ | After signing out, the Book reads "Sign in to see your book" and the link reaches `/app/login` |
| ☐ | Home and Calls still render fully when signed out -- they are public |
| ☐ | Signing in from `/app/login` returns you to `/app`, still signed in after a reload |
| ☐ | A wrong password says the same thing as an unknown email |

:::
```

Check the rest of the file for any other reference to editing `client_auth.py` and remove those too. A checklist that still tells a reader to modify source will be followed by someone who does not know it is obsolete.

- [ ] **Step 8: Run the whole suite**

Run: `python3 -m pytest tests/ -q` and `node --test "tests/js/*.test.js"`

Expected: both pass. Report both counts. Note that `node --test tests/js/` (with a trailing directory rather than the glob) fails with `MODULE_NOT_FOUND` on Node 22 and is not a real failure — use the quoted glob.

- [ ] **Step 9: Commit**

```bash
git add prototype/static/app/api.js prototype/static/app/main.js prototype/static/app.css docs/APP_MANUAL_CHECKS.md tests/test_app_screens.py
git commit -m "feat(app): the shell shows who is signed in

Populates #who, which the dashboard review found was never filled, using
/api/app/me, which was the one endpoint no screen consumed -- each was
the other's answer.

Sign-out is a form POST: a GET could be triggered by any image tag on
any page. The manual checklist's edit-the-source procedure for reaching
a signed-out screen is replaced by clicking Sign out."
```

---

## What this plan does not do

Self-serve signup, email verification, password reset, and the mail provider they depend on are **project B2**. Per-user Kite tokens, a closed-positions view and the `/classic` redirect are later still.

**The SEBI Research Analyst / Investment Adviser position remains a deploy gate.** Authentication does not change it; it only makes the audience easier to grow.
