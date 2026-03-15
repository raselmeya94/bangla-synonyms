"""
bangla_synonyms.core._quality
------------------------------
Post-processing pipeline: noise filtering + cross-source validation.

Two-stage process
-----------------
Stage 1 — Noise filter (``_is_clean``)
    Rejects each candidate synonym that:
    - Is a multi-word phrase (more than ``_MAX_TOKENS`` tokens)
    - Contains digits, Latin characters, dashes, zero-width chars, or brackets
    - Matches descriptive / numbered entry patterns
    - Is too short or too long
    - Contains no Bangla characters at all
    - Is identical to the word being looked up

    ``_MAX_TOKENS = 1`` enforces single-token synonyms.  This is intentionally
    strict: Shabdkosh in particular scrapes multiple word-senses per entry and
    returns multi-word glosses (e.g. "সুচি ছিদ্র" for the "eye of a needle"
    sense of চোখ).  Allowing two tokens lets those wrong-sense phrases through.

Stage 2 — Cross-source validation (``apply_quality``)
    Decides which cleaned entries to keep based on which sources contributed.

    Path A — Wiktionary IS present:
        • Keep ALL clean Wiktionary entries (authoritative, no cap).
        • Keep Shabdkosh entries ONLY when the same synonym already appears in
          the Wiktionary accepted set.  This is tighter than a simple cap:
          Shabdkosh scrapes multiple senses of a word and cannot be trusted to
          filter to the correct sense on its own.  Wiktionary acts as the
          sense-disambiguator — a Shabdkosh synonym is accepted only when
          Wiktionary independently confirms it belongs to this word's sense.
        • Keep English-Bangla entries ONLY when the same synonym already
          appears in the Wiktionary accepted set (same rule, even stricter
          source).

        Quality tag: ``"wikiconfirmed"``

    Path B — Wiktionary is NOT present:
        • If two or more non-wiki sources returned results, keep entries that
          appear in at least two of them (cross-source agreement).
        • If only one source was active or contributed, return all its cleaned
          entries as-is — there is no other reference to validate against.

        Quality tag: ``"cross_source"`` or ``"single_source"``

    Either path: if nothing survives filtering → ``"empty"``.

Why Shabdkosh needs Wiki confirmation
--------------------------------------
Shabdkosh is a multi-sense dictionary.  When you look up "চোখ" it returns
synonyms for *all* senses: eye (চক্ষু, নয়ন), needle-eye (সুচি ছিদ্র),
center/heart (কেন্দ্র, হৃৎপিণ্ড), etc.  The scraper has no way to know which
sense the caller intended.  Wiktionary's Bangla entries are sense-specific:
it lists only the body-part synonyms.  So using Wiktionary as a filter —
"keep this Shabdkosh entry only if Wiktionary also lists it" — gives us
correct-sense results without needing semantic NLP.

Public API
----------
    apply_quality(raw_result: dict) -> dict

    ``raw_result`` must contain ``"results"`` (list of dicts with keys
    ``"synonym"`` and ``"source"``) and ``"word"`` (str).

    Returns the same dict shape with updated ``"results"``, ``"words"``, and
    a new ``"quality"`` key.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled patterns used by _normalize() and _is_clean()
# ---------------------------------------------------------------------------

# Any Bangla Unicode character (U+0980–U+09FF)
_BN_CHAR = re.compile(r"[\u0980-\u09FF]")

# Any Latin letter — signals a definition, abbreviation, or English gloss
_LATIN = re.compile(r"[a-zA-Z]")

# Any ASCII or Bangla decimal digit
_DIGIT = re.compile(r"[0-9\u09E6-\u09EF]")

# Invisible / zero-width characters that survive strip()
_INVISIBLE = re.compile(
    r"[\u200b-\u200f"  # zero-width space, non-joiner, joiner, …
    r"\u00ad"  # soft hyphen
    r"\u2060"  # word joiner
    r"\ufeff]",  # BOM / zero-width no-break space
    re.UNICODE,
)

# Structural noise characters — presence means the token is not a plain word
_STRUCTURAL = re.compile(
    r"[।॥"  # Bangla sentence-end marks (daari, double daari)
    r"\(\)\[\]\{\}"  # any bracket type
    r"/\\\|"  # slash, backslash, pipe
    r",;"  # comma, semicolon
    r":\."  # colon, period (period alone can be part of abbrevs)
    r"\-–—"  # dashes and hyphens
    r"?!*~@#%^&+=<>'\"]",  # punctuation that never appears in a Bangla word
    re.UNICODE,
)

# Patterns that signal a descriptive gloss rather than a synonym word
_GLOSS_PREFIX = re.compile(
    r"^\d"  # starts with a digit        "১. জননী"
    r"|^\s*\w+\s*:"  # "prefix label:"            "অর্থ: চক্ষু"  "cf. চক্ষু"
    r"|\s{2,}",  # double (or more) spaces    "ভালচোখ-  নীরোগ"
    re.UNICODE,
)

# Single-token only.
# Allowing 2+ tokens lets multi-word wrong-sense glosses through
# (e.g. Shabdkosh's "সুচি ছিদ্র" for the needle-eye sense of চোখ).
_MAX_TOKENS = 1

# Character-length bounds measured on the bare normalised string (spaces removed)
_MIN_LEN = 2
_MAX_LEN = 20


# ---------------------------------------------------------------------------
# Normaliser — strip junk before validation
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """
    Return a lightly normalised copy of ``text``, or an empty string if the
    token is beyond salvage.

    Steps applied in order
    ----------------------
    1. Strip leading/trailing whitespace.
    2. Remove all invisible / zero-width characters.
    3. Strip leading and trailing punctuation that cannot be part of a Bangla
       word (``*``, ``~``, ``?``, ``!``, ``'``, ``"``, ``:``, ``.``).
       Interior punctuation is left untouched — ``_is_clean`` will reject the
       token if any structural character remains after stripping.
    4. Strip whitespace again (the stripping in step 3 may expose new edges).
    """
    w = text.strip()
    if not w:
        return ""

    # Remove invisible characters anywhere in the string
    w = _INVISIBLE.sub("", w)

    # Strip edge punctuation that is never part of a Bangla word
    edge_punct = r"""*~?!'":;.,@#%^&+\-"""
    w = w.strip(edge_punct).strip()

    return w


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def _is_clean(synonym: str, lookup_word: str) -> bool:
    """
    Return ``True`` when ``synonym`` is a plausible single-word Bangla synonym.

    The input is first normalised by ``_normalize()``.  Validation then
    rejects the candidate when it:

    - Is empty after normalisation.
    - Is identical to the lookup word.
    - Contains no Bangla character at all.
    - Contains any Latin letter (signals an English gloss or abbreviation).
    - Contains any digit (Arabic or Bangla-script decimal).
    - Contains any structural noise character (brackets, slashes, dashes, …).
    - Matches the gloss-prefix pattern (starts with digit, has "label:",
      or contains double spaces).
    - Has more than ``_MAX_TOKENS`` whitespace-separated tokens.
    - Has a bare character length outside [``_MIN_LEN``, ``_MAX_LEN``].

    Separation of concerns
    ----------------------
    ``_normalize`` handles recoverable surface noise (edge punctuation,
    invisible chars).  ``_is_clean`` enforces hard structural rules on the
    result.  A token that requires interior changes — not just edge-stripping —
    is rejected outright rather than silently mutated, because rewriting the
    interior could produce a different word.
    """
    w = _normalize(synonym)

    if not w:
        return False

    if w == lookup_word:
        return False

    # Must contain at least one Bangla character
    if not _BN_CHAR.search(w):
        return False

    # No Latin letters anywhere (rules out English glosses and abbreviations)
    if _LATIN.search(w):
        return False

    # No digits anywhere (rules out numbered entries after normalisation)
    if _DIGIT.search(w):
        return False

    # No structural noise characters (brackets, dashes, slashes, punctuation)
    if _STRUCTURAL.search(w):
        return False

    # No gloss-style prefix patterns or double spaces
    if _GLOSS_PREFIX.search(w):
        return False

    # Single token only
    if len([t for t in w.split() if t]) > _MAX_TOKENS:
        return False

    # Length guard (bare string with spaces removed)
    bare = w.replace(" ", "")
    if not (_MIN_LEN <= len(bare) <= _MAX_LEN):
        return False

    return True


# ---------------------------------------------------------------------------
# Cross-source validation
# ---------------------------------------------------------------------------


def apply_quality(raw: dict) -> dict:
    """
    Apply noise filtering and cross-source validation to a raw scrape result.

    Parameters
    ----------
    raw : dict
        Output of ``fetch_with_sources_raw()``.  Must contain:
        - ``"word"``    : str  — the word that was looked up
        - ``"results"`` : list — each item has ``"synonym"`` and ``"source"``

    Returns
    -------
    dict
        Same shape as input with three fields updated:

        ``"results"``
            Filtered list of ``{"synonym": str, "source": str}`` dicts.
            Entries that passed cross-source validation carry
            ``"confirmed": True``.

        ``"words"``
            Flat deduplicated synonym list, source-priority order.

        ``"sources_results"``
            Passed through unchanged from the input ``raw`` dict.
            Contains the raw per-source output before any filtering, keyed
            by source name.  Present only when the caller supplied it
            (i.e. when coming from ``fetch_with_sources_raw``).

        ``"quality"``
            One of:
            - ``"wikiconfirmed"``  wiki + shabdkosh both present (all three or
                                   wiki+shabdkosh pair).
            - ``"cross_source"``   Two sources present but not the wiki+shabdkosh
                                   pair; en_bn filtered to intersection.
            - ``"single_source"``  Exactly one source; cleaned entries as-is.
            - ``"empty"``          Nothing survived filtering.

    Merge rules by active-source combination
    -----------------------------------------
    The rule answers: *which entries from each source survive?*

    Single source (any one of the three)
        All cleaned entries from that source.  No cross-validation possible.
        Quality: ``"single_source"``

    wiki + shabdkosh
        wiki all  +  shabdkosh ∩ wiki.
        Shabdkosh is multi-sense; wiki acts as the sense anchor and rejects
        wrong-sense shabdkosh entries.
        Quality: ``"wikiconfirmed"``

    wiki + english_bangla
        wiki all  +  en_bn ∩ wiki.
        en_bn is noisy; wiki acts as the sense anchor.
        Quality: ``"cross_source"``

    shabdkosh + english_bangla
        (shabd ∩ en_bn)  +  (en_bn ∩ shabd).
        Both sources are multi-sense; only synonyms confirmed by both survive.
        Quality: ``"cross_source"``

    wiki + shabdkosh + english_bangla  (default, sources=None)
        wiki all
        +  shabdkosh ∩ wiki
        +  en_bn ∩ (wiki ∪ shabdkosh_confirmed).
        wiki is the primary sense anchor; confirmed shabdkosh entries extend
        the trusted set so en_bn can contribute synonyms wiki may have missed.
        Quality: ``"wikiconfirmed"``
    """

    word = raw.get("word", "")
    entries = raw.get("results", [])

    # ------------------------------------------------------------------
    # Stage 1: noise filter
    # ------------------------------------------------------------------
    cleaned: list[dict] = []
    for entry in entries:
        raw_syn = entry.get("synonym", "")
        src = entry.get("source", "")
        # _normalize() strips edge punctuation and invisible chars;
        # _is_clean() runs _normalize() internally and validates the result.
        # We store the *normalised* form so downstream code works on clean text.
        norm_syn = _normalize(raw_syn)
        if _is_clean(raw_syn, word):
            cleaned.append({"synonym": norm_syn, "source": src})
        else:
            log.debug("[quality] dropped '%s' (source=%s) for '%s'", raw_syn, src, word)

    if not cleaned:
        return {**raw, "results": [], "words": [], "quality": "empty"}

    # ------------------------------------------------------------------
    # Stage 2: build per-source word sets for intersection logic
    # ------------------------------------------------------------------
    # IMPORTANT: use ``sources_results`` (the raw per-source output before
    # global dedup) to build the word sets, NOT ``cleaned`` (which reflects
    # post-dedup entries and may be missing a word from source B if source A
    # already contributed the same word earlier in the pipeline).
    #
    # Example: shabdkosh returns ["বদল"], english_bangla returns ["বদলানো",
    # "বদল"].  fetch_with_sources_raw deduplicates globally so the second
    # "বদল" never reaches ``results``.  If we built enbn_set from ``cleaned``
    # it would be {"বদলানো"} — the intersection with shabd_set would be empty
    # and the valid synonym "বদল" would be dropped.  Building from
    # ``sources_results`` gives enbn_set = {"বদলানো", "বদল"} and the
    # intersection is correctly {"বদল"}.
    raw_sources: dict[str, list[str]] = raw.get("sources_results", {})

    def _source_set(name: str) -> set[str]:
        """
        Return the set of *cleaned* synonyms from source ``name``.

        We normalise each word from ``sources_results`` through the same
        ``_normalize`` + ``_is_clean`` pipeline so the sets are comparable
        with the normalised strings stored in ``cleaned``.
        """
        words = raw_sources.get(name, [])
        result: set[str] = set()
        for w in words:
            norm = _normalize(w)
            if _is_clean(w, word):
                result.add(norm)
        return result

    wiki_set = _source_set("wiktionary")
    shabd_set = _source_set("shabdkosh")
    enbn_set = _source_set("english_bangla")

    # Fallback: if sources_results is absent (e.g. local cache hit or
    # older callers), derive sets from cleaned as before.
    if not raw_sources:
        by_source: dict[str, list[str]] = {}
        for entry in cleaned:
            by_source.setdefault(entry["source"], []).append(entry["synonym"])
        wiki_set = set(by_source.get("wiktionary", []))
        shabd_set = set(by_source.get("shabdkosh", []))
        enbn_set = set(by_source.get("english_bangla", []))

    has_wiki = bool(wiki_set)
    has_shabd = bool(shabd_set)
    has_enbn = bool(enbn_set)

    # ------------------------------------------------------------------
    # Stage 3: pick merge strategy based on which sources contributed
    # ------------------------------------------------------------------

    def _collect(source: str, accepted_set: set | None) -> list[dict]:
        """
        Yield cleaned entries from ``source`` in scrape order.

        If ``accepted_set`` is None every entry passes (trusted source,
        no intersection required).  Otherwise only entries whose synonym
        is in ``accepted_set`` are kept, and they receive ``confirmed=True``.
        """
        result = []
        for entry in cleaned:
            if entry["source"] != source:
                continue
            syn = entry["synonym"]
            if accepted_set is None:
                result.append(entry)
            elif syn in accepted_set:
                result.append({**entry, "confirmed": True})
        return result

    # --- single source ---------------------------------------------------
    if sum([has_wiki, has_shabd, has_enbn]) == 1:
        # No cross-validation possible — return everything cleaned.
        final: list[dict] = cleaned
        quality = "single_source"

    # --- all three sources (default, sources=None) ----------------------
    elif has_wiki and has_shabd and has_enbn:
        # wiki is authoritative. shabdkosh is filtered to wiki∩shabdkosh so
        # wrong-sense shabdkosh entries are rejected. en_bn is filtered to
        # synonyms present in either wiki or the confirmed shabdkosh set.
        shabd_confirmed = wiki_set & shabd_set  # intersection
        trusted_union = wiki_set | shabd_confirmed

        final = (
            _collect("wiktionary", accepted_set=None)
            + _collect("shabdkosh", accepted_set=wiki_set)
            + _collect("english_bangla", accepted_set=trusted_union)
        )
        quality = "wikiconfirmed"

    # --- wiki + shabdkosh (no en_bn) ------------------------------------
    elif has_wiki and has_shabd:
        # shabdkosh is multi-sense; wiki acts as sense anchor.
        # Keep only shabdkosh entries that wiki independently confirms.
        final = _collect("wiktionary", accepted_set=None) + _collect(
            "shabdkosh", accepted_set=wiki_set
        )
        quality = "wikiconfirmed"

    # --- wiki + english_bangla (no shabdkosh) ----------------------------
    elif has_wiki and has_enbn:
        # wiki is the sense anchor; en_bn kept only where wiki agrees.
        final = _collect("wiktionary", accepted_set=None) + _collect(
            "english_bangla", accepted_set=wiki_set
        )
        quality = "cross_source"

    # --- shabdkosh + english_bangla (no wiki) ----------------------------
    elif has_shabd and has_enbn:
        # Neither source is authoritative alone.
        # Keep only entries that appear in BOTH sources (intersection).
        # shabdkosh wrong-sense entries that en_bn doesn't confirm are dropped.
        intersection = shabd_set & enbn_set
        final = _collect("shabdkosh", accepted_set=intersection) + _collect(
            "english_bangla", accepted_set=intersection
        )
        quality = "cross_source"

    else:
        # Fallback — should not be reached, but never silently drop data.
        final = cleaned
        quality = "single_source"

    # ------------------------------------------------------------------
    # Stage 4: global dedup (preserve first-seen order)
    # ------------------------------------------------------------------
    seen: set[str] = set()
    deduped: list[dict] = []
    for entry in final:
        syn = entry["synonym"]
        if syn not in seen:
            seen.add(syn)
            deduped.append(entry)

    if not deduped:
        return {**raw, "results": [], "words": [], "quality": "empty"}

    log.debug(
        "[quality] '%s': %d raw → %d after filtering (strategy=%s)",
        word,
        len(entries),
        len(deduped),
        quality,
    )

    return {
        **raw,
        "results": deduped,
        "words": [e["synonym"] for e in deduped],
        "quality": quality,
    }
