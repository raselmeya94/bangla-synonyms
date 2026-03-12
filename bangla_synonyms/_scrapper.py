"""
bangla_synonyms._scrapper
--------------------------
Scrapper — full control over scraping behaviour with source selection,
fallback cascade, and offline support.

Public import path: ``from bangla_synonyms import Scrapper``
"""
from __future__ import annotations

import logging
import time

from .core import DatasetManager, fetch_with_sources, fetch_with_sources_raw, DEFAULT_SOURCES, SOURCES, _save
from .core._wikitext import make_session

log = logging.getLogger(__name__)


class Scrapper:
    """
    Bangla synonym scraper with full parameter control.

    Parameters
    ----------
    offline    : bool       — no internet; local dataset only (default: False)
    auto_save  : bool       — persist scraped results to disk (default: False)
                              explicitly set True to save results locally
    delay      : float      — seconds between requests (default: 1.0)
    timeout    : int        — HTTP request timeout seconds (default: 10)
    sources    : list|None  — which sources to use (default: all three)
    merge      : bool       — merge all source results (True) or stop at
                              first hit (False) (default: True)

    Sources available
    -----------------
    ``"wiktionary"``     — bn.wiktionary.org (most reliable, structured)
    ``"shabdkosh"``      — shabdkosh.com (good coverage)
    ``"english_bangla"`` — english-bangla.com (last resort, near-synonyms)

    Lookup behaviour
    ----------------
    1. Strip whitespace from input word.
    2. Check local dataset (fast, no network).
    3. If not found and ``offline=False``, query configured sources in order.
    4. If ``auto_save=True``, persist the result for next time.

    Quick patterns
    --------------
    +--------------------------------------------+----------------------------------+
    | ``Scrapper()``                             | online, no auto-save, delay 1 s  |
    +--------------------------------------------+----------------------------------+
    | ``Scrapper(offline=True)``                 | local dataset only, no HTTP      |
    +--------------------------------------------+----------------------------------+
    | ``Scrapper(auto_save=True)``               | scrape and persist to disk       |
    +--------------------------------------------+----------------------------------+
    | ``Scrapper(sources=["wiktionary"])``        | Wiktionary only                  |
    +--------------------------------------------+----------------------------------+
    | ``Scrapper(merge=False)``                  | stop at first source with hits   |
    +--------------------------------------------+----------------------------------+
    | ``Scrapper(delay=2.0, timeout=15)``        | polite / slow connection         |
    +--------------------------------------------+----------------------------------+

    Examples
    --------
        from bangla_synonyms import Scrapper

        # Default — local cache first, then online (results NOT saved)
        sc = Scrapper()
        sc.get("চোখ")                          # → ['চক্ষু', 'নেত্র', 'লোচন', ...]
        sc.get_many(["চোখ", "মা", "নদী"])

        # Save scraped results for next time
        sc = Scrapper(auto_save=True)
        sc.get("আকাশ")                         # found online → saved to dataset

        # Offline only
        sc_offline = Scrapper(offline=True)
        sc_offline.get("মা")                   # local only — no network call

        # Wiktionary only, stop at first hit
        sc_wiki = Scrapper(sources=["wiktionary"], merge=False)
        sc_wiki.get("আকাশ")

        # Custom delay for slow connections
        sc_slow = Scrapper(delay=2.0, timeout=15)
        sc_slow.get("সুন্দর")
    """

    def __init__(
        self,
        offline:   bool       = False,
        auto_save: bool       = False,   # False by default — user must opt in
        delay:     float      = 1.0,
        timeout:   int        = 10,
        sources:   list | None = None,
        merge:     bool       = True,
    ) -> None:
        # validate sources
        if sources is not None:
            invalid = [s for s in sources if s not in SOURCES]
            if invalid:
                valid = list(SOURCES.keys())
                raise ValueError(
                    f"Unknown source(s): {invalid}. "
                    f"Valid sources: {valid}"
                )

        self.offline   = offline
        self.auto_save = auto_save
        self.delay     = delay
        self.timeout   = timeout
        self.sources   = sources          # None → DEFAULT_SOURCES
        self.merge     = merge

        self._dm      = DatasetManager()
        self._session = make_session() if not offline else None

    # ── Core ──────────────────────────────────────────────────

    def get(self, word: str, raw: bool = False) -> list[str] | dict:
        """
        একটা শব্দের synonym list return করে।

        Lookup sequence
        ---------------
        1. Local dataset চেক করে (network call নেই)।
        2. না পেলে configured sources থেকে scrape করে।
        3. ``auto_save=True`` হলে result local এ save করে।

        Parameters
        ----------
        word : Bangla শব্দ
        raw  : False (default) → flat list return করে (backward-compatible)
               True            → source metadata সহ dict return করে

        Returns (raw=False)
        -------------------
        list[str]  — e.g. ``['চক্ষু', 'নেত্র', 'লোচন']``

        Returns (raw=True)
        ------------------
        dict::

            {
                "word":          "চোখ",
                "source":        "local" | "wiktionary" | ...,
                "results": [
                    {"synonym": "চক্ষু", "source": "wiktionary"},
                    {"synonym": "নেত্র", "source": "wiktionary"},
                    {"synonym": "আঁখি", "source": "shabdkosh"},
                ],
                "words":         ["চক্ষু", "নেত্র", "আঁখি"],
                "sources_hit":   ["wiktionary", "shabdkosh"],
                "sources_tried": ["wiktionary", "shabdkosh", "english_bangla"],
            }

        Examples
        --------
            sc = Scrapper()
            sc.get("চোখ")           # → ['চক্ষু', 'নেত্র', ...]
            sc.get("চোখ", raw=True) # → {"word": "চোখ", "results": [...], ...}
            sc.get("xyz")           # → []
        """
        word = word.strip()
        if not word:
            return {} if raw else []

        # 1. local dataset first
        cached = self._dm.get(word)
        if cached:
            log.debug("[scrapper] '%s' found in local dataset (%d synonyms)", word, len(cached))
            if raw:
                return {
                    "word":          word,
                    "source":        "local",
                    "results":       [{"synonym": w, "source": "local"} for w in cached],
                    "words":         cached,
                    "sources_hit":   ["local"],
                    "sources_tried": ["local"],
                }
            return cached

        log.debug("[scrapper] '%s' not found in local dataset", word)

        # 2. offline mode — no network
        if self.offline or self._session is None:
            if raw:
                return {
                    "word": word, "source": None,
                    "results": [], "words": [],
                    "sources_hit": [], "sources_tried": [],
                }
            return []

        # 3. online scrape with source cascade
        log.debug("[scrapper] scraping online for '%s'", word)
        raw_result = fetch_with_sources_raw(
            word,
            self._session,
            self.timeout,
            self.sources,
            self.merge,
        )

        if raw_result is None:
            log.warning("[scrapper] all sources returned network errors for '%s'", word)
            if raw:
                return {
                    "word": word, "source": None,
                    "results": [], "words": [],
                    "sources_hit": [], "sources_tried": list(self.active_sources),
                }
            return []

        synonyms = raw_result["words"]

        if synonyms and self.auto_save:
            self._dm.add(word, synonyms)

        if raw:
            # top-level "source" field — first source that contributed
            top_source = raw_result["sources_hit"][0] if raw_result["sources_hit"] else None
            return {**raw_result, "source": top_source}

        return synonyms

    def get_many(self, words: list[str], raw: bool = False) -> dict[str, list | dict]:
        """
        একাধিক শব্দের synonym lookup করে।

        Online requests এর মাঝে ``delay`` seconds অপেক্ষা করে
        যাতে rate-limit এ না পড়তে হয়।

        Parameters
        ----------
        words : Bangla শব্দের list
        raw   : False (default) → ``{word: [synonyms]}``
                True            → ``{word: raw_dict}`` (source metadata সহ)

        Examples
        --------
            sc = Scrapper()
            sc.get_many(["চোখ", "মা"])
            # → {'চোখ': [...], 'মা': [...]}

            sc.get_many(["চোখ", "মা"], raw=True)
            # → {
            #     'চোখ': {"word": "চোখ", "results": [...], "words": [...], ...},
            #     'মা':  {"word": "মা",  "results": [...], "words": [...], ...},
            #   }
        """
        result: dict = {}
        needs_delay = False

        for word in words:
            in_local = self._dm.has(word.strip())
            if needs_delay and not in_local and not self.offline:
                time.sleep(self.delay)

            result[word] = self.get(word, raw=raw)
            needs_delay = not in_local and not self.offline

        return result

    # ── Source info ───────────────────────────────────────────

    @property
    def active_sources(self) -> list[str]:
        """Currently configured sources (expanded DEFAULT_SOURCES if None)."""
        return self.sources if self.sources is not None else list(DEFAULT_SOURCES)

    # ── Dataset helpers ───────────────────────────────────────

    def add(self, word: str, synonyms: list[str]) -> None:
        """Manually add synonyms to local dataset."""
        self._dm.add(word, synonyms)

    def stats(self) -> dict:
        """Print and return dataset statistics."""
        return self._dm.stats()

    def export(self, path: str, fmt: str = "json") -> None:
        """Export local dataset to file (json or csv)."""
        self._dm.export(path, fmt)

    # ── Repr ──────────────────────────────────────────────────

    def __repr__(self) -> str:
        if self.offline:
            mode = "offline"
        else:
            src  = ", ".join(self.active_sources)
            mode = f"online [sources={src}, delay={self.delay}s, merge={self.merge}]"
        return (
            f"Scrapper(mode={mode}, "
            f"auto_save={self.auto_save}, "
            f"words={len(self._dm)})"
        )
