"""
bangla_synonyms.core._quality
------------------------------
Post-processing pipeline — noise filtering + cross-source validation.

যা করে
------
1. **Noise filter** (`_is_clean`)
   প্রতিটা candidate synonym চেক করে:
   - Multi-word phrase বাদ (e.g. "ভালচোখ-  নীরোগ চোখ", "সাদা চোখ - স্বাভাবিক দৃষ")
   - Descriptive/numbered entries বাদ (e.g. "১.  জননী", "কন্যাস্থানীয়া নারীকে সম্বোধন")
   - Special characters বাদ (dash, hyphen, numbers, ZWJ, ZWNJ)
   - Too short / too long বাদ
   - শব্দটা নিজেই synonym হলে বাদ

2. **Cross-source validation** (`apply_quality`)
   Wiktionary আছে কিনা তার উপর ভিত্তি করে দুটো পথ:

   Path A — Wiktionary present:
     - Wiktionary এর সব clean entries রাখো (authoritative)
     - বাকি sources থেকে শুধু সেগুলো রাখো যেগুলো wiktionary তেও আছে
       (cross-confirmed → high accuracy)

   Path B — Wiktionary absent:
     - সব sources এর clean entries নাও
     - কমপক্ষে 2টা source এ আছে এমন শব্দগুলো রাখো
     - যদি সব entries single-source হয় (মাত্র একটাই source ছিল),
       তাহলে সেগুলোই রাখো — কোনো option নেই

Public API
----------
    apply_quality(raw_result: dict) -> dict

    raw_result এ ``results`` list এবং ``word`` থাকতে হবে।
    Return করে filtered & annotated dict (same shape, নতুন key ``"quality"`` সহ)।
"""
from __future__ import annotations

import re
import unicodedata
import logging

log = logging.getLogger(__name__)

# ── Bangla Unicode range ───────────────────────────────────────
_BN_CHAR  = re.compile(r"[\u0980-\u09FF]")   # any Bangla character

# Characters that indicate a phrase / noise
_NOISE_CHARS = re.compile(
    r"[0-9"             # digits
    r"\-–—"             # dashes / hyphens
    r"\u200b-\u200f"    # zero-width chars (ZWJ, ZWNJ, etc.)
    r"\u00ad"           # soft hyphen
    r"।॥"               # sentence-end marks
    r"\(\)\[\]]"        # brackets
    r"/"                # slash
    r","                # comma inside a token
    r";"                # semicolon
    r"]",
    re.UNICODE,
)

# Patterns that strongly indicate a descriptive phrase, not a synonym
_DESCRIPTIVE_RE = re.compile(
    r"^\d"              # starts with digit  "১. জননী"
    r"|[a-zA-Z]"        # contains Latin     "নীরোগ eye"
    r"|\s{2,}"          # double spaces      "ভালচোখ-  নীরোগ"
)

# Maximum word count in a valid synonym (single token preferred; allow 2 for compounds)
_MAX_TOKENS  = 2
# Character length bounds for a single Bangla word
_MIN_LEN     = 2
_MAX_LEN     = 20


def _bangla_token_count(text: str) -> int:
    """Whitespace-split token count (ignoring empty strings)."""
    return len([t for t in text.split() if t])


def _is_clean(word: str, lookup_word: str) -> bool:
    """
    Return True if `word` is a plausible single-word Bangla synonym.

    Rejects
    -------
    - Same as the lookup word
    - Contains noise characters (digits, dashes, ZWJ, …)
    - Descriptive phrase pattern (starts with digit, has Latin chars, double spaces)
    - More than _MAX_TOKENS whitespace-separated tokens
    - Too short or too long
    - No Bangla characters at all
    """
    w = word.strip()

    if not w:
        return False

    # must differ from the word being looked up
    if w == lookup_word:
        return False

    # must contain at least one Bangla character
    if not _BN_CHAR.search(w):
        return False

    # noise character check
    if _NOISE_CHARS.search(w):
        return False

    # descriptive pattern check
    if _DESCRIPTIVE_RE.search(w):
        return False

    # token count — allow "মনোরম্য" (1) or "মনোরম্য অভিরমণীয়" (2 max)
    if _bangla_token_count(w) > _MAX_TOKENS:
        return False

    # length guard on the full string (strip spaces)
    bare = w.replace(" ", "")
    if len(bare) < _MIN_LEN or len(bare) > _MAX_LEN:
        return False

    return True


