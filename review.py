"""Entrypoint. Runs inside GitHub Actions on every pull request.

    python review.py

Required environment:
    GITHUB_TOKEN        provided automatically by Actions
    GITHUB_REPOSITORY   provided automatically ("owner/repo")
    PR_NUMBER           set in the workflow
    GEMINI_API_KEY      your repo secret
"""

import os
import sys

from src.reviewer.diff import extract_hunks, total_added_lines
from src.reviewer.github import get_pr_diff, post_review
from src.reviewer.llm import LLMError, review_hunk
from src.reviewer.prompts import SYSTEM, build_user_prompt

MAX_HUNKS = int(os.getenv("MAX_HUNKS", "20"))
MAX_ADDED_LINES = int(os.getenv("MAX_ADDED_LINES", "1500"))


def main() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    pr_number = int(os.environ["PR_NUMBER"])

    diff = get_pr_diff(repo, pr_number)
    added = total_added_lines(diff)

    # Refuse enormous PRs rather than burning the free tier producing noise.
    if added > MAX_ADDED_LINES:
        post_review(
            repo,
            pr_number,
            f"This PR adds {added} lines, above the {MAX_ADDED_LINES}-line "
            "review limit. Split it and I will review each part.",
            [],
        )
        return 0

    hunks = extract_hunks(diff, max_hunks=MAX_HUNKS)
    if not hunks:
        print("nothing reviewable in this diff")
        return 0

    print(f"reviewing {len(hunks)} hunks across the diff")

    comments = []
    failures = 0

    for hunk in hunks:
        try:
            result = review_hunk(SYSTEM, build_user_prompt(hunk.path, hunk.body))
        except LLMError as e:
            print(f"  ! {hunk.path}: {e}")
            failures += 1
            continue

        for finding in result.get("findings", [])[:1]:
            comments.append(
                {
                    "path": hunk.path,
                    "line": int(finding.get("line", hunk.start_line)),
                    "side": "RIGHT",
                    "body": (
                        f"**{finding.get('category', 'note')}** — "
                        f"{finding.get('comment', '').strip()}"
                    ),
                }
            )
            print(f"  + {hunk.path}:{finding.get('line')} {finding.get('category')}")

    if comments:
        body = (
            f"Automated review of {len(hunks)} changed hunks — "
            f"**{len(comments)} finding(s)**.\n\n"
            "_These are suggestions from a model, not a gate. "
            "Resolve or dismiss as you see fit._"
        )
    else:
        body = (
            f"Automated review of {len(hunks)} changed hunks — no issues found.\n\n"
            "_Checked for bugs, security, resource leaks and correctness. "
            "Style was deliberately not reviewed._"
        )

    if failures:
        body += f"\n\n<sub>{failures} hunk(s) could not be reviewed.</sub>"

    post_review(repo, pr_number, body, comments)
    print(f"posted review with {len(comments)} comments")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # Never fail the build because the reviewer had a bad day.
        print(f"review bot error: {e}", file=sys.stderr)
        sys.exit(0)
