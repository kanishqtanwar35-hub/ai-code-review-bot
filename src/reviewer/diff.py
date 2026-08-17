"""Parse a unified diff into reviewable hunks.

The bot must comment on the RIGHT line of the RIGHT file. GitHub's review API
addresses lines by their position in the diff, not by line number in the file,
which is the part everyone gets wrong the first time.
"""

from dataclasses import dataclass
from typing import List

from unidiff import PatchSet

# Files nobody wants an LLM opinion on.
SKIP_SUFFIXES = (
    ".lock", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf",
    ".min.js", ".min.css", ".map", ".woff", ".woff2", ".ttf",
)
# Generated files whose extension does not give them away.
SKIP_NAMES = (
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Pipfile.lock", "go.sum", "Cargo.lock", "composer.lock",
)
SKIP_PATHS = ("node_modules/", "dist/", "build/", "vendor/", ".venv/")


@dataclass
class Hunk:
    """One contiguous block of added lines, with enough context to review it."""

    path: str
    start_line: int          # line number in the new file
    body: str                # the added lines, with markers
    diff_position: int       # position within the file's patch (for the API)


def should_review(path: str) -> bool:
    if any(path.endswith(s) for s in SKIP_SUFFIXES):
        return False
    if path.rsplit("/", 1)[-1] in SKIP_NAMES:
        return False
    if any(p in path for p in SKIP_PATHS):
        return False
    return True


def extract_hunks(diff_text: str, max_hunks: int = 20) -> List[Hunk]:
    """Turn a unified diff into a list of reviewable hunks.

    Only ADDED lines are reviewed. Reviewing deletions produces comments about
    code that no longer exists, which is how these bots earn a reputation for
    being noise.
    """
    hunks: List[Hunk] = []
    patch = PatchSet(diff_text)

    for patched_file in patch:
        if patched_file.is_removed_file:
            continue
        if not should_review(patched_file.path):
            continue

        position = 0
        for hunk in patched_file:
            added: List[str] = []
            first_added_line = None
            first_added_position = None

            for line in hunk:
                position += 1
                if line.is_added:
                    if first_added_line is None:
                        first_added_line = line.target_line_no
                        first_added_position = position
                    added.append(f"{line.target_line_no}: {line.value.rstrip()}")

            if added and first_added_line is not None:
                hunks.append(
                    Hunk(
                        path=patched_file.path,
                        start_line=first_added_line,
                        body="\n".join(added),
                        diff_position=first_added_position,
                    )
                )

            if len(hunks) >= max_hunks:
                return hunks

    return hunks


def total_added_lines(diff_text: str) -> int:
    return sum(f.added for f in PatchSet(diff_text))
