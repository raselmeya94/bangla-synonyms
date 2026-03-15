# # # # # """
# # # # # bangla_synonyms.core._quality
# # # # # ------------------------------
# # # # # Post-processing pipeline — noise filtering + cross-source validation.

# # # # # যা করে
# # # # # ------
# # # # # 1. **Noise filter** (`_is_clean`)
# # # # #    প্রতিটা candidate synonym চেক করে:
# # # # #    - Multi-word phrase বাদ (e.g. "ভালচোখ-  নীরোগ চোখ", "সাদা চোখ - স্বাভাবিক দৃষ")
# # # # #    - Descriptive/numbered entries বাদ (e.g. "১.  জননী", "কন্যাস্থানীয়া নারীকে সম্বোধন")
# # # # #    - Special characters বাদ (dash, hyphen, numbers, ZWJ, ZWNJ)
# # # # #    - Too short / too long বাদ
# # # # #    - শব্দটা নিজেই synonym হলে বাদ

# # # # # 2. **Cross-source validation** (`apply_quality`)
# # # # #    Wiktionary আছে কিনা তার উপর ভিত্তি করে দুটো পথ:

# # # # #    Path A — Wiktionary present:
# # # # #      - Wiktionary এর সব clean entries রাখো (authoritative)
# # # # #      - বাকি sources থেকে শুধু সেগুলো রাখো যেগুলো wiktionary তেও আছে
# # # # #        (cross-confirmed → high accuracy)

# # # # #    Path B — Wiktionary absent:
# # # # #      - সব sources এর clean entries নাও
# # # # #      - কমপক্ষে 2টা source এ আছে এমন শব্দগুলো রাখো
# # # # #      - যদি সব entries single-source হয় (মাত্র একটাই source ছিল),
# # # # #        তাহলে সেগুলোই রাখো — কোনো option নেই

# # # # # Public API
# # # # # ----------
# # # # #     apply_quality(raw_result: dict) -> dict

# # # # #     raw_result এ ``results`` list এবং ``word`` থাকতে হবে।
# # # # #     Return করে filtered & annotated dict (same shape, নতুন key ``"quality"`` সহ)।
# # # # # """
# # # # # from __future__ import annotations

# # # # # import re
# # # # # import unicodedata
# # # # # import logging

# # # # # log = logging.getLogger(__name__)

# # # # # # ── Bangla Unicode range ───────────────────────────────────────
# # # # # _BN_CHAR  = re.compile(r"[\u0980-\u09FF]")   # any Bangla character

# # # # # # Characters that indicate a phrase / noise
# # # # # _NOISE_CHARS = re.compile(
# # # # #     r"[0-9"             # digits
# # # # #     r"\-–—"             # dashes / hyphens
# # # # #     r"\u200b-\u200f"    # zero-width chars (ZWJ, ZWNJ, etc.)
# # # # #     r"\u00ad"           # soft hyphen
# # # # #     r"।॥"               # sentence-end marks
# # # # #     r"\(\)\[\]]"        # brackets
# # # # #     r"/"                # slash
# # # # #     r","                # comma inside a token
# # # # #     r";"                # semicolon
# # # # #     r"]",
# # # # #     re.UNICODE,
# # # # # )

# # # # # # Patterns that strongly indicate a descriptive phrase, not a synonym
# # # # # _DESCRIPTIVE_RE = re.compile(
# # # # #     r"^\d"              # starts with digit  "১. জননী"
# # # # #     r"|[a-zA-Z]"        # contains Latin     "নীরোগ eye"
# # # # #     r"|\s{2,}"          # double spaces      "ভালচোখ-  নীরোগ"
# # # # # )

# # # # # # Maximum word count in a valid synonym (single token preferred; allow 2 for compounds)
# # # # # _MAX_TOKENS  = 2
# # # # # # Character length bounds for a single Bangla word
# # # # # _MIN_LEN     = 2
# # # # # _MAX_LEN     = 20


# # # # # def _bangla_token_count(text: str) -> int:
# # # # #     """Whitespace-split token count (ignoring empty strings)."""
# # # # #     return len([t for t in text.split() if t])


# # # # # def _is_clean(word: str, lookup_word: str) -> bool:
# # # # #     """
# # # # #     Return True if `word` is a plausible single-word Bangla synonym.

# # # # #     Rejects
# # # # #     -------
# # # # #     - Same as the lookup word
# # # # #     - Contains noise characters (digits, dashes, ZWJ, …)
# # # # #     - Descriptive phrase pattern (starts with digit, has Latin chars, double spaces)
# # # # #     - More than _MAX_TOKENS whitespace-separated tokens
# # # # #     - Too short or too long
# # # # #     - No Bangla characters at all
# # # # #     """
# # # # #     w = word.strip()

# # # # #     if not w:
# # # # #         return False

# # # # #     # must differ from the word being looked up
# # # # #     if w == lookup_word:
# # # # #         return False

# # # # #     # must contain at least one Bangla character
# # # # #     if not _BN_CHAR.search(w):
# # # # #         return False

# # # # #     # noise character check
# # # # #     if _NOISE_CHARS.search(w):
# # # # #         return False

# # # # #     # descriptive pattern check
# # # # #     if _DESCRIPTIVE_RE.search(w):
# # # # #         return False

# # # # #     # token count — allow "মনোরম্য" (1) or "মনোরম্য অভিরমণীয়" (2 max)
# # # # #     if _bangla_token_count(w) > _MAX_TOKENS:
# # # # #         return False

# # # # #     # length guard on the full string (strip spaces)
# # # # #     bare = w.replace(" ", "")
# # # # #     if len(bare) < _MIN_LEN or len(bare) > _MAX_LEN:
# # # # #         return False

# # # # #     return True


# # # # # def apply_quality(raw: dict) -> dict:
# # # # #     """
# # # # #     Raw scrape result এ quality filter + cross-source validation apply করে।

# # # # #     Parameters
# # # # #     ----------
# # # # #     raw : dict — ``fetch_with_sources_raw()`` এর return value

# # # # #     Returns
# # # # #     -------
# # # # #     dict — same shape as input, with:
# # # # #         ``"results"``  filtered list of ``{"synonym", "source"}``
# # # # #         ``"words"``    updated flat list
# # # # #         ``"quality"``  new key describing what strategy was used:
# # # # #                        ``"wikiconfirmed"``  — wiktionary present, others cross-checked
# # # # #                        ``"cross_source"``   — no wiktionary, ≥2 source agreement
# # # # #                        ``"single_source"``  — only one source available, cleaned only
# # # # #                        ``"empty"``          — nothing survived filtering

# # # # #     Strategy
# # # # #     --------
# # # # #     **Path A — wiktionary present:**
# # # # #         Keep ALL clean wiktionary entries.
# # # # #         From other sources, keep ONLY entries that also appear in the wiktionary set.
# # # # #         This gives high-precision synonyms: wiktionary confirmed, secondarily validated.

# # # # #     **Path B — wiktionary absent:**
# # # # #         Collect all clean entries.
# # # # #         Keep entries that appear in ≥2 sources (cross-source agreement).
# # # # #         If every entry is single-source (only 1 source total), keep all cleaned entries.
# # # # #     """
# # # # #     word    = raw.get("word", "")
# # # # #     entries = raw.get("results", [])

# # # # #     # ── Step 1: clean every entry ─────────────────────────────
# # # # #     cleaned: list[dict] = []
# # # # #     for entry in entries:
# # # # #         syn = entry.get("synonym", "").strip()
# # # # #         src = entry.get("source", "")
# # # # #         if _is_clean(syn, word):
# # # # #             cleaned.append({"synonym": syn, "source": src})
# # # # #         else:
# # # # #             log.debug("[quality] dropped '%s' (source=%s) for '%s'", syn, src, word)

# # # # #     if not cleaned:
# # # # #         return {**raw, "results": [], "words": [], "quality": "empty"}

# # # # #     # ── Step 2: group by source ───────────────────────────────
# # # # #     by_source: dict[str, set[str]] = {}
# # # # #     for entry in cleaned:
# # # # #         src = entry["source"]
# # # # #         by_source.setdefault(src, set()).add(entry["synonym"])

# # # # #     sources_present = set(by_source.keys())

# # # # #     # ── Path A: wiktionary present ────────────────────────────
# # # # #     if "wiktionary" in sources_present:

# # # # #         # Count total source appearances for every clean word
# # # # #         # (across ALL sources including wiktionary)
# # # # #         word_sources: dict[str, set[str]] = {}
# # # # #         for entry in cleaned:
# # # # #             syn = entry["synonym"]
# # # # #             word_sources.setdefault(syn, set()).add(entry["source"])

# # # # #         final: list[dict] = []
# # # # #         seen:  set[str]   = set()

# # # # #         # 1. All wiktionary entries — always kept (authoritative)
# # # # #         for entry in cleaned:
# # # # #             if entry["source"] == "wiktionary" and entry["synonym"] not in seen:
# # # # #                 final.append(entry)
# # # # #                 seen.add(entry["synonym"])

# # # # #         # 2. Non-wiki entries that appear in ≥2 sources total
# # # # #         #    (w+s, w+eb, s+eb — any combination counts)
# # # # #         for entry in cleaned:
# # # # #             if entry["source"] == "wiktionary":
# # # # #                 continue
# # # # #             syn = entry["synonym"]
# # # # #             if syn in seen:
# # # # #                 continue
# # # # #             if len(word_sources.get(syn, set())) >= 2:
# # # # #                 final.append({**entry, "confirmed": True})
# # # # #                 seen.add(syn)

# # # # #         quality = "wikiconfirmed"

# # # # #     # ── Path B: no wiktionary ─────────────────────────────────
# # # # #     else:
# # # # #         # count how many sources each synonym appears in
# # # # #         syn_sources: dict[str, list[str]] = {}
# # # # #         for entry in cleaned:
# # # # #             syn = entry["synonym"]
# # # # #             src = entry["source"]
# # # # #             syn_sources.setdefault(syn, [])
# # # # #             if src not in syn_sources[syn]:
# # # # #                 syn_sources[syn].append(src)

# # # # #         multi = {syn for syn, srcs in syn_sources.items() if len(srcs) >= 2}

