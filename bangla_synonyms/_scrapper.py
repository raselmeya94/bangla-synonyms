"""
bangla_synonyms._scrapper
--------------------------
Scrapper — full control over scraping behaviour.

Public import path: ``from bangla_synonyms import Scrapper``
"""
from __future__ import annotations

import time

from .core._wikitext import fetch_synonyms, make_session
from .core import DatasetManager, _save


class Scrapper:
    """
    Scrape synonyms from Wiktionary with full parameter control.

    Parameters
    ----------
    offline    : bool  — no internet; local dataset only   (default: False)
    auto_save  : bool  — persist scraped results locally   (default: True)
    delay      : float — seconds to wait between requests  (default: 1.0)
    timeout    : int   — HTTP request timeout in seconds   (default: 10)

    Behaviour when ``offline`` is omitted (default)
    -----------------------------------------------
    The scrapper always checks the local dataset first.
    If the word is not found locally it falls back to live
    Wiktionary, so you get the best of both worlds without
    any manual configuration.

    Quick patterns
    --------------
    +-------------------------------------------+----------------------------------+
    | ``Scrapper()``                            | online, auto-save, delay 1 s     |
    +-------------------------------------------+----------------------------------+
    | ``Scrapper(offline=True)``                | local dataset only, no HTTP      |
    +-------------------------------------------+----------------------------------+
    | ``Scrapper(auto_save=False)``             | scrape but never write to disk   |
    +-------------------------------------------+----------------------------------+
    | ``Scrapper(delay=2.0, timeout=15)``       | polite / slow connection         |
    +-------------------------------------------+----------------------------------+

    Example
    -------
        from bangla_synonyms import Scrapper

        sc = Scrapper()
        sc.get("চোখ")                      # local-first, then online
        sc.get_many(["চোখ", "মা", "নদী"])

        sc_offline = Scrapper(offline=True)
        sc_offline.get("মা")               # local only – no network call

        sc_custom = Scrapper(delay=2.0, timeout=15, auto_save=False)
        sc_custom.get("আকাশ")
    """

    def __init__(
        self,
        offline:   bool  = False,
        auto_save: bool  = True,
        delay:     float = 1.0,
        timeout:   int   = 10,
    ) -> None:
        self.offline   = offline
        self.auto_save = auto_save
        self.delay     = delay
        self.timeout   = timeout

        self._dm      = DatasetManager()
        self._session = make_session() if not offline else None

    # ── Core ──────────────────────────────────────────────────

    def get(self, word: str) -> list[str]:
        """
        Get synonyms for a single word.

        Flow
        ----
        1. Strip whitespace.
        2. Check local dataset (fast, no network).
        3. If not found **and** ``offline=False``, query Wiktionary.
        4. If ``auto_save=True``, persist the result for next time.

        Returns ``[]`` if nothing is found anywhere.

        Example
        -------
            sc = Scrapper()
            sc.get("চোখ")    # → ['চক্ষু', 'নেত্র', 'লোচন', ...]
            sc.get("xyz")    # → []
        """
        word = word.strip()

        # 1. check local dataset first
        cached = self._dm.get(word)
        if cached:
            return cached

        # 2. not found locally
        print(f"[local] '{word}' not found in local dataset.")

        # 3. go online
        if not self.offline and self._session:
            print(f"[online] scraping Wiktionary for '{word}'…")
            synonyms = fetch_synonyms(word, self._session, self.timeout)
            if synonyms:
                if self.auto_save:
                    self._dm.add(word, synonyms)
                return synonyms

        return []

    def get_many(self, words: list[str]) -> dict[str, list[str]]:
        """
        Get synonyms for multiple words.

        Respects ``delay`` between online requests to avoid rate-limits.

        Example
        -------
            sc = Scrapper()
            sc.get_many(["চোখ", "মা", "আকাশ"])
            # → {'চোখ': [...], 'মা': [...], 'আকাশ': [...]}
        """
        result: dict[str, list[str]] = {}
        for i, word in enumerate(words):
            result[word] = self.get(word)
            if not self.offline and i < len(words) - 1:
                time.sleep(self.delay)
        return result

    # ── Repr ──────────────────────────────────────────────────

    def __repr__(self) -> str:
        mode = "offline" if self.offline else f"online (delay={self.delay}s)"
        return (
            f"Scrapper(mode={mode}, "
            f"auto_save={self.auto_save}, "
            f"words={len(self._dm)})"
        )
