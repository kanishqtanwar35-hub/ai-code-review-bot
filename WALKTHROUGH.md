# Code walkthrough — 02-ai-code-review-bot

Four modules, each with one job. Read in this order.

```
GitHub Actions (pull_request event)
    |
    v
review.py ------------------------------------------+
    |                                               |
    +-- github.get_pr_diff()      raw unified diff   |
    +-- diff.extract_hunks()      -> [Hunk]          |
    +-- llm.review_hunk()         -> {"findings":[]} | per hunk
    +-- github.post_review()      one review, N comments
```

---

## `diff.py` — the part everyone underestimates

Turning a diff into "file X, line Y" is the actual hard problem here, not the
LLM call.

**Only added lines are reviewed.** `if line.is_added` in `extract_hunks` is the
whole rule. Review a deletion and you get a comment about code that no longer
exists — which is how these bots earn their reputation for noise.

**Line numbers come from `line.target_line_no`**, the position in the *new*
file. Using the old file's numbering puts every comment in the wrong place, and
it is the classic first-attempt bug.

**Skip lists run before the model is called**, not after. A 4,000-line
`package-lock.json` would otherwise consume your entire free-tier quota
producing opinions nobody wants. Note there are two lists: `SKIP_SUFFIXES` for
extensions and `SKIP_NAMES` for generated files whose extension is innocent —
`package-lock.json` ends in `.json` and would sail through a suffix-only check.
The test `test_skips_lockfiles` exists because that exact bug was present in
the first version of this file.

## `prompts.py` — the product

The system prompt is longer than the code that sends it. That ratio is correct.

Three constraints do the real work:

1. **A closed list of categories.** Without it the model reports style.
2. **"Returning nothing is the correct and expected outcome."** Models are
   agreeable and will invent a finding to seem useful. You have to explicitly
   license silence.
3. **One finding per response, most severe.** Caps noise and forces triage.

`temperature: 0.1` — review is not a creative task. And
`responseMimeType: "application/json"` makes Gemini return parseable JSON
rather than prose with JSON in it.

## `llm.py` — raw HTTP, on purpose

No SDK. The call is ten lines, it never breaks on a package upgrade, and you
learn what the API actually looks like — which is what gets asked about.

Two details worth keeping:

- **429 handling.** Free tiers rate-limit per minute. The retry waits
  `2^(attempt+2)` seconds on 429 specifically, rather than treating it as a
  generic failure. Without this, a PR touching fifteen files fails halfway.
- **`_extract_json` strips markdown fences.** Models wrap JSON in ` ```json `
  despite being told not to. Handle it rather than hoping.

## `github.py` — one review, not N comments

`post_review` sends a single review containing all comments. Posting twelve
separate comments sends twelve notifications and gets the bot disabled.

`"event": "COMMENT"` — never `REQUEST_CHANGES`. A bot that can block a merge is
a bot that gets removed the first time it is wrong.

**The 422 fallback** is the most practical thing in this file. GitHub rejects
the *entire* review if any single line is not part of the diff. Rather than
losing every finding, the code retries as a plain issue comment with the
findings inlined. Partial delivery beats silent failure.

## `review.py` — orchestration and blast radius

Two guards worth noting:

- **`MAX_ADDED_LINES`.** A 3,000-line PR is refused with an explanation. This
  protects your free quota and produces better behaviour than a bad review.
- **The bare `except` at the bottom that exits 0.** The review bot must never
  fail someone's build. If Gemini is down, the PR still merges. Deciding what
  is advisory and what is blocking is a design decision, and this one is
  deliberate.

Also note the workflow's `concurrency` block: pushing twice cancels the first
run, so a PR never receives two contradictory reviews.

---

## Extending it

1. **Post the review as a check run** with an annotation count.
2. **Feed it the file's full context**, not just the hunk — better findings,
   more tokens.
3. **Track precision.** Log which comments got resolved versus dismissed. Being
   able to say "72% of my bot's findings were acted on" is a genuinely strong
   interview line, and it is just a counter.