# # # # #         if multi:
# # # # #             # keep only cross-source confirmed
# # # # #             seen = set()
# # # # #             final = []
# # # # #             for entry in cleaned:
# # # # #                 syn = entry["synonym"]
# # # # #                 if syn in multi and syn not in seen:
# # # # #                     final.append({**entry, "confirmed": True})
# # # # #                     seen.add(syn)
# # # # #             quality = "cross_source"
# # # # #         else:
# # # # #             # single source only — return all cleaned (no choice)
# # # # #             seen  = set()
# # # # #             final = []
# # # # #             for entry in cleaned:
# # # # #                 syn = entry["synonym"]
# # # # #                 if syn not in seen:
# # # # #                     final.append(entry)
# # # # #                     seen.add(syn)
# # # # #             quality = "single_source"

# # # # #     log.debug(
# # # # #         "[quality] '%s': %d raw → %d after filtering (strategy=%s)",
# # # # #         word, len(entries), len(final), quality,
# # # # #     )

# # # # #     return {
# # # # #         **raw,
# # # # #         "results": final,
# # # # #         "words":   [e["synonym"] for e in final],
# # # # #         "quality": quality,
# # # # #     }

# # # # """
# # # # bangla_synonyms.core._quality
# # # # ------------------------------
# # # # Post-processing pipeline: noise filtering + cross-source validation.

# # # # Two-stage process
# # # # -----------------
# # # # Stage 1 — Noise filter (``_is_clean``)
# # # #     Rejects each candidate synonym that:
# # # #     - Is a multi-word phrase (more than ``_MAX_TOKENS`` tokens)
# # # #     - Contains digits, Latin characters, dashes, zero-width chars, or brackets
# # # #     - Matches descriptive / numbered entry patterns
# # # #     - Is too short or too long
# # # #     - Contains no Bangla characters at all
# # # #     - Is identical to the word being looked up

# # # # Stage 2 — Cross-source validation (``apply_quality``)
# # # #     Decides which cleaned entries to keep based on which sources contributed.

# # # #     Path A — Wiktionary IS present:
# # # #         • Keep ALL clean Wiktionary entries (authoritative).
# # # #         • Keep Shabdkosh entries up to a proportional cap relative to the
# # # #           Wiktionary count — they do not need cross-confirmation because
# # # #           Shabdkosh is a reputable secondary dictionary.
# # # #         • Keep English-Bangla entries ONLY when the same synonym also appears
# # # #           in at least one other source (Wiktionary or Shabdkosh), because
# # # #           English-Bangla is the least reliable source.

# # # #         Quality tag: ``"wikiconfirmed"``

# # # #     Path B — Wiktionary is NOT present:
# # # #         • If two or more non-wiki sources returned results, keep entries that
# # # #           appear in at least two of them (cross-source agreement).
# # # #         • If only one source was active or contributed, return all its cleaned
# # # #           entries as-is — there is no other reference to validate against.

# # # #         Quality tag: ``"cross_source"`` or ``"single_source"``

# # # #     Either path: if nothing survives filtering → ``"empty"``.

# # # # Why the old logic was wrong
# # # # ---------------------------
# # # # The previous "Path A" demanded that every non-wiki synonym appear in ≥2
# # # # sources *total* before being kept.  In practice this dropped every valid
# # # # Shabdkosh synonym because Shabdkosh and English-Bangla rarely overlap on the
# # # # same word — they cover different vocabulary.  The result was that calling
# # # # ``get("চোখ")`` with all three sources active returned *fewer* synonyms than
# # # # calling ``get("চোখ", sources=["wiktionary"])`` alone.

# # # # The new logic treats Shabdkosh as a trusted secondary (include up to a cap)
# # # # and reserves the strict cross-confirmation requirement only for the lower-
# # # # reliability English-Bangla source.

# # # # Public API
# # # # ----------
# # # #     apply_quality(raw_result: dict) -> dict

# # # #     ``raw_result`` must contain ``"results"`` (list of dicts with keys
# # # #     ``"synonym"`` and ``"source"``) and ``"word"`` (str).

# # # #     Returns the same dict shape with updated ``"results"``, ``"words"``, and
# # # #     a new ``"quality"`` key.
# # # # """
# # # # from __future__ import annotations

# # # # import logging
# # # # import re

# # # # log = logging.getLogger(__name__)

# # # # # ---------------------------------------------------------------------------
# # # # # Bangla Unicode range
# # # # # ---------------------------------------------------------------------------
# # # # _BN_CHAR = re.compile(r"[\u0980-\u09FF]")

# # # # # Characters that indicate noise / phrase-level entries
# # # # _NOISE_CHARS = re.compile(
# # # #     r"[0-9"           # digits
# # # #     r"\-–—"           # dashes and hyphens
# # # #     r"\u200b-\u200f"  # zero-width chars (ZWJ, ZWNJ, …)
# # # #     r"\u00ad"         # soft hyphen
# # # #     r"।॥"             # Bangla sentence-end marks
# # # #     r"\(\)\[\]]"      # brackets
# # # #     r"/"              # slash
# # # #     r","              # comma inside a token
# # # #     r";]",            # semicolon
# # # #     re.UNICODE,
# # # # )

# # # # # Patterns that strongly suggest a descriptive phrase rather than a synonym
# # # # _DESCRIPTIVE_RE = re.compile(
# # # #     r"^\d"       # starts with a digit  →  "১. জননী"
# # # #     r"|[a-zA-Z]" # contains Latin chars →  "নীরোগ eye"
# # # #     r"|\s{2,}"   # double spaces        →  "ভালচোখ-  নীরোগ"
# # # # )

# # # # # A valid synonym is at most two whitespace-separated tokens (to allow
# # # # # common Bangla compound words written with a space).
# # # # _MAX_TOKENS = 2

# # # # # Character-length bounds (measured on the bare string, spaces removed)
# # # # _MIN_LEN = 2
# # # # _MAX_LEN = 20

# # # # # ---------------------------------------------------------------------------
# # # # # Proportional cap: when Wiktionary is present, include at most this many
# # # # # Shabdkosh entries relative to the number of Wiktionary entries.
# # # # # Example: 4 wiki entries → cap = ceil(4 * 1.5) = 6 shabdkosh entries.
# # # # # This prevents Shabdkosh from flooding the results while still contributing
# # # # # meaningfully when Wiktionary coverage is thin.
# # # # # ---------------------------------------------------------------------------
# # # # _SHABDKOSH_CAP_RATIO = 1.5


# # # # # ---------------------------------------------------------------------------
# # # # # Noise filter
# # # # # ---------------------------------------------------------------------------

# # # # def _token_count(text: str) -> int:
# # # #     """Return the number of whitespace-separated non-empty tokens."""
# # # #     return len([t for t in text.split() if t])


# # # # def _is_clean(synonym: str, lookup_word: str) -> bool:
# # # #     """
# # # #     Return True when ``synonym`` is a plausible single-word Bangla synonym.

# # # #     Rejects the candidate when it:
# # # #     - Is empty or identical to the lookup word.
# # # #     - Contains no Bangla characters.
# # # #     - Contains noise characters (digits, dashes, zero-width chars, …).
# # # #     - Matches the descriptive-phrase pattern.
# # # #     - Has more than ``_MAX_TOKENS`` whitespace-separated tokens.
# # # #     - Has a bare character length outside [``_MIN_LEN``, ``_MAX_LEN``].
# # # #     """
# # # #     w = synonym.strip()

# # # #     if not w:
# # # #         return False

# # # #     if w == lookup_word:
# # # #         return False

# # # #     if not _BN_CHAR.search(w):
# # # #         return False

# # # #     if _NOISE_CHARS.search(w):
# # # #         return False

# # # #     if _DESCRIPTIVE_RE.search(w):
# # # #         return False

# # # #     if _token_count(w) > _MAX_TOKENS:
# # # #         return False

# # # #     bare = w.replace(" ", "")
# # # #     if not (_MIN_LEN <= len(bare) <= _MAX_LEN):
# # # #         return False

# # # #     return True


# # # # # ---------------------------------------------------------------------------
# # # # # Cross-source validation
# # # # # ---------------------------------------------------------------------------

# # # # def apply_quality(raw: dict) -> dict:
# # # #     """
# # # #     Apply noise filtering and cross-source validation to a raw scrape result.

# # # #     Parameters
# # # #     ----------
# # # #     raw : dict
# # # #         Output of ``fetch_with_sources_raw()``.  Must contain:
# # # #         - ``"word"``    : str   — the word that was looked up
# # # #         - ``"results"`` : list  — each item has ``"synonym"`` and ``"source"``

# # # #     Returns
# # # #     -------
# # # #     dict
# # # #         Same shape as input with three fields updated:

# # # #         ``"results"``
# # # #             Filtered list of ``{"synonym": str, "source": str}`` dicts.
# # # #             Entries from cross-validated secondary sources also carry
# # # #             ``"confirmed": True``.

# # # #         ``"words"``
# # # #             Flat list of surviving synonyms (backward-compatible shortcut).

# # # #         ``"quality"``
# # # #             One of:
# # # #             - ``"wikiconfirmed"``  Wiktionary was present; Shabdkosh added up
# # # #                                    to its cap; English-Bangla only if confirmed.
# # # #             - ``"cross_source"``   No Wiktionary; entries confirmed by ≥2 sources.
# # # #             - ``"single_source"``  Only one source available; cleaned entries
# # # #                                    returned as-is.
# # # #             - ``"empty"``          Nothing survived filtering.

# # # #     Algorithm
# # # #     ---------
# # # #     Path A — Wiktionary present
# # # #         1. Keep all clean Wiktionary entries (always authoritative).
# # # #         2. Keep Shabdkosh entries up to ``ceil(wiki_count * _SHABDKOSH_CAP_RATIO)``
# # # #            without requiring cross-confirmation (Shabdkosh is a reputable
# # # #            secondary dictionary).
# # # #         3. Keep English-Bangla entries only when the same synonym already
# # # #            appears in the Wiktionary or Shabdkosh accepted set.

# # # #     Path B — Wiktionary absent
# # # #         1. Count how many distinct sources provide each synonym.
# # # #         2. If any synonym appears in ≥2 sources, keep only those (cross_source).
# # # #         3. If all synonyms are single-source, keep all cleaned entries
# # # #            (single_source) — there is nothing to validate against.
# # # #     """
# # # #     import math

# # # #     word    = raw.get("word", "")
# # # #     entries = raw.get("results", [])

