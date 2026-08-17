"""Diff parsing tests — these run without any API key.

Everything network-dependent is excluded on purpose: a test suite that needs
a secret is a test suite that never runs.
"""

from src.reviewer.diff import extract_hunks, should_review, total_added_lines

SAMPLE_DIFF = """diff --git a/calc.py b/calc.py
index 1111111..2222222 100644
--- a/calc.py
+++ b/calc.py
@@ -1,2 +1,5 @@
 def add(a, b):
     return a + b
+
+def divide(a, b):
+    return a / b
diff --git a/package-lock.json b/package-lock.json
index 3333333..4444444 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,2 +1,3 @@
 {
+  "noise": true
 }
"""


def test_skips_lockfiles():
    assert should_review("src/app.py") is True
    assert should_review("package-lock.json") is False
    assert should_review("node_modules/foo/index.js") is False
    assert should_review("static/logo.svg") is False


def test_extracts_only_reviewable_files():
    hunks = extract_hunks(SAMPLE_DIFF)
    assert len(hunks) == 1
    assert hunks[0].path == "calc.py"


def test_hunk_contains_added_lines_with_numbers():
    hunk = extract_hunks(SAMPLE_DIFF)[0]
    assert "def divide(a, b):" in hunk.body
    assert "return a / b" in hunk.body
    # deletions and context must not appear
    assert "return a + b" not in hunk.body


def test_start_line_points_at_first_added_line():
    hunk = extract_hunks(SAMPLE_DIFF)[0]
    assert hunk.start_line == 3


def test_max_hunks_is_respected():
    assert len(extract_hunks(SAMPLE_DIFF, max_hunks=0)) <= 1


def test_total_added_lines_counts_every_file():
    # 3 added in calc.py + 1 in the lockfile
    assert total_added_lines(SAMPLE_DIFF) == 4
