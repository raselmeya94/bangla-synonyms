

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
  E1 (section) {{l|bn|word}}              link template in synonym section
  E2 (section) [[wikilink]]               wikilink in synonym section
  E3 (section) * bare bullet              bullet item in synonym section
  E4 (section) plain comma text           "বৃহৎ, প্রকাণ্ড, বিস্তৃত" in section
  F  সমার্থক শব্দ: word1 (tr), word2     inline colon list with transliteration
  G  সমার্থক শব্দ: word                  inline colon single word
  H  #word1, word2                        definition line — bn.wiktionary often
                                          embeds synonyms directly in definition
                                          items when there is no synonym section.
     Sub-cases:
     H1  #শব্দ১, শব্দ২                   bare comma list
     H2  #[[শব্দ১]], [[শব্দ২]]           wikilinks inside definition
     H3  #{{l|bn|শব্দ১}}, ...            link templates inside definition
     H4  #(note) শব্দ১, শব্দ২            parenthetical note then words
     H5  #*শব্দ১, শব্দ২                  definition-synonym line (#*)
     Mixed sense-unit lines are also handled:
       # [[শ্লথ]], [[মন্থর]] ([[শিথিল]] গতি)। [[ক্লান্ত]]।
     Each sense unit (split by । and ,) contributes only the first
     [[wikilink]] BEFORE the opening parenthesis.  Links inside parens
     are example usages of the lookup word, not synonyms.
     Sentence definitions (#যে ব্যক্তি...) are rejected — only single
     Bangla tokens (no spaces) qualify as synonyms from definition lines.

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
_USER_AGENT = "bangla-synonyms/1.0 (Bangla NLP; github.com/raselmeya94/bangla-synonyms)"

_BN_RE       = re.compile(r"[\u0980-\u09FF]")
_BANGLA_WORD = re.compile(r"^[\u0980-\u09FF।্ঁ-ঃ]+$")
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

# Pattern H — definition line prefix: # or ## or #*
_DEF_LINE_RE     = re.compile(r"^#+\*?\s*")

# A synonym token must consist entirely of Bangla Unicode characters
# (including vowel signs, conjuncts, hasanta, anusvara, visarga).
# Tokens with spaces are sentence fragments — not synonyms.
_BANGLA_TOKEN_RE = re.compile(
    r"^[\u0980-\u09FF\u09BC\u09BE-\u09CC\u09CD\u09D7\u09E0-\u09E3]+$"
)

# Leading parenthetical note in a definition line, e.g. "(সমার্থক)" or "(অর্থ১)"
_LEADING_PAREN_RE = re.compile(r"^\([^)]*\)\s*")


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


def _is_synonym_token(token: str) -> bool:
    """
    Return True when ``token`` is a plausible single-word Bangla synonym.

    Accepts only strings that consist entirely of Bangla Unicode characters
    (no spaces, no Latin, no digits).  This rejects sentence-style definitions
    such as "যে ব্যক্তি লেখাপড়া জানে না" which appear on # definition lines
    alongside genuine comma-separated synonym lists.
    """
    t = token.strip()
    return bool(t and len(t) >= 2 and _BANGLA_TOKEN_RE.match(t))


def _split_outside_parens(text: str) -> list[str]:
    """
    Split ``text`` by ``,`` and ``।`` but not when inside parentheses.

    Used to break a definition line into individual sense units without
    splitting on commas that are part of parenthetical example phrases,
    e.g. ``[[মন্থর]] ([[শিথিল]] গতি)`` must stay together as one unit so
    that the ``([[শিথিল]] গতি)`` part is recognized as a paren block and
    the inner link is not mistakenly extracted as a synonym.
    """
    parts: list[str] = []
    depth   = 0
    current: list[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            current.append(ch)
        elif ch in (",", "।") and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def _extract_def_synonyms(line: str, word: str, seen: list) -> list:
    """
    Extract synonyms from a definition line (H patterns).

    Handles:
    - ``#শব্দ১, শব্দ২``                                    bare comma list       (H1)
    - ``#[[শব্দ১]], [[শব্দ২]]``                            wikilinks             (H2)
    - ``#{{l|bn|শব্দ১}}, {{l|bn|শব্দ২}}``                 link templates        (H3)
    - ``#(note) শব্দ১, শব্দ২``                             leading paren note    (H4)
    - ``#*শব্দ১, শব্দ২``                                   def-synonym marker    (H5)

    Also handles mixed sense-unit lines such as::

        # [[শ্লথ]], [[মন্থর]] ([[শিথিল]] গতি)। [[ক্লান্ত]]। [[ঢিলেঢালা]]।

    Strategy
    --------
    1. If ``{{l|bn|word}}`` templates are present, extract from them only
       (they are always explicit synonym markup — no ambiguity).
    2. Otherwise split the body into sense units using
       ``_split_outside_parens`` (splits on ``,`` and ``।`` but not inside
       parentheses).  For each unit, take the first wikilink that appears
       **before** any opening parenthesis.  Links inside parens are
       example uses of the lookup word (e.g. ``([[শিথিল]] গতি)``), not
       synonyms, and are intentionally skipped.
    3. If no links are found in a unit, treat the pre-paren text as a
       plain Bangla token.

    Sentence definitions (e.g. ``#যে ব্যক্তি লেখাপড়া জানে না``) are
    rejected because their tokens contain spaces and fail
    ``_is_synonym_token``.
    """
    # Strip the # / ## / #* prefix
    body = _DEF_LINE_RE.sub("", line.strip())
    if not body:
        return []

    # Strip a leading parenthetical note — "(সমার্থক)" "(অর্থ১)" etc.
    body = _LEADING_PAREN_RE.sub("", body).strip()

    result: list[str] = []

    # H3 — {{l|bn|word}} link templates (highest priority — unambiguous markup)
    for m in _LINK_TMPL_RE.finditer(body):
        w = m.group(1).strip()
        if _is_synonym_token(w) and w != word and w not in seen and w not in result:
            result.append(w)

    if result:
        return result

    # H1 / H2 / H4 — split into paren-aware sense units, then extract
    # the first [[wikilink]] before the opening paren of each unit.
    for unit in _split_outside_parens(body):
        unit = unit.strip()
        if not unit:
            continue

        # Isolate the part before any parenthetical example
        paren_pos    = unit.find("(")
        before_paren = unit[:paren_pos].strip() if paren_pos != -1 else unit

        # Prefer explicit [[wikilink]] in the before-paren section
        m = _WIKILINK_RE.search(before_paren)
        if m:
            w = m.group(1).strip()
            if _is_synonym_token(w) and w != word and w not in seen and w not in result:
                result.append(w)
        else:
            # No link markup — try plain Bangla token
            clean = re.sub(r"['''\"*#\[\]{}|।]", "", before_paren).strip()
            if _is_synonym_token(clean) and clean != word and clean not in seen and clean not in result:
                result.append(clean)

    return result


# ── Wikitext parser ───────────────────────────────────────────

def _parse_wikitext(word: str, wikitext: str) -> list:
    """
    Parse all known synonym patterns from Bangla Wiktionary wikitext.

    Two passes are made:

    Pass 1 — whole-page patterns
        Scans every line for template-based patterns (A–D, F–G) that appear
        anywhere in the page, and for definition lines (H) that carry synonyms
        when the page has no dedicated synonym section.

    Pass 2 — synonym-section patterns
        Re-scans the page and processes lines only within a section whose
        heading matches ``_SYN_HEADERS`` (E1–E4).

    Definition lines (H) are processed in Pass 1 only when no template-based
    synonyms (A–D, F–G) are found first.  This avoids duplicating entries
    for pages that have both a synonym section and a definition with synonyms.
    """
    synonyms: list[str] = []

    # ── Pass 1: whole-page patterns ───────────────────────────
    has_template_syns = False

    for line in wikitext.split("\n"):
        ls = line.strip()

        # A / B / C — block synonym templates
        for m in _BLOCK_SYN_RE.finditer(ls):
            for w in _pipe_words(m.group(1), word, synonyms):
                log.debug("[wiktionary] [A/B/C] '%s'", w)
                synonyms.append(w)
                has_template_syns = True

        # D — inline {{syn|bn|...}} template
        for m in _SYN_INLINE_RE.finditer(ls):
            for w in _pipe_words(m.group(1), word, synonyms):
                log.debug("[wiktionary] [D] '%s'", w)
                synonyms.append(w)
                has_template_syns = True

        # F / G — inline "সমার্থক শব্দ: ..." colon pattern
        m = _INLINE_COLON_RE.search(ls)
        if m:
            raw_after = m.group(1)
            if "=" not in raw_after:
                for w in _split_colon_list(raw_after, word, synonyms):
                    log.debug("[wiktionary] [F/G] '%s'", w)
                    synonyms.append(w)
                    has_template_syns = True

    # H — definition lines (only when no template synonyms found on the page).
    # bn.wiktionary often has pages like:
    #   ===বিশেষণ===
    #   #সমাপ্ত, পরিপূর্ণ
    # with no synonym section at all.  We extract from these only as a fallback
    # so as not to duplicate entries on pages that already have A–G coverage.
    if not has_template_syns:
        for line in wikitext.split("\n"):
            ls = line.strip()
            if re.match(r"^#", ls) and not re.match(r"^#\s*\{", ls):
                # Skip redirect lines like "#REDIRECT [[word]]"
                if re.match(r"^#\s*(?:REDIRECT|redirect)", ls):
                    continue
                for w in _extract_def_synonyms(ls, word, synonyms):
                    log.debug("[wiktionary] [H] '%s'", w)
                    synonyms.append(w)

    # ── Pass 2: synonym section only ──────────────────────────
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

        found_on_line: list[str] = []

        # E1 — {{l|bn|word}}
        for m in _LINK_TMPL_RE.finditer(ls):
            w = m.group(1).strip()
            if is_bangla(w) and w != word and w not in synonyms:
                log.debug("[wiktionary] [E1] '%s'", w)
                found_on_line.append(w)
                synonyms.append(w)

        # E2 — [[wikilink]]
        for m in _WIKILINK_RE.finditer(ls):
            w = m.group(1).strip()
            if is_bangla(w) and w != word and w not in synonyms:
                log.debug("[wiktionary] [E2] '%s'", w)
                found_on_line.append(w)
                synonyms.append(w)

        # E3 — * bullet item
        if re.match(r"^\*\s*", ls) and not found_on_line:
            body = re.sub(r"^\*+\s*", "", ls)
            for part in body.split(","):
                w = _clean_word(part)
                if is_bangla(w) and w != word and w not in synonyms and len(w) > 1:
                    log.debug("[wiktionary] [E3] '%s'", w)
                    found_on_line.append(w)
                    synonyms.append(w)

        # E4 — plain comma text line (no bullet, no template)
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
    Fetch synonyms from bn.wiktionary.org (wikitext API → HTML fallback).

    Returns
    -------
    list[str]
        Synonyms found (may be empty when the page exists but has no synonyms).
    None
        Network error — caller should treat this source as unavailable.
    """
    result = _fetch_wikitext_api(word, session, timeout)
    if result is None:
        return None
    if result:
        return result
    return _fetch_html_fallback(word, session, timeout)

def fetch_word_list(limit: int, session: requests.Session, timeout: int = 10) -> list:
    """
    Fetch up to ``limit`` single-word Bangla entries from the Wiktionary
    allpages API.

    Multi-word page titles (e.g. "অ আ ক খ", "অংশ করা") are filtered out
    by ``_BANGLA_WORD`` — only titles consisting entirely of Bangla Unicode
    characters with no spaces are included.

    Parameters
    ----------
    limit : int
        Maximum number of words to return.  The function stops as soon as
        ``limit`` valid words have been collected, even if the current API
        batch contained more pages.
    session : requests.Session
        A retry-enabled session created by ``make_session()``.
    timeout : int, default 10
        HTTP request timeout in seconds per API call.

    Returns
    -------
    list[str]
        At most ``limit`` Bangla word strings, in Wiktionary page order.
    """
    words:  list[str] = []
    params: dict      = {
        "action": "query", "list": "allpages",
        "apnamespace": 0, "aplimit": 500,
        "apfrom": "অ", "format": "json", "formatversion": 2,
    }

    while len(words) < limit:
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
            t = p.get("title", "").strip()
            if _BANGLA_WORD.match(t):
                words.append(t)
                if len(words) >= limit:
                    break

        cont = data.get("continue", {})
        if "apcontinue" in cont and len(words) < limit:
            params["apfrom"] = cont["apcontinue"]
            time.sleep(0.3)
        else:
            break

    return words


# def fetch_word_list(limit: int, session: requests.Session, timeout: int = 10) -> list:
    """Fetch a list of Bangla words from the Wiktionary allpages API."""
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