# # # #     # ------------------------------------------------------------------
# # # #     # Stage 1: noise filter
# # # #     # ------------------------------------------------------------------
# # # #     cleaned: list[dict] = []
# # # #     for entry in entries:
# # # #         syn = entry.get("synonym", "").strip()
# # # #         src = entry.get("source", "")
# # # #         if _is_clean(syn, word):
# # # #             cleaned.append({"synonym": syn, "source": src})
# # # #         else:
# # # #             log.debug(
# # # #                 "[quality] dropped '%s' (source=%s) for '%s'", syn, src, word
# # # #             )

# # # #     if not cleaned:
# # # #         return {**raw, "results": [], "words": [], "quality": "empty"}

# # # #     # ------------------------------------------------------------------
# # # #     # Group cleaned entries by source for path selection
# # # #     # ------------------------------------------------------------------
# # # #     by_source: dict[str, list[str]] = {}
# # # #     for entry in cleaned:
# # # #         by_source.setdefault(entry["source"], []).append(entry["synonym"])

# # # #     sources_present = set(by_source.keys())

# # # #     # ------------------------------------------------------------------
# # # #     # Path A: Wiktionary is present
# # # #     # ------------------------------------------------------------------
# # # #     if "wiktionary" in sources_present:
# # # #         final: list[dict] = []
# # # #         seen:  set[str]   = set()

# # # #         # Step 1 — all clean Wiktionary entries (authoritative, no cap)
# # # #         for entry in cleaned:
# # # #             if entry["source"] == "wiktionary" and entry["synonym"] not in seen:
# # # #                 final.append(entry)
# # # #                 seen.add(entry["synonym"])

# # # #         wiki_count = len(final)

# # # #         # Step 2 — Shabdkosh entries up to proportional cap
# # # #         shabdkosh_cap = math.ceil(wiki_count * _SHABDKOSH_CAP_RATIO)
# # # #         shabdkosh_added = 0
# # # #         for entry in cleaned:
# # # #             if entry["source"] != "shabdkosh":
# # # #                 continue
# # # #             if entry["synonym"] in seen:
# # # #                 continue
# # # #             if shabdkosh_added >= shabdkosh_cap:
# # # #                 break
# # # #             final.append({**entry, "confirmed": True})
# # # #             seen.add(entry["synonym"])
# # # #             shabdkosh_added += 1

# # # #         # Step 3 — English-Bangla entries only when cross-confirmed
# # # #         # (synonym must already be in the accepted set from wiki or shabdkosh)
# # # #         for entry in cleaned:
# # # #             if entry["source"] != "english_bangla":
# # # #                 continue
# # # #             syn = entry["synonym"]
# # # #             if syn in seen:
# # # #                 # already accepted from a higher-tier source — skip duplicate
# # # #                 continue
# # # #             # Accept only if this synonym was also provided by wiki or shabdkosh
# # # #             also_in_other = any(
# # # #                 syn in by_source.get(s, [])
# # # #                 for s in ("wiktionary", "shabdkosh")
# # # #             )
# # # #             if also_in_other:
# # # #                 final.append({**entry, "confirmed": True})
# # # #                 seen.add(syn)

# # # #         quality = "wikiconfirmed"

# # # #     # ------------------------------------------------------------------
# # # #     # Path B: Wiktionary is absent
# # # #     # ------------------------------------------------------------------
# # # #     else:
# # # #         # Count distinct sources per synonym
# # # #         syn_sources: dict[str, set[str]] = {}
# # # #         for entry in cleaned:
# # # #             syn_sources.setdefault(entry["synonym"], set()).add(entry["source"])

# # # #         multi_confirmed = {
# # # #             syn for syn, srcs in syn_sources.items() if len(srcs) >= 2
# # # #         }

# # # #         seen = set()
# # # #         final = []

# # # #         if multi_confirmed:
# # # #             # Keep only synonyms confirmed by two or more sources
# # # #             for entry in cleaned:
# # # #                 syn = entry["synonym"]
# # # #                 if syn in multi_confirmed and syn not in seen:
# # # #                     final.append({**entry, "confirmed": True})
# # # #                     seen.add(syn)
# # # #             quality = "cross_source"
# # # #         else:
# # # #             # Single source only — return all cleaned entries
# # # #             for entry in cleaned:
# # # #                 syn = entry["synonym"]
# # # #                 if syn not in seen:
# # # #                     final.append(entry)
# # # #                     seen.add(syn)
# # # #             quality = "single_source"

# # # #     # ------------------------------------------------------------------
# # # #     # Guard: if filtering removed everything, mark as empty
# # # #     # ------------------------------------------------------------------
# # # #     if not final:
# # # #         return {**raw, "results": [], "words": [], "quality": "empty"}

# # # #     log.debug(
# # # #         "[quality] '%s': %d raw entries → %d kept (strategy=%s)",
# # # #         word, len(entries), len(final), quality,
# # # #     )

# # # #     return {
# # # #         **raw,
# # # #         "results": final,
# # # #         "words":   [e["synonym"] for e in final],
# # # #         "quality": quality,
# # # #     }

# # # """
# # # bangla_synonyms.core._quality
# # # ------------------------------
# # # Post-processing pipeline: noise filtering + cross-source validation.

# # # Two-stage process
# # # -----------------
# # # Stage 1 — Noise filter (``_is_clean``)
# # #     Rejects each candidate synonym that:
# # #     - Is a multi-word phrase (more than ``_MAX_TOKENS`` tokens)
# # #     - Contains digits, Latin characters, dashes, zero-width chars, or brackets
# # #     - Matches descriptive / numbered entry patterns
# # #     - Is too short or too long
# # #     - Contains no Bangla characters at all
# # #     - Is identical to the word being looked up

# # #     ``_MAX_TOKENS = 1`` enforces single-token synonyms.  This is intentionally
# # #     strict: Shabdkosh in particular scrapes multiple word-senses per entry and
# # #     returns multi-word glosses (e.g. "সুচি ছিদ্র" for the "eye of a needle"
# # #     sense of চোখ).  Allowing two tokens lets those wrong-sense phrases through.

# # # Stage 2 — Cross-source validation (``apply_quality``)
# # #     Decides which cleaned entries to keep based on which sources contributed.

# # #     Path A — Wiktionary IS present:
# # #         • Keep ALL clean Wiktionary entries (authoritative, no cap).
# # #         • Keep Shabdkosh entries ONLY when the same synonym already appears in
# # #           the Wiktionary accepted set.  This is tighter than a simple cap:
# # #           Shabdkosh scrapes multiple senses of a word and cannot be trusted to
# # #           filter to the correct sense on its own.  Wiktionary acts as the
# # #           sense-disambiguator — a Shabdkosh synonym is accepted only when
# # #           Wiktionary independently confirms it belongs to this word's sense.
# # #         • Keep English-Bangla entries ONLY when the same synonym already
# # #           appears in the Wiktionary accepted set (same rule, even stricter
# # #           source).

# # #         Quality tag: ``"wikiconfirmed"``

# # #     Path B — Wiktionary is NOT present:
# # #         • If two or more non-wiki sources returned results, keep entries that
# # #           appear in at least two of them (cross-source agreement).
# # #         • If only one source was active or contributed, return all its cleaned
# # #           entries as-is — there is no other reference to validate against.

# # #         Quality tag: ``"cross_source"`` or ``"single_source"``

# # #     Either path: if nothing survives filtering → ``"empty"``.

# # # Why Shabdkosh needs Wiki confirmation
# # # --------------------------------------
# # # Shabdkosh is a multi-sense dictionary.  When you look up "চোখ" it returns
# # # synonyms for *all* senses: eye (চক্ষু, নয়ন), needle-eye (সুচি ছিদ্র),
# # # center/heart (কেন্দ্র, হৃৎপিণ্ড), etc.  The scraper has no way to know which
# # # sense the caller intended.  Wiktionary's Bangla entries are sense-specific:
# # # it lists only the body-part synonyms.  So using Wiktionary as a filter —
# # # "keep this Shabdkosh entry only if Wiktionary also lists it" — gives us
# # # correct-sense results without needing semantic NLP.

# # # Public API
# # # ----------
# # #     apply_quality(raw_result: dict) -> dict

# # #     ``raw_result`` must contain ``"results"`` (list of dicts with keys
# # #     ``"synonym"`` and ``"source"``) and ``"word"`` (str).

# # #     Returns the same dict shape with updated ``"results"``, ``"words"``, and
# # #     a new ``"quality"`` key.
# # # """
# # # from __future__ import annotations

# # # import logging
# # # import re

# # # log = logging.getLogger(__name__)

# # # # ---------------------------------------------------------------------------
# # # # Compiled patterns used by _normalize() and _is_clean()
# # # # ---------------------------------------------------------------------------

# # # # Any Bangla Unicode character (U+0980–U+09FF)
# # # _BN_CHAR = re.compile(r"[\u0980-\u09FF]")

# # # # Any Latin letter — signals a definition, abbreviation, or English gloss
# # # _LATIN = re.compile(r"[a-zA-Z]")

# # # # Any ASCII or Bangla decimal digit
# # # _DIGIT = re.compile(r"[0-9\u09E6-\u09EF]")

# # # # Invisible / zero-width characters that survive strip()
# # # _INVISIBLE = re.compile(
# # #     r"[\u200b-\u200f"   # zero-width space, non-joiner, joiner, …
# # #     r"\u00ad"           # soft hyphen
# # #     r"\u2060"           # word joiner
# # #     r"\ufeff]",         # BOM / zero-width no-break space
# # #     re.UNICODE,
# # # )

# # # # Structural noise characters — presence means the token is not a plain word
# # # _STRUCTURAL = re.compile(
# # #     r"[।॥"              # Bangla sentence-end marks (daari, double daari)
# # #     r"\(\)\[\]\{\}"     # any bracket type
# # #     r"/\\\|"            # slash, backslash, pipe
# # #     r",;"               # comma, semicolon
# # #     r":\."              # colon, period (period alone can be part of abbrevs)
# # #     r"\-–—"             # dashes and hyphens
# # #     r"?!*~@#%^&+=<>'\"]",  # punctuation that never appears in a Bangla word
# # #     re.UNICODE,
# # # )

# # # # Patterns that signal a descriptive gloss rather than a synonym word
# # # _GLOSS_PREFIX = re.compile(
# # #     r"^\d"                 # starts with a digit        "১. জননী"
# # #     r"|^\s*\w+\s*:"        # "prefix label:"            "অর্থ: চক্ষু"  "cf. চক্ষু"
# # #     r"|\s{2,}",            # double (or more) spaces    "ভালচোখ-  নীরোগ"
# # #     re.UNICODE,
# # # )

