"""
core/_wikitext.py
-----------------
Synonym scraper for bn.wiktionary.org.
Internal module. Not part of public API.

Handles all known bn.wiktionary.org synonym patterns:

  A  {{স|bn|চক্ষু|নেত্র|...}}            standalone block template
  B  {{s|bn|জল|বারি|...}}                 lowercase shorthand of A
  C  {{সমার্থক|bn|তটিনী|...}}            alternate block template
  D  {{syn|bn|খুবসুরত|tr2=x|g=y|...}}    inline syn with named-param skipping
  E1 (section) {{l|bn|word}}              link template
  E2 (section) [[wikilink]]               wikilink
  E3 (section) * bare bullet              bullet item (may be comma list)
  E4 (section) plain comma text           "বৃহৎ, প্রকাণ্ড, বিস্তৃত"
  F  সমার্থক শব্দ: word1 (tr), word2     inline colon list with transliteration
  G  সমার্থক শব্দ: word                  inline colon single word

Contract
--------
fetch_synonyms(word, session, timeout)
    -> list[str]   -- synonyms found (may be [])
    -> None        -- network error
"""
from __future__ import annotations

import logging
import re
import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

# ── Constants ─────────────────────────────────────────────────

_API_URL    = "https://bn.wiktionary.org/w/api.php"
_WIKI_BASE  = "https://bn.wiktionary.org/wiki"
_USER_AGENT = "bangla-synonyms/1.0 (Bangla NLP; github.com/bangla-nlp/bangla-synonyms)"

_BN_RE       = re.compile(r"[\u0980-\u09FF]")
_BANGLA_WORD = re.compile(r"^[\u0980-\u09FF\s।্ঁ-ঃ]+$")
_SYN_HEADERS = ["সমার্থক শব্দ", "সমার্থক", "প্রতিশব্দ"]

log = logging.getLogger(__name__)

# ── Compiled regexes ──────────────────────────────────────────

_BLOCK_SYN_RE    = re.compile(r"\{\{(?:স|s|সমার্থক)\|bn\|([^}]+)\}\}")
_SYN_INLINE_RE   = re.compile(r"\{\{syn\|bn\|([^}]+)\}\}")
_LINK_TMPL_RE    = re.compile(r"\{\{l\|bn\|([^|}]+)")
_WIKILINK_RE     = re.compile(r"\[\[([^\]|#]+)\]\]")
_INLINE_COLON_RE = re.compile(
    r"(?:সমার্থক শব্দ|সমার্থক|প্রতিশব্দ)\s*[:\-]\s*(.+)"
)
_PAREN_TR_RE     = re.compile(r"\([^)]*\)")


# ── Session factory ───────────────────────────────────────────

