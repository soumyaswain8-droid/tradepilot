"""Terminology guard: no promise-language reaches a user-facing surface.

compliance/terminology.yaml holds a versioned list of banned patterns
(predict, guarantee, assured, expected profit, ...) and the globs to scan.
This test walks those globs and fails with every hit as ``path:line: word`` so
the offender is fixable from the assertion message alone.

Matching rules, decided here and documented so nobody re-litigates them:

* Case-insensitive, word-boundary matching (``\\b<pattern>\\b``). ``predict``
  therefore does NOT match ``predictable`` or ``predictor``; plurals that
  carry the same promise (``predictions``, ``guarantees``) are listed
  explicitly in the yaml.
* Comments are NOT stripped and NOT exempt. A banned word inside an HTML
  ``<!-- -->`` or a JS/Dart ``//`` / ``/* */`` comment is still a hit,
  because comments get copy-pasted into copy and a wrong mental model in a
  comment becomes a wrong sentence on a page. Hits on comment lines are
  labelled ``(comment)`` in the message so the reader can see what kind of
  hit it is. A comment that legitimately names the concept (a disclaimer, a
  note that script order "guarantees" something) is exempted through an
  ``allow`` entry with a reason, never by loosening the scan.
* An ``allow`` entry is {file, line_contains, reason, [word]}. ``file`` is a
  repo-relative path (fnmatch globs accepted); ``line_contains`` is a
  substring of the offending line; ``word``, when present, restricts the
  exemption to that one banned pattern so the rest of the line stays guarded.
* Every allow entry must still match a real hit -- a stale exemption is a
  hole, so it fails the build too.
* ``*.bak*`` files are skipped: they are archived copies, not surfaces.
"""
import fnmatch
import glob
import os
import re
import sys

import pytest
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

RULES_PATH = os.path.join(REPO_ROOT, "compliance", "terminology.yaml")

_COMMENT_PREFIXES = ("//", "/*", "*", "<!--", "#")


def load_rules(path=RULES_PATH):
    with open(path, encoding="utf-8") as fh:
        rules = yaml.safe_load(fh)
    assert rules.get("version") == 1, "terminology.yaml must declare version: 1"
    assert rules.get("banned"), "terminology.yaml has no banned patterns"
    assert rules.get("scan"), "terminology.yaml has no scan globs"
    rules.setdefault("allow", [])
    return rules


def compile_banned(rules):
    """[(pattern_text, compiled_regex, replace_with), ...] with word boundaries."""
    out = []
    for entry in rules["banned"]:
        pat = entry["pattern"]
        out.append((pat, re.compile(r"\b(?:" + pat + r")\b", re.IGNORECASE), entry.get("replace_with", "")))
    return out


def _is_comment_line(line):
    return line.lstrip().startswith(_COMMENT_PREFIXES)


def scan_file(path, compiled, root=REPO_ROOT):
    """Return [(rel_path, line_no, pattern_text, line_text, is_comment), ...]."""
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    hits = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh, 1):
            for pat, rx, _ in compiled:
                if rx.search(line):
                    hits.append((rel, line_no, pat, line.rstrip("\n"), _is_comment_line(line)))
    return hits


def scan_tree(rules, root=REPO_ROOT):
    compiled = compile_banned(rules)
    files = set()
    for pattern in rules["scan"]:
        for p in glob.glob(os.path.join(root, pattern), recursive=True):
            if os.path.isfile(p) and ".bak" not in os.path.basename(p):
                files.add(p)
    hits = []
    for p in sorted(files):
        hits.extend(scan_file(p, compiled, root))
    return hits


def _allow_matches(entry, hit):
    rel, _, pat, line, _ = hit
    if not fnmatch.fnmatch(rel, entry["file"]):
        return False
    if entry["line_contains"] not in line:
        return False
    if entry.get("word") and entry["word"] != pat:
        return False
    return True


def is_allowed(hit, allow):
    return any(_allow_matches(e, hit) for e in allow)


def format_hit(hit):
    rel, line_no, pat, line, is_comment = hit
    tag = " (comment)" if is_comment else ""
    return f"{rel}:{line_no}: {pat}{tag}  |  {line.strip()[:120]}"


# --------------------------------------------------------------------------
# rules file sanity
# --------------------------------------------------------------------------