# # # # Single-token only.
# # # # Allowing 2+ tokens lets multi-word wrong-sense glosses through
# # # # (e.g. Shabdkosh's "সুচি ছিদ্র" for the needle-eye sense of চোখ).
# # # _MAX_TOKENS = 1

# # # # Character-length bounds measured on the bare normalised string (spaces removed)
# # # _MIN_LEN = 2
# # # _MAX_LEN = 20


# # # # ---------------------------------------------------------------------------
# # # # Normaliser — strip junk before validation
# # # # ---------------------------------------------------------------------------

# # # def _normalize(text: str) -> str:
# # #     """
# # #     Return a lightly normalised copy of ``text``, or an empty string if the
# # #     token is beyond salvage.

# # #     Steps applied in order
# # #     ----------------------
# # #     1. Strip leading/trailing whitespace.
# # #     2. Remove all invisible / zero-width characters.
# # #     3. Strip leading and trailing punctuation that cannot be part of a Bangla
# # #        word (``*``, ``~``, ``?``, ``!``, ``'``, ``"``, ``:``, ``.``).
# # #        Interior punctuation is left untouched — ``_is_clean`` will reject the
# # #        token if any structural character remains after stripping.
# # #     4. Strip whitespace again (the stripping in step 3 may expose new edges).
# # #     """
# # #     w = text.strip()
# # #     if not w:
# # #         return ""

# # #     # Remove invisible characters anywhere in the string
# # #     w = _INVISIBLE.sub("", w)

# # #     # Strip edge punctuation that is never part of a Bangla word
# # #     edge_punct = r"""*~?!'":;.,@#%^&+\-"""
# # #     w = w.strip(edge_punct).strip()

# # #     return w


# # # # ---------------------------------------------------------------------------
# # # # Validator
# # # # ---------------------------------------------------------------------------

# # # def _is_clean(synonym: str, lookup_word: str) -> bool:
# # #     """
# # #     Return ``True`` when ``synonym`` is a plausible single-word Bangla synonym.

# # #     The input is first normalised by ``_normalize()``.  Validation then
# # #     rejects the candidate when it:

# # #     - Is empty after normalisation.
# # #     - Is identical to the lookup word.
# # #     - Contains no Bangla character at all.
# # #     - Contains any Latin letter (signals an English gloss or abbreviation).
# # #     - Contains any digit (Arabic or Bangla-script decimal).
# # #     - Contains any structural noise character (brackets, slashes, dashes, …).
# # #     - Matches the gloss-prefix pattern (starts with digit, has "label:",
# # #       or contains double spaces).
# # #     - Has more than ``_MAX_TOKENS`` whitespace-separated tokens.
# # #     - Has a bare character length outside [``_MIN_LEN``, ``_MAX_LEN``].

# # #     Separation of concerns
# # #     ----------------------
# # #     ``_normalize`` handles recoverable surface noise (edge punctuation,
# # #     invisible chars).  ``_is_clean`` enforces hard structural rules on the
# # #     result.  A token that requires interior changes — not just edge-stripping —
# # #     is rejected outright rather than silently mutated, because rewriting the
# # #     interior could produce a different word.
# # #     """
# # #     w = _normalize(synonym)

# # #     if not w:
# # #         return False

# # #     if w == lookup_word:
# # #         return False

# # #     # Must contain at least one Bangla character
# # #     if not _BN_CHAR.search(w):
# # #         return False

# # #     # No Latin letters anywhere (rules out English glosses and abbreviations)
# # #     if _LATIN.search(w):
# # #         return False

# # #     # No digits anywhere (rules out numbered entries after normalisation)
# # #     if _DIGIT.search(w):
# # #         return False

# # #     # No structural noise characters (brackets, dashes, slashes, punctuation)
# # #     if _STRUCTURAL.search(w):
# # #         return False

# # #     # No gloss-style prefix patterns or double spaces
# # #     if _GLOSS_PREFIX.search(w):
# # #         return False

# # #     # Single token only
# # #     if len([t for t in w.split() if t]) > _MAX_TOKENS:
# # #         return False

# # #     # Length guard (bare string with spaces removed)
# # #     bare = w.replace(" ", "")
# # #     if not (_MIN_LEN <= len(bare) <= _MAX_LEN):
# # #         return False

# # #     return True


# # # # ---------------------------------------------------------------------------
# # # # Cross-source validation
# # # # ---------------------------------------------------------------------------

# # # def apply_quality(raw: dict) -> dict:
# # #     """
# # #     Apply noise filtering and cross-source validation to a raw scrape result.

# # #     Parameters
# # #     ----------
# # #     raw : dict
# # #         Output of ``fetch_with_sources_raw()``.  Must contain:
# # #         - ``"word"``    : str  — the word that was looked up
# # #         - ``"results"`` : list — each item has ``"synonym"`` and ``"source"``

# # #     Returns
# # #     -------
# # #     dict
# # #         Same shape as input with three fields updated:

# # #         ``"results"``
# # #             Filtered list of ``{"synonym": str, "source": str}`` dicts.
# # #             Entries that passed cross-source validation carry
# # #             ``"confirmed": True``.

# # #         ``"words"``
# # #             Flat deduplicated synonym list, source-priority order.

# # #         ``"quality"``
# # #             One of:
# # #             - ``"wikiconfirmed"``  wiki + shabdkosh both present (all three or
# # #                                    wiki+shabdkosh pair).
# # #             - ``"cross_source"``   Two sources present but not the wiki+shabdkosh
# # #                                    pair; en_bn filtered to intersection.
# # #             - ``"single_source"``  Exactly one source; cleaned entries as-is.
# # #             - ``"empty"``          Nothing survived filtering.

# # #     Merge rules by active-source combination
# # #     -----------------------------------------
# # #     The rule answers: *which entries from each source survive?*

# # #     Single source (any one of the three)
# # #         All cleaned entries from that source.  No cross-validation possible.
# # #         Quality: ``"single_source"``

# # #     wiki + shabdkosh
# # #         All wiki entries + all shabdkosh entries.
# # #         Both are reputable dictionaries — no intersection filter needed.
# # #         Quality: ``"wikiconfirmed"``

# # #     wiki + english_bangla
# # #         All wiki entries + shabdkosh entries that are ALSO in wiki (intersection).
# # #         en_bn is multi-sense and noisy; wiki acts as the sense anchor.
# # #         Quality: ``"cross_source"``

# # #     shabdkosh + english_bangla
# # #         All shabdkosh entries + en_bn entries that are ALSO in shabdkosh
# # #         (intersection).  shabdkosh acts as the sense anchor.
# # #         Quality: ``"cross_source"``

# # #     wiki + shabdkosh + english_bangla  (default, sources=None)
# # #         All wiki entries + all shabdkosh entries + en_bn entries that appear
# # #         in EITHER wiki or shabdkosh (intersection with the trusted union).
# # #         Quality: ``"wikiconfirmed"``
# # #     """

# # #     word    = raw.get("word", "")
# # #     entries = raw.get("results", [])

# # #     # ------------------------------------------------------------------
# # #     # Stage 1: noise filter
# # #     # ------------------------------------------------------------------
# # #     cleaned: list[dict] = []
# # #     for entry in entries:
# # #         raw_syn = entry.get("synonym", "")
# # #         src     = entry.get("source", "")
# # #         # _normalize() strips edge punctuation and invisible chars;
# # #         # _is_clean() runs _normalize() internally and validates the result.
# # #         # We store the *normalised* form so downstream code works on clean text.
# # #         norm_syn = _normalize(raw_syn)
# # #         if _is_clean(raw_syn, word):
# # #             cleaned.append({"synonym": norm_syn, "source": src})
# # #         else:
# # #             log.debug(
# # #                 "[quality] dropped '%s' (source=%s) for '%s'", raw_syn, src, word
# # #             )

# # #     if not cleaned:
# # #         return {**raw, "results": [], "words": [], "quality": "empty"}

# # #     # ------------------------------------------------------------------
# # #     # Stage 2: group by source
# # #     # ------------------------------------------------------------------
# # #     # Preserve insertion order within each source bucket.
# # #     by_source: dict[str, list[str]] = {}
# # #     for entry in cleaned:
# # #         by_source.setdefault(entry["source"], []).append(entry["synonym"])

# # #     # Convenience sets for fast intersection checks.
# # #     wiki_set  = set(by_source.get("wiktionary",     []))
# # #     shabd_set = set(by_source.get("shabdkosh",       []))
# # #     enbn_set  = set(by_source.get("english_bangla",  []))

# # #     has_wiki  = bool(wiki_set)
# # #     has_shabd = bool(shabd_set)
# # #     has_enbn  = bool(enbn_set)

# # #     # ------------------------------------------------------------------
# # #     # Stage 3: pick merge strategy based on which sources contributed
# # #     # ------------------------------------------------------------------

# # #     def _collect(source: str, accepted_set: set | None) -> list[dict]:
# # #         """
# # #         Yield cleaned entries from ``source`` in scrape order.

# # #         If ``accepted_set`` is None every entry passes (trusted source,
# # #         no intersection required).  Otherwise only entries whose synonym
# # #         is in ``accepted_set`` are kept, and they receive ``confirmed=True``.
# # #         """
# # #         result = []
# # #         for entry in cleaned:
# # #             if entry["source"] != source:
# # #                 continue
# # #             syn = entry["synonym"]
# # #             if accepted_set is None:
# # #                 result.append(entry)
# # #             elif syn in accepted_set:
# # #                 result.append({**entry, "confirmed": True})
# # #         return result

# # #     # --- single source ---------------------------------------------------
# # #     if sum([has_wiki, has_shabd, has_enbn]) == 1:
# # #         # No cross-validation possible — return everything cleaned.
# # #         final: list[dict] = cleaned
# # #         quality = "single_source"

# # #     # --- wiki + shabdkosh (with or without en_bn) -----------------------
# # #     elif has_wiki and has_shabd:
# # #         # wiki and shabdkosh are both trusted: include all entries from both.
# # #         # en_bn is noisy: keep only synonyms that appear in wiki ∪ shabdkosh.
# # #         trusted_union = wiki_set | shabd_set

# # #         final = (
# # #             _collect("wiktionary",    accepted_set=None)
# # #             + _collect("shabdkosh",   accepted_set=None)
# # #             + _collect("english_bangla", accepted_set=trusted_union)
# # #         )
# # #         quality = "wikiconfirmed"