def make_session() -> requests.Session:
    """Retry-enabled session with package User-Agent."""
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    s = requests.Session()
    s.headers["User-Agent"] = _USER_AGENT
    retry = Retry(total=2, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


# ── Helpers ───────────────────────────────────────────────────

def is_bangla(text: str) -> bool:
    return bool(_BN_RE.search(text))


def _pipe_words(raw: str, word: str, seen: list) -> list:
    result = []
    for part in raw.split("|"):
        part = part.strip()
        if "=" in part:
            continue
        if is_bangla(part) and part != word and part not in seen:
            result.append(part)
    return result


def _clean_word(text: str) -> str:
    text = _PAREN_TR_RE.sub("", text)
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    text = re.sub(r"\[\[([^\]|]+)[\]|].*?\]\]", r"\1", text)
    text = re.sub(r"[*#;:\[\]{}|'''\"।,\d]", " ", text)
    return text.strip()


def _split_colon_list(raw: str, word: str, seen: list) -> list:
    result = []
    for part in re.split(r"[,;]", raw):
        w = _clean_word(part)
        for token in w.split():
            token = token.strip()
            if is_bangla(token) and token != word and token not in seen and len(token) > 1:
                result.append(token)
                break
    return result


# ── Wikitext parser ───────────────────────────────────────────

def _parse_wikitext(word: str, wikitext: str) -> list:
    synonyms = []

    # Pass 1: whole-page patterns
    for line in wikitext.split("\n"):
        ls = line.strip()

        for m in _BLOCK_SYN_RE.finditer(ls):
            for w in _pipe_words(m.group(1), word, synonyms):
                log.debug("[wiktionary] [A/B/C] '%s'", w)
                synonyms.append(w)

        for m in _SYN_INLINE_RE.finditer(ls):
            for w in _pipe_words(m.group(1), word, synonyms):
                log.debug("[wiktionary] [D] '%s'", w)
                synonyms.append(w)

        m = _INLINE_COLON_RE.search(ls)
        if m:
            raw_after = m.group(1)
            if "=" not in raw_after:
                for w in _split_colon_list(raw_after, word, synonyms):
                    log.debug("[wiktionary] [F/G] '%s'", w)
                    synonyms.append(w)

    # Pass 2: synonym section only
    in_section = False
    for line in wikitext.split("\n"):
        ls = line.strip()

        if any(h in ls for h in _SYN_HEADERS) and re.search(r"={2,5}", ls):
            in_section = True
            continue

        if in_section and re.match(r"^={2,5}[^=]", ls):
            in_section = False
            continue

        if not in_section:
            continue

        found_on_line = []

        for m in _LINK_TMPL_RE.finditer(ls):
            w = m.group(1).strip()
            if is_bangla(w) and w != word and w not in synonyms:
                log.debug("[wiktionary] [E1] '%s'", w)
                found_on_line.append(w)
                synonyms.append(w)

        for m in _WIKILINK_RE.finditer(ls):
            w = m.group(1).strip()
            if is_bangla(w) and w != word and w not in synonyms:
                log.debug("[wiktionary] [E2] '%s'", w)
                found_on_line.append(w)
                synonyms.append(w)

        if re.match(r"^\*\s*", ls) and not found_on_line:
            body = re.sub(r"^\*+\s*", "", ls)
            for part in body.split(","):
                w = _clean_word(part)
                if is_bangla(w) and w != word and w not in synonyms and len(w) > 1:
                    log.debug("[wiktionary] [E3] '%s'", w)
                    found_on_line.append(w)
                    synonyms.append(w)

        if not found_on_line and ls and is_bangla(ls) and not ls.startswith("{"):
            for part in ls.split(","):
                w = _clean_word(part)
                if is_bangla(w) and w != word and w not in synonyms and len(w) > 1:
                    log.debug("[wiktionary] [E4] '%s'", w)
                    synonyms.append(w)

    return list(dict.fromkeys(synonyms))


# ── API calls ─────────────────────────────────────────────────

def _fetch_wikitext_api(word: str, session: requests.Session, timeout: int) -> list | None:
    try:
        resp = session.get(
            _API_URL,
            params={
                "action": "parse", "page": word,
                "prop": "wikitext", "format": "json", "formatversion": 2,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        log.warning("[wiktionary] request timed out for '%s'", word)
        return None
    except requests.exceptions.ConnectionError:
        log.warning("[wiktionary] connection error for '%s'", word)
        return None
    except requests.exceptions.RequestException as e:
        log.warning("[wiktionary] request failed for '%s': %s", word, e)
        return None
    except ValueError:
        log.warning("[wiktionary] invalid JSON response for '%s'", word)
        return None

    err = data.get("error", {})
    if err.get("code") == "missingtitle":
        return []
    if err:
        log.warning("[wiktionary] API error for '%s': %s", word, err.get("info", err))
        return []

    wikitext = data.get("parse", {}).get("wikitext", "")
    if not wikitext:
        return []

    return _parse_wikitext(word, wikitext)


def _fetch_html_fallback(word: str, session: requests.Session, timeout: int) -> list:
    url = f"{_WIKI_BASE}/{quote(word)}"
    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        log.warning("[wiktionary] HTML fallback timed out for '%s'", word)
        return []
    except requests.exceptions.RequestException as e:
        log.warning("[wiktionary] HTML fallback failed for '%s': %s", word, e)
        return []

    soup     = BeautifulSoup(resp.text, "lxml")
    synonyms = []

    for span in soup.find_all("span", class_="mw-headline"):
        if any(h in span.get_text() for h in _SYN_HEADERS):
            sibling = span.find_parent().find_next_sibling()
            while sibling and sibling.name not in ("h2", "h3", "h4"):
                if sibling.name == "ul":
                    for li in sibling.find_all("li"):
                        for a in li.find_all("a"):
                            w = a.get_text().strip()
                            if is_bangla(w) and w != word:
                                synonyms.append(w)
                        if not li.find("a"):
                            for p in li.get_text().split(","):
                                w = p.strip()
                                if is_bangla(w) and w != word:
                                    synonyms.append(w)
                sibling = sibling.find_next_sibling()

    return list(dict.fromkeys(synonyms))


# ── Public function ───────────────────────────────────────────

def fetch_synonyms(word: str, session: requests.Session, timeout: int = 10) -> list | None:
    """
    Wiktionary থেকে synonym fetch করে (wikitext API -> HTML fallback).

    Returns list[str] or None on network error.
    """
    result = _fetch_wikitext_api(word, session, timeout)
    if result is None:
        return None
    if result:
        return result
    return _fetch_html_fallback(word, session, timeout)


def fetch_word_list(limit: int, session: requests.Session, timeout: int = 10) -> list:
    """Wiktionary allpages API থেকে Bangla শব্দের list বের করে।"""
    words  = []
    params = {
        "action": "query", "list": "allpages",
        "apnamespace": 0, "aplimit": 500,
        "apfrom": "অ", "format": "json", "formatversion": 2,
    }
    fetched = 0

    while fetched < limit:
        try:
            resp = session.get(_API_URL, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            log.warning("[wiktionary] word list fetch failed: %s", e)
            break
        except ValueError:
            log.warning("[wiktionary] invalid JSON in word list response")
            break

        pages = data.get("query", {}).get("allpages", [])
        for p in pages:
            t = p.get("title", "")
            if _BANGLA_WORD.match(t.strip()):
                words.append(t)

        fetched += len(pages)
        cont     = data.get("continue", {})
        if "apcontinue" in cont and fetched < limit:
            params["apfrom"] = cont["apcontinue"]
            time.sleep(0.3)
        else:
            break

    return words