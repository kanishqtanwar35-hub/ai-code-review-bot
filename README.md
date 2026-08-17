# AI code review bot

A GitHub Action that reviews the added lines of every pull request and posts a
single review with inline comments. Runs on GitHub Actions' free tier and
Gemini's free tier — **total cost £0/month**.

**Status:** diff parsing verified, 6/6 tests pass. The LLM and GitHub calls need
live credentials, so they are exercised on your first real PR.

---

## Why this one is worth building

It is permanently visible. Every PR on the repo carries the bot's output, so
anyone who opens your GitHub sees the thing working without cloning anything.
It also proves four separate skills at once: diff parsing, prompt design, API
integration, and CI configuration.

---

## Setup

1. **Get a Gemini key** — <https://aistudio.google.com/apikey> (free).
2. **Add it as a repo secret** — Settings → Secrets and variables → Actions →
   New repository secret → name `GEMINI_API_KEY`.
3. **Copy `.github/workflows/ai-review.yml`** into any repo, along with
   `review.py`, `src/reviewer/` and `requirements.txt`.
4. **Open a pull request.** The bot reviews it.

`GITHUB_TOKEN` is provided automatically by Actions — you do not create it.

---

## Behaviour

| Situation | What happens |
|---|---|
| Normal PR | One review, at most one comment per hunk |
| Nothing wrong | Posts "no issues found" — silence would look broken |
| PR over 1,500 added lines | Refuses and asks for a split |
| Lockfiles, images, `node_modules/` | Skipped before the model is called |
| Line not in the diff (422) | Falls back to a summary comment |
| Rate limited (429) | Exponential backoff, up to 3 attempts |
| Bot itself errors | Exits 0 — never fails your build |
| PR from a fork | Skipped (forked tokens are read-only) |

---

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | — | required |
| `GEMINI_MODEL` | `gemini-2.0-flash` | any Gemini model id |
| `MAX_HUNKS` | `20` | caps calls per PR |
| `MAX_ADDED_LINES` | `1500` | refuse-to-review threshold |

---

## What it deliberately does *not* review

Style, formatting, naming, missing docstrings, and "consider using X instead"
when the code is already correct. See `src/reviewer/prompts.py`.

This restraint is the whole design. A bot that comments on every hunk gets
muted in a week; one that speaks rarely gets read. Being able to explain that
tradeoff is worth more in an interview than the code itself.

---

## Testing locally

```bash
pip install -r requirements.txt
pytest -q                       # 6 tests, no API key needed
```

To dry-run against a real PR:

```bash
export GITHUB_TOKEN=ghp_...
export GEMINI_API_KEY=...
export GITHUB_REPOSITORY=yourname/yourrepo
export PR_NUMBER=1
python review.py
```