# # #     # --- wiki + english_bangla (no shabdkosh) ----------------------------
# # #     elif has_wiki and has_enbn:
# # #         # wiki is the sense anchor; en_bn kept only where wiki agrees.
# # #         final = (
# # #             _collect("wiktionary",    accepted_set=None)
# # #             + _collect("english_bangla", accepted_set=wiki_set)
# # #         )
# # #         quality = "cross_source"

# # #     # --- shabdkosh + english_bangla (no wiki) ----------------------------
# # #     elif has_shabd and has_enbn:
# # #         # shabdkosh is the sense anchor; en_bn kept only where shabdkosh agrees.
# # #         final = (
# # #             _collect("shabdkosh",     accepted_set=None)
# # #             + _collect("english_bangla", accepted_set=shabd_set)
# # #         )
# # #         quality = "cross_source"

# # #     else:
# # #         # Fallback: should not be reached given the checks above,
# # #         # but return all cleaned entries rather than silently dropping them.
# # #         final   = cleaned
# # #         quality = "single_source"

# # #     # ------------------------------------------------------------------
# # #     # Stage 4: global dedup (preserve first-seen order)
# # #     # ------------------------------------------------------------------
# # #     seen: set[str] = set()
# # #     deduped: list[dict] = []
# # #     for entry in final:
# # #         syn = entry["synonym"]
# # #         if syn not in seen:
# # #             seen.add(syn)
# # #             deduped.append(entry)

# # #     if not deduped:
# # #         return {**raw, "results": [], "words": [], "quality": "empty"}

# # #     log.debug(
# # #         "[quality] '%s': %d raw → %d after filtering (strategy=%s)",
# # #         word, len(entries), len(deduped), quality,
# # #     )

# # #     return {
# # #         **raw,
# # #         "results": deduped,
# # #         "words":   [e["synonym"] for e in deduped],
# # #         "quality": quality,
# # #     }

# # """
# # bangla_synonyms.core._quality
# # ------------------------------
# # Post-processing pipeline: noise filtering + cross-source validation.

# # Two-stage process
# # -----------------
# # Stage 1 — Noise filter (``_is_clean``)
# #     Rejects each candidate synonym that:
# #     - Is a multi-word phrase (more than ``_MAX_TOKENS`` tokens)
# #     - Contains digits, Latin characters, dashes, zero-width chars, or brackets
# #     - Matches descriptive / numbered entry patterns
# #     - Is too short or too long
# #     - Contains no Bangla characters at all
# #     - Is identical to the word being looked up

# #     ``_MAX_TOKENS = 1`` enforces single-token synonyms.  This is intentionally
# #     strict: Shabdkosh in particular scrapes multiple word-senses per entry and
# #     returns multi-word glosses (e.g. "সুচি ছিদ্র" for the "eye of a needle"
# #     sense of চোখ).  Allowing two tokens lets those wrong-sense phrases through.

# # Stage 2 — Cross-source validation (``apply_quality``)
# #     Decides which cleaned entries to keep based on which sources contributed.

# #     Path A — Wiktionary IS present:
# #         • Keep ALL clean Wiktionary entries (authoritative, no cap).
# #         • Keep Shabdkosh entries ONLY when the same synonym already appears in
# #           the Wiktionary accepted set.  This is tighter than a simple cap:
# #           Shabdkosh scrapes multiple senses of a word and cannot be trusted to
# #           filter to the correct sense on its own.  Wiktionary acts as the
# #           sense-disambiguator — a Shabdkosh synonym is accepted only when
# #           Wiktionary independently confirms it belongs to this word's sense.
# #         • Keep English-Bangla entries ONLY when the same synonym already
# #           appears in the Wiktionary accepted set (same rule, even stricter
# #           source).

# #         Quality tag: ``"wikiconfirmed"``

# #     Path B — Wiktionary is NOT present:
# #         • If two or more non-wiki sources returned results, keep entries that
# #           appear in at least two of them (cross-source agreement).
# #         • If only one source was active or contributed, return all its cleaned
# #           entries as-is — there is no other reference to validate against.

# #         Quality tag: ``"cross_source"`` or ``"single_source"``

# #     Either path: if nothing survives filtering → ``"empty"``.

# # Why Shabdkosh needs Wiki confirmation
# # --------------------------------------
# # Shabdkosh is a multi-sense dictionary.  When you look up "চোখ" it returns
# # synonyms for *all* senses: eye (চক্ষু, নয়ন), needle-eye (সুচি ছিদ্র),
# # center/heart (কেন্দ্র, হৃৎপিণ্ড), etc.  The scraper has no way to know which
# # sense the caller intended.  Wiktionary's Bangla entries are sense-specific:
# # it lists only the body-part synonyms.  So using Wiktionary as a filter —
# # "keep this Shabdkosh entry only if Wiktionary also lists it" — gives us
# # correct-sense results without needing semantic NLP.

# # Public API
# # ----------
# #     apply_quality(raw_result: dict) -> dict

# #     ``raw_result`` must contain ``"results"`` (list of dicts with keys
# #     ``"synonym"`` and ``"source"``) and ``"word"`` (str).

# #     Returns the same dict shape with updated ``"results"``, ``"words"``, and
# #     a new ``"quality"`` key.
# # """
# # from __future__ import annotations

# # import logging
# # import re

# # log = logging.getLogger(__name__)

# # # ---------------------------------------------------------------------------
# # # Compiled patterns used by _normalize() and _is_clean()
# # # ---------------------------------------------------------------------------

# # # Any Bangla Unicode character (U+0980–U+09FF)
# # _BN_CHAR = re.compile(r"[\u0980-\u09FF]")

# # # Any Latin letter — signals a definition, abbreviation, or English gloss
# # _LATIN = re.compile(r"[a-zA-Z]")

# # # Any ASCII or Bangla decimal digit
# # _DIGIT = re.compile(r"[0-9\u09E6-\u09EF]")

# # # Invisible / zero-width characters that survive strip()
# # _INVISIBLE = re.compile(
# #     r"[\u200b-\u200f"   # zero-width space, non-joiner, joiner, …
# #     r"\u00ad"           # soft hyphen
# #     r"\u2060"           # word joiner
# #     r"\ufeff]",         # BOM / zero-width no-break space
# #     re.UNICODE,
# # )

# # # Structural noise characters — presence means the token is not a plain word
# # _STRUCTURAL = re.compile(
# #     r"[।॥"              # Bangla sentence-end marks (daari, double daari)
# #     r"\(\)\[\]\{\}"     # any bracket type
# #     r"/\\\|"            # slash, backslash, pipe
# #     r",;"               # comma, semicolon
# #     r":\."              # colon, period (period alone can be part of abbrevs)
# #     r"\-–—"             # dashes and hyphens
# #     r"?!*~@#%^&+=<>'\"]",  # punctuation that never appears in a Bangla word
# #     re.UNICODE,
# # )

# # # Patterns that signal a descriptive gloss rather than a synonym word
# # _GLOSS_PREFIX = re.compile(
# #     r"^\d"                 # starts with a digit        "১. জননী"
# #     r"|^\s*\w+\s*:"        # "prefix label:"            "অর্থ: চক্ষু"  "cf. চক্ষু"
# #     r"|\s{2,}",            # double (or more) spaces    "ভালচোখ-  নীরোগ"
# #     re.UNICODE,
# # )

# # # Single-token only.
# # # Allowing 2+ tokens lets multi-word wrong-sense glosses through
# # # (e.g. Shabdkosh's "সুচি ছিদ্র" for the needle-eye sense of চোখ).
# # _MAX_TOKENS = 1

# # # Character-length bounds measured on the bare normalised string (spaces removed)
# # _MIN_LEN = 2
# # _MAX_LEN = 20


# # # ---------------------------------------------------------------------------
# # # Normaliser — strip junk before validation
# # # ---------------------------------------------------------------------------

# # def _normalize(text: str) -> str:
# #     """
# #     Return a lightly normalised copy of ``text``, or an empty string if the
# #     token is beyond salvage.

# #     Steps applied in order
# #     ----------------------
# #     1. Strip leading/trailing whitespace.
# #     2. Remove all invisible / zero-width characters.
# #     3. Strip leading and trailing punctuation that cannot be part of a Bangla
# #        word (``*``, ``~``, ``?``, ``!``, ``'``, ``"``, ``:``, ``.``).
# #        Interior punctuation is left untouched — ``_is_clean`` will reject the
# #        token if any structural character remains after stripping.
# #     4. Strip whitespace again (the stripping in step 3 may expose new edges).
# #     """
# #     w = text.strip()
# #     if not w:
# #         return ""

# #     # Remove invisible characters anywhere in the string
# #     w = _INVISIBLE.sub("", w)

# #     # Strip edge punctuation that is never part of a Bangla word
# #     edge_punct = r"""*~?!'":;.,@#%^&+\-"""
# #     w = w.strip(edge_punct).strip()

# #     return w


# # # ---------------------------------------------------------------------------
# # # Validator
# # # ---------------------------------------------------------------------------

# # def _is_clean(synonym: str, lookup_word: str) -> bool:
# #     """
# #     Return ``True`` when ``synonym`` is a plausible single-word Bangla synonym.

# #     The input is first normalised by ``_normalize()``.  Validation then
# #     rejects the candidate when it:

# #     - Is empty after normalisation.
# #     - Is identical to the lookup word.
# #     - Contains no Bangla character at all.
# #     - Contains any Latin letter (signals an English gloss or abbreviation).
# #     - Contains any digit (Arabic or Bangla-script decimal).
# #     - Contains any structural noise character (brackets, slashes, dashes, …).
# #     - Matches the gloss-prefix pattern (starts with digit, has "label:",
# #       or contains double spaces).
# #     - Has more than ``_MAX_TOKENS`` whitespace-separated tokens.
# #     - Has a bare character length outside [``_MIN_LEN``, ``_MAX_LEN``].

# #     Separation of concerns
# #     ----------------------
# #     ``_normalize`` handles recoverable surface noise (edge punctuation,
# #     invisible chars).  ``_is_clean`` enforces hard structural rules on the
# #     result.  A token that requires interior changes — not just edge-stripping —
# #     is rejected outright rather than silently mutated, because rewriting the
# #     interior could produce a different word.
# #     """
# #     w = _normalize(synonym)

# #     if not w:
# #         return False

# #     if w == lookup_word:
# #         return False

# #     # Must contain at least one Bangla character
# #     if not _BN_CHAR.search(w):
# #         return False

