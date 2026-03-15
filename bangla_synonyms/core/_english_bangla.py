"""
core/_english_bangla.py
-----------------------
Synonym scraper for english-bangla.com (bn->bn dictionary).
Internal module. Not part of public API.

Source
------
Site    : https://www.english-bangla.com
URL     : https://www.english-bangla.com/bntobn/index/{word}

HTML structure
--------------
<div class="word-base b2b text-center">
    <strong><span class="stl3">রচনা</span></strong>
    <span class="format1">
        /<span style="...">বিশেষ্য পদ</span>/
        রচন, বিন্যাস, সাজানো; নির্মাণ, গঠন;
    </span>
</div>

Parse strategy
--------------
1. <span class="format1"> খোঁজো
2. Inner <span> (pos label) সরাও
3. "/pos/" markers বাদ দাও
4. "," এবং ";" দিয়ে split
5. Bangla token রাখো (len 2-30)

Note
----
এই site pure synonym দেয় না — related words / near-synonyms দেয়।
তাই এটা সবার শেষে last-resort হিসেবে ব্যবহার করা হয়।

Contract
--------
fetch_english_bangla(word, session, timeout)
    -> list[str]   -- words found (may be [])
    -> None        -- network / HTTP error
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

# ── Constants ─────────────────────────────────────────────────

_URL = "https://www.english-bangla.com/bntobn/index/{word}"
_BN_RE = re.compile(r"[\u0980-\u09FF]")
_POS_RE = re.compile(r"/[^/]*/")  # "/বিশেষ্য পদ/" pos markers

log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────


def _is_bangla(text: str) -> bool:
    return bool(_BN_RE.search(text))


# ── Public fetch function ─────────────────────────────────────


def fetch_english_bangla(word: str, session, timeout: int = 10) -> list | None:
    """
    english-bangla.com (bn->bn) থেকে related words fetch করে।

    Returns list[str] or None on network error.
    """
    import requests

    url = _URL.format(word=quote(word))
    log.debug("[english-bangla] fetching '%s'", word)

    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        log.warning("[english-bangla] request timed out for '%s'", word)
        return None
    except requests.exceptions.ConnectionError:
        log.warning("[english-bangla] connection error for '%s'", word)
        return None
    except requests.exceptions.HTTPError as e:
        log.warning("[english-bangla] HTTP %s for '%s'", e.response.status_code, word)
        return []
    except requests.exceptions.RequestException as e:
        log.warning("[english-bangla] request failed for '%s': %s", word, e)
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    synonyms = []
    seen = set()

    for block in soup.find_all("div", class_="word-base"):
        fmt = block.find("span", class_="format1")
        if not fmt:
            continue

        # pos label inner spans সরাও
        for inner in fmt.find_all("span"):
            inner.decompose()

        raw = fmt.get_text()
        raw = _POS_RE.sub("", raw)

        for part in re.split(r"[,;।]", raw):
            w = part.strip().rstrip(".").strip()
            if _is_bangla(w) and w != word and w not in seen and 1 < len(w) < 30:
                seen.add(w)
                synonyms.append(w)
                log.debug("[english-bangla] found: '%s'", w)

    log.debug("[english-bangla] '%s' -> %s", word, synonyms)
    return synonyms
