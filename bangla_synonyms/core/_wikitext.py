# """
# core/_wikitext.py
# -----------------
# Internal scraping helpers shared by Scrapper and core modules.
# Not part of public API — import from bangla_synonyms or bangla_synonyms.core instead.
# """
# from __future__ import annotations

# import re
# import time
# from urllib.parse import quote

# import requests
# from bs4 import BeautifulSoup

# _API_URL     = "https://bn.wiktionary.org/w/api.php"
# _WIKI_BASE   = "https://bn.wiktionary.org/wiki"
# _USER_AGENT  = "bangla-synonyms/1.0 (Bangla NLP; github.com/bangla-nlp/bangla-synonyms)"
# _SYN_HEADERS = ["সমার্থক শব্দ", "সমার্থক", "প্রতিশব্দ"]
# _BN_RE       = re.compile(r"[\u0980-\u09FF]")
# _TEMPLATE_RE = re.compile(r"\{\{l\|bn\|([^\}|]+)")
# _WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")
# _BANGLA_WORD = re.compile(r"^[\u0980-\u09FF\s।্ঁ-ঃ]+$")


# def make_session() -> requests.Session:
#     from requests.adapters import HTTPAdapter
#     from urllib3.util.retry import Retry
#     s = requests.Session()
#     s.headers["User-Agent"] = _USER_AGENT
#     retry = Retry(total=2, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503])
#     s.mount("https://", HTTPAdapter(max_retries=retry))
#     return s


# def fetch_synonyms(word: str, session: requests.Session, timeout: int = 10) -> list[str] | None:
#     """
#     Fetch synonyms for one word.
#     Returns:
#         list[str]  — synonyms (may be empty [])
#         None       — network error
#     """
#     result = _wikitext(word, session, timeout)
#     if result is None:
#         return None
#     if result:
#         return result
#     return _html_fallback(word, session, timeout)


# def fetch_word_list(limit: int, session: requests.Session, timeout: int = 10) -> list[str]:
#     """Fetch list of Bangla words from Wiktionary allpages API."""
#     words  = []
#     params = {
#         "action": "query", "list": "allpages",
#         "apnamespace": 0, "aplimit": 500,
#         "apfrom": "অ", "format": "json", "formatversion": 2,
#     }
#     fetched = 0
#     while fetched < limit:
#         try:
#             data  = session.get(_API_URL, params=params, timeout=timeout).json()
#             pages = data.get("query", {}).get("allpages", [])
#             for p in pages:
#                 t = p.get("title", "")
#                 if _BANGLA_WORD.match(t.strip()):
#                     words.append(t)
#             fetched += len(pages)
#             cont = data.get("continue", {})
#             if "apcontinue" in cont and fetched < limit:
#                 params["apfrom"] = cont["apcontinue"]
#                 time.sleep(0.3)
#             else:
#                 break
#         except Exception:
#             break
#     return words


# def is_bangla(text: str) -> bool:
#     return bool(_BN_RE.search(text))


# # ── Private ───────────────────────────────────────────────────

# def _wikitext(word: str, session: requests.Session, timeout: int) -> list[str] | None:
#     try:
#         data = session.get(
#             _API_URL,
#             params={
#                 "action": "parse", "page": word,
#                 "prop": "wikitext", "format": "json", "formatversion": 2,
#             },
#             timeout=timeout,
#         ).json()
#     except Exception:
#         return None

#     if data.get("error", {}).get("code") == "missingtitle":
#         return []

#     wikitext = data.get("parse", {}).get("wikitext", "")
#     if not wikitext:
#         return []

#     synonyms   = []
#     in_section = False

#     for line in wikitext.split("\n"):
#         line = line.strip()
#         if any(h in line for h in _SYN_HEADERS):
#             in_section = True
#             continue
#         if in_section:
#             if re.match(r"^={2,5}[^=]", line):
#                 break
#             for m in _TEMPLATE_RE.finditer(line):
#                 w = m.group(1).strip()
#                 if is_bangla(w) and w != word:
#                     synonyms.append(w)
#             for m in _WIKILINK_RE.finditer(line):
#                 w = m.group(1).strip()
#                 if is_bangla(w) and w != word and w not in synonyms:
#                     synonyms.append(w)

#     return list(dict.fromkeys(synonyms))