# #     # No Latin letters anywhere (rules out English glosses and abbreviations)
# #     if _LATIN.search(w):
# #         return False

# #     # No digits anywhere (rules out numbered entries after normalisation)
# #     if _DIGIT.search(w):
# #         return False

# #     # No structural noise characters (brackets, dashes, slashes, punctuation)
# #     if _STRUCTURAL.search(w):
# #         return False

# #     # No gloss-style prefix patterns or double spaces
# #     if _GLOSS_PREFIX.search(w):
# #         return False

# #     # Single token only
# #     if len([t for t in w.split() if t]) > _MAX_TOKENS:
# #         return False

# #     # Length guard (bare string with spaces removed)
# #     bare = w.replace(" ", "")
# #     if not (_MIN_LEN <= len(bare) <= _MAX_LEN):
# #         return False

# #     return True


# # # ---------------------------------------------------------------------------
# # # Cross-source validation
# # # ---------------------------------------------------------------------------

# # def apply_quality(raw: dict) -> dict:
# #     """
# #     Apply noise filtering and cross-source validation to a raw scrape result.

# #     Parameters
# #     ----------
# #     raw : dict
# #         Output of ``fetch_with_sources_raw()``.  Must contain:
# #         - ``"word"``    : str  — the word that was looked up
# #         - ``"results"`` : list — each item has ``"synonym"`` and ``"source"``

# #     Returns
# #     -------
# #     dict
# #         Same shape as input with three fields updated:

# #         ``"results"``
# #             Filtered list of ``{"synonym": str, "source": str}`` dicts.
# #             Entries that passed cross-source validation carry
# #             ``"confirmed": True``.

# #         ``"words"``
# #             Flat deduplicated synonym list, source-priority order.

# #         ``"quality"``
# #             One of:
# #             - ``"wikiconfirmed"``  wiki + shabdkosh both present (all three or
# #                                    wiki+shabdkosh pair).
# #             - ``"cross_source"``   Two sources present but not the wiki+shabdkosh
# #                                    pair; en_bn filtered to intersection.
# #             - ``"single_source"``  Exactly one source; cleaned entries as-is.
# #             - ``"empty"``          Nothing survived filtering.

# #     Merge rules by active-source combination
# #     -----------------------------------------
# #     The rule answers: *which entries from each source survive?*

# #     Single source (any one of the three)
# #         All cleaned entries from that source.  No cross-validation possible.
# #         Quality: ``"single_source"``

# #     wiki + shabdkosh
# #         wiki all  +  shabdkosh ∩ wiki.
# #         Shabdkosh is multi-sense; wiki acts as the sense anchor and rejects
# #         wrong-sense shabdkosh entries.
# #         Quality: ``"wikiconfirmed"``

# #     wiki + english_bangla
# #         wiki all  +  en_bn ∩ wiki.
# #         en_bn is noisy; wiki acts as the sense anchor.
# #         Quality: ``"cross_source"``

# #     shabdkosh + english_bangla
# #         (shabd ∩ en_bn)  +  (en_bn ∩ shabd).
# #         Both sources are multi-sense; only synonyms confirmed by both survive.
# #         Quality: ``"cross_source"``

# #     wiki + shabdkosh + english_bangla  (default, sources=None)
# #         wiki all
# #         +  shabdkosh ∩ wiki
# #         +  en_bn ∩ (wiki ∪ shabdkosh_confirmed).
# #         wiki is the primary sense anchor; confirmed shabdkosh entries extend
# #         the trusted set so en_bn can contribute synonyms wiki may have missed.
# #         Quality: ``"wikiconfirmed"``
# #     """

# #     word    = raw.get("word", "")
# #     entries = raw.get("results", [])

# #     # ------------------------------------------------------------------
# #     # Stage 1: noise filter
# #     # ------------------------------------------------------------------
# #     cleaned: list[dict] = []
# #     for entry in entries:
# #         raw_syn = entry.get("synonym", "")
# #         src     = entry.get("source", "")
# #         # _normalize() strips edge punctuation and invisible chars;
# #         # _is_clean() runs _normalize() internally and validates the result.
# #         # We store the *normalised* form so downstream code works on clean text.
# #         norm_syn = _normalize(raw_syn)
# #         if _is_clean(raw_syn, word):
# #             cleaned.append({"synonym": norm_syn, "source": src})
# #         else:
# #             log.debug(
# #                 "[quality] dropped '%s' (source=%s) for '%s'", raw_syn, src, word
# #             )

# #     if not cleaned:
# #         return {**raw, "results": [], "words": [], "quality": "empty"}

# #     # ------------------------------------------------------------------
# #     # Stage 2: group by source
# #     # ------------------------------------------------------------------
# #     # Preserve insertion order within each source bucket.
# #     by_source: dict[str, list[str]] = {}
# #     for entry in cleaned:
# #         by_source.setdefault(entry["source"], []).append(entry["synonym"])

# #     # Convenience sets for fast intersection checks.
# #     wiki_set  = set(by_source.get("wiktionary",     []))
# #     shabd_set = set(by_source.get("shabdkosh",       []))
# #     enbn_set  = set(by_source.get("english_bangla",  []))

# #     has_wiki  = bool(wiki_set)
# #     has_shabd = bool(shabd_set)
# #     has_enbn  = bool(enbn_set)

# #     # ------------------------------------------------------------------
# #     # Stage 3: pick merge strategy based on which sources contributed
# #     # ------------------------------------------------------------------

# #     def _collect(source: str, accepted_set: set | None) -> list[dict]:
# #         """
# #         Yield cleaned entries from ``source`` in scrape order.

# #         If ``accepted_set`` is None every entry passes (trusted source,
# #         no intersection required).  Otherwise only entries whose synonym
# #         is in ``accepted_set`` are kept, and they receive ``confirmed=True``.
# #         """
# #         result = []
# #         for entry in cleaned:
# #             if entry["source"] != source:
# #                 continue
# #             syn = entry["synonym"]
# #             if accepted_set is None:
# #                 result.append(entry)
# #             elif syn in accepted_set:
# #                 result.append({**entry, "confirmed": True})
# #         return result

# #     # --- single source ---------------------------------------------------
# #     if sum([has_wiki, has_shabd, has_enbn]) == 1:
# #         # No cross-validation possible — return everything cleaned.
# #         final: list[dict] = cleaned
# #         quality = "single_source"

# #     # --- all three sources (default, sources=None) ----------------------
# #     elif has_wiki and has_shabd and has_enbn:
# #         # wiki is authoritative. shabdkosh is filtered to wiki∩shabdkosh so
# #         # wrong-sense shabdkosh entries are rejected. en_bn is filtered to
# #         # synonyms present in either wiki or the confirmed shabdkosh set.
# #         shabd_confirmed = wiki_set & shabd_set   # intersection
# #         trusted_union   = wiki_set | shabd_confirmed

# #         final = (
# #             _collect("wiktionary",       accepted_set=None)
# #             + _collect("shabdkosh",      accepted_set=wiki_set)
# #             + _collect("english_bangla", accepted_set=trusted_union)
# #         )
# #         quality = "wikiconfirmed"

# #     # --- wiki + shabdkosh (no en_bn) ------------------------------------
# #     elif has_wiki and has_shabd:
# #         # shabdkosh is multi-sense; wiki acts as sense anchor.
# #         # Keep only shabdkosh entries that wiki independently confirms.
# #         final = (
# #             _collect("wiktionary", accepted_set=None)
# #             + _collect("shabdkosh", accepted_set=wiki_set)
# #         )
# #         quality = "wikiconfirmed"

# #     # --- wiki + english_bangla (no shabdkosh) ----------------------------
# #     elif has_wiki and has_enbn:
# #         # wiki is the sense anchor; en_bn kept only where wiki agrees.
# #         final = (
# #             _collect("wiktionary",       accepted_set=None)
# #             + _collect("english_bangla", accepted_set=wiki_set)
# #         )
# #         quality = "cross_source"

# #     # --- shabdkosh + english_bangla (no wiki) ----------------------------
# #     elif has_shabd and has_enbn:
# #         # Neither source is authoritative alone.
# #         # Keep only entries that appear in BOTH sources (intersection).
# #         # shabdkosh wrong-sense entries that en_bn doesn't confirm are dropped.
# #         intersection = shabd_set & enbn_set
# #         final = (
# #             _collect("shabdkosh",        accepted_set=intersection)
# #             + _collect("english_bangla", accepted_set=intersection)
# #         )
# #         quality = "cross_source"

# #     else:
# #         # Fallback — should not be reached, but never silently drop data.
# #         final   = cleaned
# #         quality = "single_source"

# #     # ------------------------------------------------------------------
# #     # Stage 4: global dedup (preserve first-seen order)
# #     # ------------------------------------------------------------------
# #     seen: set[str] = set()
# #     deduped: list[dict] = []
# #     for entry in final:
# #         syn = entry["synonym"]
# #         if syn not in seen:
# #             seen.add(syn)
# #             deduped.append(entry)

# #     if not deduped:
# #         return {**raw, "results": [], "words": [], "quality": "empty"}

# #     log.debug(
# #         "[quality] '%s': %d raw → %d after filtering (strategy=%s)",
# #         word, len(entries), len(deduped), quality,
# #     )

# #     return {
# #         **raw,
# #         "results": deduped,
# #         "words":   [e["synonym"] for e in deduped],
# #         "quality": quality,
# #     }

# """
# bangla_synonyms.core._quality
# ------------------------------
# Post-processing pipeline: noise filtering + cross-source validation.

# Two-stage process
# -----------------
# Stage 1 — Noise filter (``_is_clean``)
#     Rejects each candidate synonym that:
#     - Is a multi-word phrase (more than ``_MAX_TOKENS`` tokens)
#     - Contains digits, Latin characters, dashes, zero-width chars, or brackets
#     - Matches descriptive / numbered entry patterns
#     - Is too short or too long
#     - Contains no Bangla characters at all
#     - Is identical to the word being looked up

#     ``_MAX_TOKENS = 1`` enforces single-token synonyms.  This is intentionally
#     strict: Shabdkosh in particular scrapes multiple word-senses per entry and
#     returns multi-word glosses (e.g. "সুচি ছিদ্র" for the "eye of a needle"
#     sense of চোখ).  Allowing two tokens lets those wrong-sense phrases through.

# Stage 2 — Cross-source validation (``apply_quality``)
#     Decides which cleaned entries to keep based on which sources contributed.