def test_rules_file_loads_and_is_versioned():
    rules = load_rules()
    assert rules["version"] == 1
    for entry in rules["banned"]:
        assert entry.get("pattern"), entry
        assert entry.get("replace_with"), f"{entry['pattern']} has no replace_with suggestion"
    for entry in rules["allow"]:
        for key in ("file", "line_contains", "reason"):
            assert entry.get(key), f"allow entry missing {key}: {entry}"


# --------------------------------------------------------------------------
# self-tests on planted files (prove the scanner catches what it should)
# --------------------------------------------------------------------------

def test_planted_word_is_caught(tmp_path):
    """A tmp file containing 'guaranteed returns' must be reported."""
    rules = load_rules()
    planted = tmp_path / "planted.html"
    planted.write_text("<p>Enjoy guaranteed returns every month.</p>\n", encoding="utf-8")
    hits = scan_file(str(planted), compile_banned(rules), root=str(tmp_path))
    assert hits, "scanner missed a planted 'guaranteed returns'"
    assert hits[0][0] == "planted.html"
    assert hits[0][1] == 1
    assert hits[0][2] == "guaranteed"
    assert "planted.html:1: guaranteed" in format_hit(hits[0])


def test_word_boundaries_and_case(tmp_path):
    rules = load_rules()
    compiled = compile_banned(rules)
    f = tmp_path / "words.js"
    f.write_text(
        "// 1 predictable outcome\n"
        "// 2 the predictor module\n"
        "3 PREDICT the close\n"
        "4 no stale predictions\n"
        "5 a Risk-Free rate\n"
        "6 expected  profit\n"
        "7 profit is assured\n",
        encoding="utf-8",
    )
    hits = scan_file(str(f), compiled, root=str(tmp_path))
    lines_hit = sorted({h[1] for h in hits})
    assert 1 not in lines_hit, "'predictable' must not match 'predict'"
    assert 2 not in lines_hit, "'predictor' must not match 'predict'"
    assert 3 in lines_hit, "case-insensitive: PREDICT"
    assert 4 in lines_hit, "plural: predictions"
    assert 5 in lines_hit, "hyphenated: Risk-Free"
    assert 6 not in lines_hit, "double space is not the phrase (exact pattern)"
    assert 7 in lines_hit, "assured"
    comment_hit = [h for h in hits if h[1] == 3]
    assert not comment_hit[0][4]
    assert "(comment)" not in format_hit(comment_hit[0])


def test_comment_is_still_a_hit_but_labelled(tmp_path):
    rules = load_rules()
    f = tmp_path / "c.dart"
    f.write_text("// AI prediction widget\n<!-- guaranteed -->\n", encoding="utf-8")
    hits = scan_file(str(f), compile_banned(rules), root=str(tmp_path))
    assert [h[1] for h in hits] == [1, 2]
    assert all(h[4] for h in hits)
    assert "(comment)" in format_hit(hits[0])


def test_allow_entry_can_restrict_to_one_word():
    hit_guarantee = ("x.html", 1, "guarantees?", "Past performance does not guarantee future results", False)
    hit_predict = ("x.html", 1, "predictions?", "Past performance does not guarantee future results", False)
    allow = [{"file": "x.html", "line_contains": "does not guarantee", "word": "guarantees?", "reason": "t"}]
    assert is_allowed(hit_guarantee, allow)
    assert not is_allowed(hit_predict, allow)
    allow_any = [{"file": "*.html", "line_contains": "does not guarantee", "reason": "t"}]
    assert is_allowed(hit_predict, allow_any)


# --------------------------------------------------------------------------
# the real tree
# --------------------------------------------------------------------------

def test_every_allow_entry_still_matches_a_real_hit():
    rules = load_rules()
    hits = scan_tree(rules)
    stale = [e for e in rules["allow"] if not any(_allow_matches(e, h) for h in hits)]
    assert not stale, "stale allow entries (remove them):\n" + "\n".join(
        f"  {e['file']} :: {e['line_contains']!r}" for e in stale
    )


def test_no_banned_terminology_on_user_facing_surfaces():
    rules = load_rules()
    replace = {e["pattern"]: e["replace_with"] for e in rules["banned"]}
    hits = scan_tree(rules)
    offending = [h for h in hits if not is_allowed(h, rules["allow"])]
    msg = "\n".join(f"  {format_hit(h)}\n      -> {replace.get(h[2], '')}" for h in offending)
    assert not offending, f"{len(offending)} banned term(s) on user-facing surfaces:\n{msg}"