# def _html_fallback(word: str, session: requests.Session, timeout: int) -> list[str]:
#     try:
#         resp = session.get(f"{_WIKI_BASE}/{quote(word)}", timeout=timeout)
#         if resp.status_code != 200:
#             return []
#     except Exception:
#         return []

#     soup     = BeautifulSoup(resp.text, "lxml")
#     synonyms = []

#     for span in soup.find_all("span", class_="mw-headline"):
#         if any(h in span.get_text() for h in _SYN_HEADERS):
#             sibling = span.find_parent().find_next_sibling()
#             while sibling and sibling.name not in ("h2", "h3", "h4"):
#                 if sibling.name == "ul":
#                     for li in sibling.find_all("li"):
#                         for a in li.find_all("a"):
#                             w = a.get_text().strip()
#                             if is_bangla(w) and w != word:
#                                 synonyms.append(w)
#                         if not li.find("a"):
#                             for p in li.get_text().split(","):
#                                 w = p.strip()
#                                 if is_bangla(w) and w != word:
#                                     synonyms.append(w)
#                 sibling = sibling.find_next_sibling()

#     return list(dict.fromkeys(synonyms))




"""
core/_wikitext.py
-----------------
Internal scraping helpers shared by Scrapper and core modules.
Not part of public API — import from bangla_synonyms or bangla_synonyms.core instead.
"""
from __future__ import annotations

import re
import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

_API_URL     = "https://bn.wiktionary.org/w/api.php"
_WIKI_BASE   = "https://bn.wiktionary.org/wiki"
_USER_AGENT  = "bangla-synonyms/1.0 (Bangla NLP; github.com/bangla-nlp/bangla-synonyms)"
_SYN_HEADERS = ["সমার্থক শব্দ", "সমার্থক", "প্রতিশব্দ"]
_BN_RE       = re.compile(r"[\u0980-\u09FF]")
_TEMPLATE_RE = re.compile(r"\{\{l\|bn\|([^\}|]+)")
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")
_BANGLA_WORD = re.compile(r"^[\u0980-\u09FF\s।্ঁ-ঃ]+$")