#     Path A — Wiktionary IS present:
#         • Keep ALL clean Wiktionary entries (authoritative, no cap).
#         • Keep Shabdkosh entries ONLY when the same synonym already appears in
#           the Wiktionary accepted set.  This is tighter than a simple cap:
#           Shabdkosh scrapes multiple senses of a word and cannot be trusted to
#           filter to the correct sense on its own.  Wiktionary acts as the
#           sense-disambiguator — a Shabdkosh synonym is accepted only when
#           Wiktionary independently confirms it belongs to this word's sense.
#         • Keep English-Bangla entries ONLY when the same synonym already
#           appears in the Wiktionary accepted set (same rule, even stricter
#           source).

#         Quality tag: ``"wikiconfirmed"``

#     Path B — Wiktionary is NOT present:
#         • If two or more non-wiki sources returned results, keep entries that
#           appear in at least two of them (cross-source agreement).
#         • If only one source was active or contributed, return all its cleaned
#           entries as-is — there is no other reference to validate against.

#         Quality tag: ``"cross_source"`` or ``"single_source"``

#     Either path: if nothing survives filtering → ``"empty"``.

# Why Shabdkosh needs Wiki confirmation
# --------------------------------------
# Shabdkosh is a multi-sense dictionary.  When you look up "চোখ" it returns
# synonyms for *all* senses: eye (চক্ষু, নয়ন), needle-eye (সুচি ছিদ্র),
# center/heart (কেন্দ্র, হৃৎপিণ্ড), etc.  The scraper has no way to know which
# sense the caller intended.  Wiktionary's Bangla entries are sense-specific:
# it lists only the body-part synonyms.  So using Wiktionary as a filter —
# "keep this Shabdkosh entry only if Wiktionary also lists it" — gives us
# correct-sense results without needing semantic NLP.

# Public API
# ----------
#     apply_quality(raw_result: dict) -> dict

#     ``raw_result`` must contain ``"results"`` (list of dicts with keys
#     ``"synonym"`` and ``"source"``) and ``"word"`` (str).

#     Returns the same dict shape with updated ``"results"``, ``"words"``, and
#     a new ``"quality"`` key.
# """
# from __future__ import annotations

# import logging
# import re

# log = logging.getLogger(__name__)

# # ---------------------------------------------------------------------------
# # Compiled patterns used by _normalize() and _is_clean()
# # ---------------------------------------------------------------------------

# # Any Bangla Unicode character (U+0980–U+09FF)
# _BN_CHAR = re.compile(r"[\u0980-\u09FF]")

# # Any Latin letter — signals a definition, abbreviation, or English gloss
# _LATIN = re.compile(r"[a-zA-Z]")

# # Any ASCII or Bangla decimal digit
# _DIGIT = re.compile(r"[0-9\u09E6-\u09EF]")

# # Invisible / zero-width characters that survive strip()
# _INVISIBLE = re.compile(
#     r"[\u200b-\u200f"   # zero-width space, non-joiner, joiner, …
#     r"\u00ad"           # soft hyphen
#     r"\u2060"           # word joiner
#     r"\ufeff]",         # BOM / zero-width no-break space
#     re.UNICODE,
# )

# # Structural noise characters — presence means the token is not a plain word
# _STRUCTURAL = re.compile(
#     r"[।॥"              # Bangla sentence-end marks (daari, double daari)
#     r"\(\)\[\]\{\}"     # any bracket type
#     r"/\\\|"            # slash, backslash, pipe
#     r",;"               # comma, semicolon
#     r":\."              # colon, period (period alone can be part of abbrevs)
#     r"\-–—"             # dashes and hyphens
#     r"?!*~@#%^&+=<>'\"]",  # punctuation that never appears in a Bangla word
#     re.UNICODE,
# )

# # Patterns that signal a descriptive gloss rather than a synonym word
# _GLOSS_PREFIX = re.compile(
#     r"^\d"                 # starts with a digit        "১. জননী"
#     r"|^\s*\w+\s*:"        # "prefix label:"            "অর্থ: চক্ষু"  "cf. চক্ষু"
#     r"|\s{2,}",            # double (or more) spaces    "ভালচোখ-  নীরোগ"
#     re.UNICODE,
# )

# # Single-token only.
# # Allowing 2+ tokens lets multi-word wrong-sense glosses through
# # (e.g. Shabdkosh's "সুচি ছিদ্র" for the needle-eye sense of চোখ).
# _MAX_TOKENS = 1

# # Character-length bounds measured on the bare normalised string (spaces removed)
# _MIN_LEN = 2
# _MAX_LEN = 20


# # ---------------------------------------------------------------------------
# # Normaliser — strip junk before validation
# # ---------------------------------------------------------------------------

# def _normalize(text: str) -> str:
#     """
#     Return a lightly normalised copy of ``text``, or an empty string if the
#     token is beyond salvage.

#     Steps applied in order
#     ----------------------
#     1. Strip leading/trailing whitespace.
#     2. Remove all invisible / zero-width characters.
#     3. Strip leading and trailing punctuation that cannot be part of a Bangla
#        word (``*``, ``~``, ``?``, ``!``, ``'``, ``"``, ``:``, ``.``).
#        Interior punctuation is left untouched — ``_is_clean`` will reject the
#        token if any structural character remains after stripping.
#     4. Strip whitespace again (the stripping in step 3 may expose new edges).
#     """
#     w = text.strip()
#     if not w:
#         return ""

#     # Remove invisible characters anywhere in the string
#     w = _INVISIBLE.sub("", w)

#     # Strip edge punctuation that is never part of a Bangla word
#     edge_punct = r"""*~?!'":;.,@#%^&+\-"""
#     w = w.strip(edge_punct).strip()

#     return w


# # ---------------------------------------------------------------------------
# # Validator
# # ---------------------------------------------------------------------------

# def _is_clean(synonym: str, lookup_word: str) -> bool:
#     """
#     Return ``True`` when ``synonym`` is a plausible single-word Bangla synonym.

#     The input is first normalised by ``_normalize()``.  Validation then
#     rejects the candidate when it:

#     - Is empty after normalisation.
#     - Is identical to the lookup word.
#     - Contains no Bangla character at all.
#     - Contains any Latin letter (signals an English gloss or abbreviation).
#     - Contains any digit (Arabic or Bangla-script decimal).
#     - Contains any structural noise character (brackets, slashes, dashes, …).
#     - Matches the gloss-prefix pattern (starts with digit, has "label:",
#       or contains double spaces).
#     - Has more than ``_MAX_TOKENS`` whitespace-separated tokens.
#     - Has a bare character length outside [``_MIN_LEN``, ``_MAX_LEN``].

#     Separation of concerns
#     ----------------------
#     ``_normalize`` handles recoverable surface noise (edge punctuation,
#     invisible chars).  ``_is_clean`` enforces hard structural rules on the
#     result.  A token that requires interior changes — not just edge-stripping —
#     is rejected outright rather than silently mutated, because rewriting the
#     interior could produce a different word.
#     """
#     w = _normalize(synonym)

#     if not w:
#         return False

#     if w == lookup_word:
#         return False

#     # Must contain at least one Bangla character
#     if not _BN_CHAR.search(w):
#         return False

#     # No Latin letters anywhere (rules out English glosses and abbreviations)
#     if _LATIN.search(w):
#         return False

#     # No digits anywhere (rules out numbered entries after normalisation)
#     if _DIGIT.search(w):
#         return False

#     # No structural noise characters (brackets, dashes, slashes, punctuation)
#     if _STRUCTURAL.search(w):
#         return False

#     # No gloss-style prefix patterns or double spaces
#     if _GLOSS_PREFIX.search(w):
#         return False

#     # Single token only
#     if len([t for t in w.split() if t]) > _MAX_TOKENS:
#         return False

#     # Length guard (bare string with spaces removed)
#     bare = w.replace(" ", "")
#     if not (_MIN_LEN <= len(bare) <= _MAX_LEN):
#         return False

#     return True


# # ---------------------------------------------------------------------------
# # Cross-source validation
# # ---------------------------------------------------------------------------

# def apply_quality(raw: dict) -> dict:
#     """
#     Apply noise filtering and cross-source validation to a raw scrape result.

#     Parameters
#     ----------
#     raw : dict
#         Output of ``fetch_with_sources_raw()``.  Must contain:
#         - ``"word"``    : str  — the word that was looked up
#         - ``"results"`` : list — each item has ``"synonym"`` and ``"source"``

#     Returns
#     -------
#     dict
#         Same shape as input with three fields updated:

#         ``"results"``
#             Filtered list of ``{"synonym": str, "source": str}`` dicts.
#             Entries that passed cross-source validation carry
#             ``"confirmed": True``.

#         ``"words"``
#             Flat deduplicated synonym list, source-priority order.

#         ``"sources_results"``
#             Passed through unchanged from the input ``raw`` dict.
#             Contains the raw per-source output before any filtering, keyed
#             by source name.  Present only when the caller supplied it
#             (i.e. when coming from ``fetch_with_sources_raw``).

#         ``"quality"``
#             One of:
#             - ``"wikiconfirmed"``  wiki + shabdkosh both present (all three or
#                                    wiki+shabdkosh pair).
#             - ``"cross_source"``   Two sources present but not the wiki+shabdkosh
#                                    pair; en_bn filtered to intersection.
#             - ``"single_source"``  Exactly one source; cleaned entries as-is.
#             - ``"empty"``          Nothing survived filtering.

#     Merge rules by active-source combination
#     -----------------------------------------
#     The rule answers: *which entries from each source survive?*

#     Single source (any one of the three)
#         All cleaned entries from that source.  No cross-validation possible.
#         Quality: ``"single_source"``

#     wiki + shabdkosh
#         wiki all  +  shabdkosh ∩ wiki.
#         Shabdkosh is multi-sense; wiki acts as the sense anchor and rejects
#         wrong-sense shabdkosh entries.
#         Quality: ``"wikiconfirmed"``

#     wiki + english_bangla
#         wiki all  +  en_bn ∩ wiki.
#         en_bn is noisy; wiki acts as the sense anchor.
#         Quality: ``"cross_source"``

#     shabdkosh + english_bangla
#         (shabd ∩ en_bn)  +  (en_bn ∩ shabd).
#         Both sources are multi-sense; only synonyms confirmed by both survive.
#         Quality: ``"cross_source"``