def apply_quality(raw: dict) -> dict:
    """
    Raw scrape result এ quality filter + cross-source validation apply করে।

    Parameters
    ----------
    raw : dict — ``fetch_with_sources_raw()`` এর return value

    Returns
    -------
    dict — same shape as input, with:
        ``"results"``  filtered list of ``{"synonym", "source"}``
        ``"words"``    updated flat list
        ``"quality"``  new key describing what strategy was used:
                       ``"wikiconfirmed"``  — wiktionary present, others cross-checked
                       ``"cross_source"``   — no wiktionary, ≥2 source agreement
                       ``"single_source"``  — only one source available, cleaned only
                       ``"empty"``          — nothing survived filtering

    Strategy
    --------
    **Path A — wiktionary present:**
        Keep ALL clean wiktionary entries.
        From other sources, keep ONLY entries that also appear in the wiktionary set.
        This gives high-precision synonyms: wiktionary confirmed, secondarily validated.

    **Path B — wiktionary absent:**
        Collect all clean entries.
        Keep entries that appear in ≥2 sources (cross-source agreement).
        If every entry is single-source (only 1 source total), keep all cleaned entries.
    """
    word    = raw.get("word", "")
    entries = raw.get("results", [])

    # ── Step 1: clean every entry ─────────────────────────────
    cleaned: list[dict] = []
    for entry in entries:
        syn = entry.get("synonym", "").strip()
        src = entry.get("source", "")
        if _is_clean(syn, word):
            cleaned.append({"synonym": syn, "source": src})
        else:
            log.debug("[quality] dropped '%s' (source=%s) for '%s'", syn, src, word)

    if not cleaned:
        return {**raw, "results": [], "words": [], "quality": "empty"}

    # ── Step 2: group by source ───────────────────────────────
    by_source: dict[str, set[str]] = {}
    for entry in cleaned:
        src = entry["source"]
        by_source.setdefault(src, set()).add(entry["synonym"])

    sources_present = set(by_source.keys())

    # ── Path A: wiktionary present ────────────────────────────
    if "wiktionary" in sources_present:

        # Count total source appearances for every clean word
        # (across ALL sources including wiktionary)
        word_sources: dict[str, set[str]] = {}
        for entry in cleaned:
            syn = entry["synonym"]
            word_sources.setdefault(syn, set()).add(entry["source"])

        final: list[dict] = []
        seen:  set[str]   = set()

        # 1. All wiktionary entries — always kept (authoritative)
        for entry in cleaned:
            if entry["source"] == "wiktionary" and entry["synonym"] not in seen:
                final.append(entry)
                seen.add(entry["synonym"])

        # 2. Non-wiki entries that appear in ≥2 sources total
        #    (w+s, w+eb, s+eb — any combination counts)
        for entry in cleaned:
            if entry["source"] == "wiktionary":
                continue
            syn = entry["synonym"]
            if syn in seen:
                continue
            if len(word_sources.get(syn, set())) >= 2:
                final.append({**entry, "confirmed": True})
                seen.add(syn)

        quality = "wikiconfirmed"

    # ── Path B: no wiktionary ─────────────────────────────────
    else:
        # count how many sources each synonym appears in
        syn_sources: dict[str, list[str]] = {}
        for entry in cleaned:
            syn = entry["synonym"]
            src = entry["source"]
            syn_sources.setdefault(syn, [])
            if src not in syn_sources[syn]:
                syn_sources[syn].append(src)

        multi = {syn for syn, srcs in syn_sources.items() if len(srcs) >= 2}

        if multi:
            # keep only cross-source confirmed
            seen = set()
            final = []
            for entry in cleaned:
                syn = entry["synonym"]
                if syn in multi and syn not in seen:
                    final.append({**entry, "confirmed": True})
                    seen.add(syn)
            quality = "cross_source"
        else:
            # single source only — return all cleaned (no choice)
            seen  = set()
            final = []
            for entry in cleaned:
                syn = entry["synonym"]
                if syn not in seen:
                    final.append(entry)
                    seen.add(syn)
            quality = "single_source"

    log.debug(
        "[quality] '%s': %d raw → %d after filtering (strategy=%s)",
        word, len(entries), len(final), quality,
    )

    return {
        **raw,
        "results": final,
        "words":   [e["synonym"] for e in final],
        "quality": quality,
    }