"""URL detection utility — extract the first URL found in a free-text task string."""

from __future__ import annotations

import re

# Matches http/https URLs including paths, query strings, and fragments.
_URL_RE = re.compile(
    r"https?://"                   # scheme
    r"(?:[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+)",  # everything after scheme
    re.IGNORECASE,
)


def extract_url(text: str) -> str | None:
    """Return the first URL found in *text*, or ``None`` if none present."""
    match = _URL_RE.search(text)
    return match.group(0) if match else None