#     wiki + shabdkosh + english_bangla  (default, sources=None)
#         wiki all
#         +  shabdkosh ∩ wiki
#         +  en_bn ∩ (wiki ∪ shabdkosh_confirmed).
#         wiki is the primary sense anchor; confirmed shabdkosh entries extend
#         the trusted set so en_bn can contribute synonyms wiki may have missed.
#         Quality: ``"wikiconfirmed"``
#     """

#     word    = raw.get("word", "")
#     entries = raw.get("results", [])

#     # ------------------------------------------------------------------
#     # Stage 1: noise filter
#     # ------------------------------------------------------------------
#     cleaned: list[dict] = []
#     for entry in entries:
#         raw_syn = entry.get("synonym", "")
#         src     = entry.get("source", "")
#         # _normalize() strips edge punctuation and invisible chars;
#         # _is_clean() runs _normalize() internally and validates the result.
#         # We store the *normalised* form so downstream code works on clean text.
#         norm_syn = _normalize(raw_syn)
#         if _is_clean(raw_syn, word):
#             cleaned.append({"synonym": norm_syn, "source": src})
#         else:
#             log.debug(
#                 "[quality] dropped '%s' (source=%s) for '%s'", raw_syn, src, word
#             )

#     if not cleaned:
#         return {**raw, "results": [], "words": [], "quality": "empty"}

#     # ------------------------------------------------------------------
#     # Stage 2: group by source
#     # ------------------------------------------------------------------
#     # Preserve insertion order within each source bucket.
#     by_source: dict[str, list[str]] = {}
#     for entry in cleaned:
#         by_source.setdefault(entry["source"], []).append(entry["synonym"])

#     # Convenience sets for fast intersection checks.
#     wiki_set  = set(by_source.get("wiktionary",     []))
#     shabd_set = set(by_source.get("shabdkosh",       []))
#     enbn_set  = set(by_source.get("english_bangla",  []))

#     has_wiki  = bool(wiki_set)
#     has_shabd = bool(shabd_set)
#     has_enbn  = bool(enbn_set)

#     # ------------------------------------------------------------------
#     # Stage 3: pick merge strategy based on which sources contributed
#     # ------------------------------------------------------------------

#     def _collect(source: str, accepted_set: set | None) -> list[dict]:
#         """
#         Yield cleaned entries from ``source`` in scrape order.

#         If ``accepted_set`` is None every entry passes (trusted source,
#         no intersection required).  Otherwise only entries whose synonym
#         is in ``accepted_set`` are kept, and they receive ``confirmed=True``.
#         """
#         result = []
#         for entry in cleaned:
#             if entry["source"] != source:
#                 continue
#             syn = entry["synonym"]
#             if accepted_set is None:
#                 result.append(entry)
#             elif syn in accepted_set:
#                 result.append({**entry, "confirmed": True})
#         return result

#     # --- single source ---------------------------------------------------
#     if sum([has_wiki, has_shabd, has_enbn]) == 1:
#         # No cross-validation possible — return everything cleaned.
#         final: list[dict] = cleaned
#         quality = "single_source"

#     # --- all three sources (default, sources=None) ----------------------
#     elif has_wiki and has_shabd and has_enbn:
#         # wiki is authoritative. shabdkosh is filtered to wiki∩shabdkosh so
#         # wrong-sense shabdkosh entries are rejected. en_bn is filtered to
#         # synonyms present in either wiki or the confirmed shabdkosh set.
#         shabd_confirmed = wiki_set & shabd_set   # intersection
#         trusted_union   = wiki_set | shabd_confirmed

#         final = (
#             _collect("wiktionary",       accepted_set=None)
#             + _collect("shabdkosh",      accepted_set=wiki_set)
#             + _collect("english_bangla", accepted_set=trusted_union)
#         )
#         quality = "wikiconfirmed"

#     # --- wiki + shabdkosh (no en_bn) ------------------------------------
#     elif has_wiki and has_shabd:
#         # shabdkosh is multi-sense; wiki acts as sense anchor.
#         # Keep only shabdkosh entries that wiki independently confirms.
#         final = (
#             _collect("wiktionary", accepted_set=None)
#             + _collect("shabdkosh", accepted_set=wiki_set)
#         )
#         quality = "wikiconfirmed"

#     # --- wiki + english_bangla (no shabdkosh) ----------------------------
#     elif has_wiki and has_enbn:
#         # wiki is the sense anchor; en_bn kept only where wiki agrees.
#         final = (
#             _collect("wiktionary",       accepted_set=None)
#             + _collect("english_bangla", accepted_set=wiki_set)
#         )
#         quality = "cross_source"

#     # --- shabdkosh + english_bangla (no wiki) ----------------------------
#     elif has_shabd and has_enbn:
#         # Neither source is authoritative alone.
#         # Keep only entries that appear in BOTH sources (intersection).
#         # shabdkosh wrong-sense entries that en_bn doesn't confirm are dropped.
#         intersection = shabd_set & enbn_set
#         final = (
#             _collect("shabdkosh",        accepted_set=intersection)
#             + _collect("english_bangla", accepted_set=intersection)
#         )
#         quality = "cross_source"

#     else:
#         # Fallback — should not be reached, but never silently drop data.
#         final   = cleaned
#         quality = "single_source"

#     # ------------------------------------------------------------------
#     # Stage 4: global dedup (preserve first-seen order)
#     # ------------------------------------------------------------------
#     seen: set[str] = set()
#     deduped: list[dict] = []
#     for entry in final:
#         syn = entry["synonym"]
#         if syn not in seen:
#             seen.add(syn)
#             deduped.append(entry)

#     if not deduped:
#         return {**raw, "results": [], "words": [], "quality": "empty"}

#     log.debug(
#         "[quality] '%s': %d raw → %d after filtering (strategy=%s)",
#         word, len(entries), len(deduped), quality,
#     )

#     return {
#         **raw,
#         "results": deduped,
#         "words":   [e["synonym"] for e in deduped],
#         "quality": quality,
#     }


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
    r"[\u200b-\u200f"   # zero-width space, non-joiner, joiner, …
    r"\u00ad"           # soft hyphen
    r"\u2060"           # word joiner
    r"\ufeff]",         # BOM / zero-width no-break space
    re.UNICODE,
)

# Structural noise characters — presence means the token is not a plain word
_STRUCTURAL = re.compile(
    r"[।॥"              # Bangla sentence-end marks (daari, double daari)
    r"\(\)\[\]\{\}"     # any bracket type
    r"/\\\|"            # slash, backslash, pipe
    r",;"               # comma, semicolon
    r":\."              # colon, period (period alone can be part of abbrevs)
    r"\-–—"             # dashes and hyphens
    r"?!*~@#%^&+=<>'\"]",  # punctuation that never appears in a Bangla word
    re.UNICODE,
)

# Patterns that signal a descriptive gloss rather than a synonym word
_GLOSS_PREFIX = re.compile(
    r"^\d"                 # starts with a digit        "১. জননী"
    r"|^\s*\w+\s*:"        # "prefix label:"            "অর্থ: চক্ষু"  "cf. চক্ষু"
    r"|\s{2,}",            # double (or more) spaces    "ভালচোখ-  নীরোগ"
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

    word    = raw.get("word", "")
    entries = raw.get("results", [])

    # ------------------------------------------------------------------
    # Stage 1: noise filter
    # ------------------------------------------------------------------
    cleaned: list[dict] = []
    for entry in entries:
        raw_syn = entry.get("synonym", "")
        src     = entry.get("source", "")
        # _normalize() strips edge punctuation and invisible chars;
        # _is_clean() runs _normalize() internally and validates the result.
        # We store the *normalised* form so downstream code works on clean text.
        norm_syn = _normalize(raw_syn)
        if _is_clean(raw_syn, word):
            cleaned.append({"synonym": norm_syn, "source": src})
        else:
            log.debug(
                "[quality] dropped '%s' (source=%s) for '%s'", raw_syn, src, word
            )

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

    wiki_set  = _source_set("wiktionary")
    shabd_set = _source_set("shabdkosh")
    enbn_set  = _source_set("english_bangla")

    # Fallback: if sources_results is absent (e.g. local cache hit or
    # older callers), derive sets from cleaned as before.
    if not raw_sources:
        by_source: dict[str, list[str]] = {}
        for entry in cleaned:
            by_source.setdefault(entry["source"], []).append(entry["synonym"])
        wiki_set  = set(by_source.get("wiktionary",    []))
        shabd_set = set(by_source.get("shabdkosh",      []))
        enbn_set  = set(by_source.get("english_bangla", []))

    has_wiki  = bool(wiki_set)
    has_shabd = bool(shabd_set)
    has_enbn  = bool(enbn_set)

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
        shabd_confirmed = wiki_set & shabd_set   # intersection
        trusted_union   = wiki_set | shabd_confirmed

        final = (
            _collect("wiktionary",       accepted_set=None)
            + _collect("shabdkosh",      accepted_set=wiki_set)
            + _collect("english_bangla", accepted_set=trusted_union)
        )
        quality = "wikiconfirmed"

    # --- wiki + shabdkosh (no en_bn) ------------------------------------
    elif has_wiki and has_shabd:
        # shabdkosh is multi-sense; wiki acts as sense anchor.
        # Keep only shabdkosh entries that wiki independently confirms.
        final = (
            _collect("wiktionary", accepted_set=None)
            + _collect("shabdkosh", accepted_set=wiki_set)
        )
        quality = "wikiconfirmed"

    # --- wiki + english_bangla (no shabdkosh) ----------------------------
    elif has_wiki and has_enbn:
        # wiki is the sense anchor; en_bn kept only where wiki agrees.
        final = (
            _collect("wiktionary",       accepted_set=None)
            + _collect("english_bangla", accepted_set=wiki_set)
        )
        quality = "cross_source"

    # --- shabdkosh + english_bangla (no wiki) ----------------------------
    elif has_shabd and has_enbn:
        # Neither source is authoritative alone.
        # Keep only entries that appear in BOTH sources (intersection).
        # shabdkosh wrong-sense entries that en_bn doesn't confirm are dropped.
        intersection = shabd_set & enbn_set
        final = (
            _collect("shabdkosh",        accepted_set=intersection)
            + _collect("english_bangla", accepted_set=intersection)
        )
        quality = "cross_source"

    else:
        # Fallback — should not be reached, but never silently drop data.
        final   = cleaned
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
        word, len(entries), len(deduped), quality,
    )

    return {
        **raw,
        "results": deduped,
        "words":   [e["synonym"] for e in deduped],
        "quality": quality,
    }