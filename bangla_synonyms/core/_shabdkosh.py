"""
core/_shabdkosh.py
------------------
Synonym scraper for shabdkosh.com — Bangla dictionary.
Internal module. Not part of public API.

Source
------
Site    : https://www.shabdkosh.com
URL     : https://www.shabdkosh.com/search-dictionary?lc=bn&sl=en&tl=bn&e={word}

HTML structure
--------------
<p class="synonyms-list synsl text-muted mb-1 fs-5">
    <span class="ensyn">আঁখি</span>,
    <span class="ensyn">চক্ষু</span>,
    ...
</p>

Parse strategy
--------------
সব <span class="ensyn"> এর text নাও।
একটা page এ একাধিক synonym block থাকতে পারে।

Contract
--------
fetch_shabdkosh(word, session, timeout)
    -> list[str]   -- synonyms found (may be [])
    -> None        -- network / HTTP error
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

# ── Constants ─────────────────────────────────────────────────

_URL = "https://www.shabdkosh.com/search-dictionary?lc=bn&sl=en&tl=bn&e={word}"
_BN_RE = re.compile(r"[\u0980-\u09FF]")

log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────


def _is_bangla(text: str) -> bool:
    return bool(_BN_RE.search(text))


# ── Public fetch function ─────────────────────────────────────


def fetch_shabdkosh(word: str, session, timeout: int = 10) -> list | None:
    """
    shabdkosh.com থেকে synonym fetch করে।

    Returns list[str] or None on network error.
    """
    import requests

    url = _URL.format(word=quote(word))
    log.debug("[shabdkosh] fetching '%s'", word)

    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        log.warning("[shabdkosh] request timed out for '%s'", word)
        return None
    except requests.exceptions.ConnectionError:
        log.warning("[shabdkosh] connection error for '%s'", word)
        return None
    except requests.exceptions.HTTPError as e:
        log.warning("[shabdkosh] HTTP %s for '%s'", e.response.status_code, word)
        return []
    except requests.exceptions.RequestException as e:
        log.warning("[shabdkosh] request failed for '%s': %s", word, e)
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    synonyms = []
    seen = set()

    for span in soup.find_all("span", class_="ensyn"):
        w = span.get_text().strip()
        if _is_bangla(w) and w != word and w not in seen:
            seen.add(w)
            synonyms.append(w)
            log.debug("[shabdkosh] found: '%s'", w)

    log.debug("[shabdkosh] '%s' -> %s", word, synonyms)
    return synonyms