def make_session() -> requests.Session:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    s = requests.Session()
    s.headers["User-Agent"] = _USER_AGENT
    retry = Retry(total=2, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def fetch_synonyms(word: str, session: requests.Session, timeout: int = 10) -> list[str] | None:
    """
    Fetch synonyms for one word.
    Returns:
        list[str]  — synonyms (may be empty [])
        None       — network error
    """
    # print(f"  [fetch_synonyms] '{word}' — trying wikitext API first...")

    result = _wikitext(word, session, timeout)

    # print(f"  [fetch_synonyms] wikitext returned → {result!r}")

    if result is None:
        # print(f"  [fetch_synonyms] wikitext gave None (network error) → returning None")
        return None

    if result:
        # print(f"  [fetch_synonyms] wikitext succeeded → returning {result}")
        return result

    # wikitext returned [] — try HTML fallback
    # print(f"  [fetch_synonyms] wikitext returned empty [] → trying HTML fallback...")
    html_result = _html_fallback(word, session, timeout)
    # print(f"  [fetch_synonyms] HTML fallback returned → {html_result!r}")
    return html_result


def fetch_word_list(limit: int, session: requests.Session, timeout: int = 10) -> list[str]:
    """Fetch list of Bangla words from Wiktionary allpages API."""
    words  = []
    params = {
        "action": "query", "list": "allpages",
        "apnamespace": 0, "aplimit": 500,
        "apfrom": "অ", "format": "json", "formatversion": 2,
    }
    fetched = 0
    while fetched < limit:
        try:
            data  = session.get(_API_URL, params=params, timeout=timeout).json()
            pages = data.get("query", {}).get("allpages", [])
            for p in pages:
                t = p.get("title", "")
                if _BANGLA_WORD.match(t.strip()):
                    words.append(t)
            fetched += len(pages)
            cont = data.get("continue", {})
            if "apcontinue" in cont and fetched < limit:
                params["apfrom"] = cont["apcontinue"]
                time.sleep(0.3)
            else:
                break
        except Exception:
            break
    return words


def is_bangla(text: str) -> bool:
    return bool(_BN_RE.search(text))


# ── Private ───────────────────────────────────────────────────

def _wikitext(word: str, session: requests.Session, timeout: int) -> list[str] | None:
    url = f"{_API_URL}?action=parse&page={word}&prop=wikitext&format=json&formatversion=2"
    # print(f"    [wikitext] GET {url}")

    try:
        resp = session.get(
            _API_URL,
            params={
                "action": "parse", "page": word,
                "prop": "wikitext", "format": "json", "formatversion": 2,
            },
            timeout=timeout,
        )
        # print(f"    [wikitext] HTTP status → {resp.status_code}")
        data = resp.json()
    except Exception as e:
        # print(f"    [wikitext] request failed → {e}")
        return None

    # page not found on Wiktionary
    error_code = data.get("error", {}).get("code")
    if error_code == "missingtitle":
        # print(f"    [wikitext] page '{word}' does not exist on Wiktionary → []")
        return []

    wikitext = data.get("parse", {}).get("wikitext", "")
    if not wikitext:
        # print(f"    [wikitext] page exists but wikitext is empty → []")
        return []

    # print(f"    [wikitext] got wikitext ({len(wikitext)} chars) — scanning for synonym section...")

    synonyms   = []
    in_section = False

    for line in wikitext.split("\n"):
        line = line.strip()
        if any(h in line for h in _SYN_HEADERS):
            # print(f"    [wikitext] found synonym section header: '{line}'")
            in_section = True
            continue
        if in_section:
            if re.match(r"^={2,5}[^=]", line):
                # print(f"    [wikitext] reached next section '{line}' — stopping scan")
                break

            found_on_line = []

            # method 1: {{l|bn|word}} templates
            for m in _TEMPLATE_RE.finditer(line):
                w = m.group(1).strip()
                if is_bangla(w) and w != word:
                    # print(f"    [wikitext] found via template: '{w}'")
                    found_on_line.append(w)
                    synonyms.append(w)

            # method 2: [[wikilink]] style
            for m in _WIKILINK_RE.finditer(line):
                w = m.group(1).strip()
                if is_bangla(w) and w != word and w not in synonyms:
                    # print(f"    [wikitext] found via wikilink: '{w}'")
                    found_on_line.append(w)
                    synonyms.append(w)

            # method 3: plain comma-separated bangla text
            # e.g. "বৃহৎ, প্রকাণ্ড, বিস্তৃত"  (no template or wikilink markup)
            if not found_on_line and line and is_bangla(line):
                for part in line.split(","):
                    w = re.sub(r"[*#;:\[\]\{\}|'']", "", part).strip()
                    if is_bangla(w) and w != word and w not in synonyms and len(w) > 1:
                        # print(f"    [wikitext] found via plain text: '{w}'")
                        synonyms.append(w)

    result = list(dict.fromkeys(synonyms))
    # print(f"    [wikitext] final synonyms → {result}")
    return result


def _html_fallback(word: str, session: requests.Session, timeout: int) -> list[str]:
    url = f"{_WIKI_BASE}/{quote(word)}"
    # print(f"    [html_fallback] GET {url}")

    try:
        resp = session.get(url, timeout=timeout)
        # print(f"    [html_fallback] HTTP status → {resp.status_code}")
        if resp.status_code != 200:
            # print(f"    [html_fallback] non-200 status → []")
            return []
    except Exception as e:
        # print(f"    [html_fallback] request failed → {e}")
        return []

    soup     = BeautifulSoup(resp.text, "lxml")
    synonyms = []

    for span in soup.find_all("span", class_="mw-headline"):
        if any(h in span.get_text() for h in _SYN_HEADERS):
            # print(f"    [html_fallback] found synonym section in HTML: '{span.get_text()}'")
            sibling = span.find_parent().find_next_sibling()
            while sibling and sibling.name not in ("h2", "h3", "h4"):
                if sibling.name == "ul":
                    for li in sibling.find_all("li"):
                        for a in li.find_all("a"):
                            w = a.get_text().strip()
                            if is_bangla(w) and w != word:
                                # print(f"    [html_fallback] found via <a>: '{w}'")
                                synonyms.append(w)
                        if not li.find("a"):
                            for p in li.get_text().split(","):
                                w = p.strip()
                                if is_bangla(w) and w != word:
                                    # print(f"    [html_fallback] found via text: '{w}'")
                                    synonyms.append(w)
                sibling = sibling.find_next_sibling()

    result = list(dict.fromkeys(synonyms))
    # print(f"    [html_fallback] final synonyms → {result}")
    return result