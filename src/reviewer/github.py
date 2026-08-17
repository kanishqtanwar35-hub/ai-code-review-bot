"""GitHub REST client — fetch the PR diff, post one review.

Posting a single review with many comments (rather than N separate comments)
means the PR shows one notification instead of twelve. Reviewers care about
this more than they care about the findings.
"""

import os
from typing import Dict, List

import requests

API = "https://api.github.com"


def _headers(accept: str = "application/vnd.github+json") -> Dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_pr_diff(repo: str, pr_number: int) -> str:
    r = requests.get(
        f"{API}/repos/{repo}/pulls/{pr_number}",
        headers=_headers("application/vnd.github.v3.diff"),
        timeout=30,
    )
    r.raise_for_status()
    return r.text


def get_pr_head_sha(repo: str, pr_number: int) -> str:
    r = requests.get(
        f"{API}/repos/{repo}/pulls/{pr_number}", headers=_headers(), timeout=30
    )
    r.raise_for_status()
    return r.json()["head"]["sha"]


def post_review(repo: str, pr_number: int, body: str, comments: List[dict]) -> dict:
    """Post one review. `comments` use {path, line, side, body}."""
    payload = {
        "commit_id": get_pr_head_sha(repo, pr_number),
        "body": body,
        "event": "COMMENT",          # never auto-REQUEST_CHANGES from a bot
        "comments": comments,
    }
    r = requests.post(
        f"{API}/repos/{repo}/pulls/{pr_number}/reviews",
        headers=_headers(),
        json=payload,
        timeout=30,
    )

    # If a line is not part of the diff GitHub rejects the whole review.
    # Fall back to a summary-only comment rather than losing the findings.
    if r.status_code == 422 and comments:
        summary = body + "\n\n" + "\n".join(
            f"- `{c['path']}:{c['line']}` — {c['body']}" for c in comments
        )
        r = requests.post(
            f"{API}/repos/{repo}/issues/{pr_number}/comments",
            headers=_headers(),
            json={"body": summary},
            timeout=30,
        )

    r.raise_for_status()
    return r.json()
