"""
bangla_synonyms._scrapper
--------------------------
``Scrapper`` — the single public class for synonym lookup.

Responsibilities
----------------
- Check the local dataset before making any network call.
- Fall back to live web scraping when a word is not cached.
- Apply quality filtering and optional persistence.
- Provide ``download()`` as a class method so no instance is needed
  to set up the dataset for the first time.

Dataset management (add, remove, export, stats) is handled by
``DatasetManager`` in ``bangla_synonyms.core``.

Public import path::

    from bangla_synonyms import Scrapper
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from .core import (DEFAULT_SOURCES, SOURCES, DatasetManager,
                   fetch_with_sources_raw, reload_dataset)
from .core._wikitext import make_session

log = logging.getLogger(__name__)

_DATASET_URLS = {
    "latest": (
        "https://github.com/raselmeya94/bangla-synonyms/releases/latest/download/"
        "bangla_synonyms_full.json"
    ),
    "mini": (
        "https://github.com/raselmeya94/bangla-synonyms/releases/latest/download/"
        "bangla_synonyms_mini.json"
    ),
}


class Scrapper:
    """
    Bangla synonym lookup with offline-first caching and live web fallback.

    Lookup sequence
    ---------------
    1. Strip whitespace from the input word.
    2. Check the local dataset — fast, no network call.
    3. If not found and ``offline=False``, scrape the configured sources
       in order and apply the quality pipeline to the merged results.
    4. If ``auto_save=True``, persist the scraped result to disk so the
       next lookup for this word is served from cache.

    Download the dataset once before first use::

        Scrapper.download()

        sc = Scrapper()
        sc.get("চোখ")              # → ['চক্ষু', 'নেত্র', 'লোচন', ...]
        sc.get_many(["চোখ", "মা"]) # → {'চোখ': [...], 'মা': [...]}

    For dataset management (add, remove, export, stats) use
    ``DatasetManager`` from ``bangla_synonyms.core`` directly.

    Parameters
    ----------
    offline : bool, default False
        Use the local dataset only; make no network calls.
        Useful for air-gapped environments or offline processing.
    auto_save : bool, default False
        Persist scraped results to disk after each successful lookup so
        they are served from cache on the next call.  Opt-in to avoid
        unexpected disk writes.
    delay : float, default 1.0
        Seconds to wait between HTTP requests inside ``get_many()``.
        Applies only to live network calls — local cache hits are instant.
        Increase this for polite scraping or slow connections.
    timeout : int, default 10
        HTTP request timeout in seconds per source.
    sources : list[str] | None, default None
        Which scraping sources to query.  ``None`` uses all three in
        default order: Wiktionary → Shabdkosh → English-Bangla.
        Valid values: ``"wiktionary"``, ``"shabdkosh"``, ``"english_bangla"``.
    merge : bool, default True
        ``True``  — query every active source and merge their results.
        ``False`` — stop at the first source that returns any results
                    (faster, lower coverage).

    Common patterns
    ---------------
    +-------------------------------------------+-------------------------------+
    | ``Scrapper()``                            | online, all sources, no save  |
    +-------------------------------------------+-------------------------------+
    | ``Scrapper(offline=True)``                | local dataset only            |
    +-------------------------------------------+-------------------------------+
    | ``Scrapper(auto_save=True)``              | scrape and persist results    |
    +-------------------------------------------+-------------------------------+
    | ``Scrapper(sources=["wiktionary"])``      | Wiktionary only               |
    +-------------------------------------------+-------------------------------+
    | ``Scrapper(merge=False)``                 | stop at first source with hit |
    +-------------------------------------------+-------------------------------+
    | ``Scrapper(delay=2.0, timeout=15)``       | polite / slow-connection mode |
    +-------------------------------------------+-------------------------------+
    """

    # ------------------------------------------------------------------
    # Class method — no instance needed
    # ------------------------------------------------------------------

    @classmethod
    def download(cls, version: str = "latest", force: bool = False) -> None:
        """
        Download the pre-built Bangla synonym dataset from GitHub Releases.

        Saves to ``./bangla_synonyms_data/dataset.json`` relative to the
        current working directory.  All running ``Scrapper`` and
        ``DatasetManager`` instances pick up the new data immediately
        without a restart.

        Parameters
        ----------
        version : str, default "latest"
            ``"latest"`` — full dataset (~10 000 words, ~3 MB).
            ``"mini"``   — small starter set (~500 words, ~150 KB).
        force : bool, default False
            Re-download even if the dataset file already exists on disk.

        Examples
        --------
            Scrapper.download()               # full dataset
            Scrapper.download("mini")         # small starter set
            Scrapper.download(force=True)     # force re-download
        """
        import requests as _requests

        url = _DATASET_URLS.get(version)
        if url is None:
            available = ", ".join(f'"{v}"' for v in _DATASET_URLS)
            print(
                f"[bangla-synonyms] unknown version '{version}'. available: {available}"
            )
            return

        save_path = Path.cwd() / "bangla_synonyms_data" / "dataset.json"

        if save_path.exists() and not force:
            print(f"[bangla-synonyms] dataset already exists at {save_path}")
            print("[bangla-synonyms] use Scrapper.download(force=True) to re-download.")
            return

        save_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[bangla-synonyms] downloading '{version}' dataset...")
        print(f"[bangla-synonyms] source : {url}")
        print(f"[bangla-synonyms] saving : {save_path}")

        try:
            resp = _requests.get(url, stream=True, timeout=30)
            resp.raise_for_status()
        except _requests.exceptions.Timeout:
            print(
                "[bangla-synonyms] download timed out. check your connection and try again."
            )
            return
        except _requests.exceptions.ConnectionError:
            print(
                "[bangla-synonyms] could not connect. check your internet connection."
            )
            return
        except _requests.exceptions.HTTPError as e:
            print(f"[bangla-synonyms] server returned HTTP {e.response.status_code}.")
            return
        except _requests.exceptions.RequestException as e:
            print(f"[bangla-synonyms] download failed: {e}")
            return

        total = int(resp.headers.get("content-length", 0))
        received = 0
        bar_width = 30

        try:
            with open(save_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    fh.write(chunk)
                    received += len(chunk)
                    if total:
                        pct = received / total
                        filled = int(bar_width * pct)
                        bar = "█" * filled + "░" * (bar_width - filled)
                        kb = received // 1024
                        print(f"\r  [{bar}] {kb} KB", end="", flush=True)
        except OSError as e:
            print(f"\n[bangla-synonyms] failed to write file: {e}")
            return

        print(f"\r  [{'█' * bar_width}] done          ")
        print(f"[bangla-synonyms] ✓ dataset ready at {save_path}")
        reload_dataset()

    # ------------------------------------------------------------------
    # Instance
    # ------------------------------------------------------------------

    def __init__(
        self,
        offline: bool = False,
        auto_save: bool = False,
        delay: float = 1.0,
        timeout: int = 10,
        sources: list | None = None,
        merge: bool = True,
    ) -> None:
        if sources is not None:
            invalid = [s for s in sources if s not in SOURCES]
            if invalid:
                raise ValueError(
                    f"Unknown source(s): {invalid}. "
                    f"Valid sources: {list(SOURCES.keys())}"
                )

        self.offline = offline
        self.auto_save = auto_save
        self.delay = delay
        self.timeout = timeout
        self.sources = sources
        self.merge = merge

        self._dm = DatasetManager()
        self._session = make_session() if not offline else None

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, word: str, raw: bool = False) -> list | dict:
        """
        Return synonyms for a single Bangla word.

        Checks the local dataset first.  If the word is not cached and
        ``offline=False``, falls back to live web scraping.

        Parameters
        ----------
        word : str
            The Bangla word to look up.
        raw : bool, default False
            ``False`` — return a plain ``list[str]`` of synonyms.
            ``True``  — return a metadata ``dict`` with per-source
                        breakdown and a ``"quality"`` field (see below).

        Returns
        -------
        list[str]
            When ``raw=False``.  Empty list ``[]`` when nothing is found.

        dict
            When ``raw=True``::

                {
                    "word":   "চোখ",
                    "source": "wiktionary",      # primary source, or "local"
                    "sources_results": {         # raw per-source output
                        "wiktionary":     ["চক্ষু", "নেত্র", "লোচন", "আঁখি"],
                        "shabdkosh":      ["অক্ষি", "আঁখি", "কেন্দ্র"],
                        "english_bangla": ["চক্ষু", "দৃষ্টি"],
                    },
                    "results": [                 # filtered entries only
                        {"synonym": "চক্ষু", "source": "wiktionary"},
                        {"synonym": "নেত্র", "source": "wiktionary"},
                        {"synonym": "আঁখি", "source": "shabdkosh",
                         "confirmed": True},
                    ],
                    "words":         ["চক্ষু", "নেত্র", "আঁখি"],
                    "sources_hit":   ["wiktionary", "shabdkosh"],
                    "sources_tried": ["wiktionary", "shabdkosh", "english_bangla"],
                    "quality":       "wikiconfirmed",
                }

            ``sources_results`` always uses the source name as key —
            ``"local"`` for cache hits, scraper names for live results.
            This keeps the structure consistent regardless of where the
            data came from.

            ``confirmed: True`` is set on entries from secondary sources
            that passed cross-source validation.  Wiktionary entries are
            always authoritative and never carry this flag.

        Examples
        --------
            sc = Scrapper()
            sc.get("চোখ")            # → ['চক্ষু', 'নেত্র', ...]
            sc.get("চোখ", raw=True)  # → {"word": "চোখ", "results": [...], ...}
            sc.get("xyz")            # → []
        """
        word = word.strip()
        if not word:
            return {} if raw else []

        # 1. Local dataset — no network call
        cached = self._dm.get(word)
        if cached:
            log.debug(
                "[scrapper] '%s' found in local dataset (%d synonyms)",
                word,
                len(cached),
            )
            if raw:
                return {
                    "word": word,
                    "source": "local",
                    "sources_results": {"local": cached},
                    "results": [{"synonym": w, "source": "local"} for w in cached],
                    "words": cached,
                    "sources_hit": ["local"],
                    "sources_tried": ["local"],
                    "quality": "local",
                }
            return cached

        # 2. Offline mode — no network allowed
        if self.offline or self._session is None:
            if raw:
                return {
                    "word": word,
                    "source": None,
                    "sources_results": {},
                    "results": [],
                    "words": [],
                    "sources_hit": [],
                    "sources_tried": [],
                    "quality": "empty",
                }
            return []

        # 3. Live scrape
        log.debug("[scrapper] fetching online for '%s'", word)
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
                    "word": word,
                    "source": None,
                    "sources_results": {},
                    "results": [],
                    "words": [],
                    "sources_hit": [],
                    "sources_tried": list(self.active_sources),
                    "quality": "empty",
                }
            return []

        synonyms = raw_result["words"]
        if synonyms and self.auto_save:
            self._dm.add(word, synonyms)

        if raw:
            top_source = (
                raw_result["sources_hit"][0] if raw_result["sources_hit"] else None
            )
            return {**raw_result, "source": top_source}

        return synonyms

    def get_many(self, words: list, raw: bool = False) -> dict:
        """
        Return synonyms for multiple Bangla words.

        A polite ``delay``-second pause is inserted between live HTTP
        requests to avoid overloading sources.  Local cache hits incur
        no delay and do not count toward the rate limit.

        Parameters
        ----------
        words : list[str]
            Bangla words to look up.
        raw : bool, default False
            ``False`` — ``{word: list[str]}``.
            ``True``  — ``{word: dict}`` with full source metadata per word.

        Returns
        -------
        dict
            Keys are the input words in the same order they were provided.
            Values are synonym lists (``raw=False``) or metadata dicts
            (``raw=True``).  Words with no results map to ``[]`` or an
            empty-result dict respectively.

        Examples
        --------
            sc = Scrapper()
            sc.get_many(["চোখ", "মা"])
            # → {'চোখ': ['চক্ষু', ...], 'মা': ['জননী', ...]}

            sc.get_many(["চোখ", "মা"], raw=True)
            # → {'চোখ': {"word": "চোখ", ...}, 'মা': {"word": "মা", ...}}
        """
        result: dict = {}
        needs_delay = False

        for word in words:
            is_cached = self._dm.has(word.strip())
            if needs_delay and not is_cached and not self.offline:
                time.sleep(self.delay)
            result[word] = self.get(word, raw=raw)
            needs_delay = not is_cached and not self.offline

        return result

    # ------------------------------------------------------------------
    # Source info
    # ------------------------------------------------------------------

    @property
    def active_sources(self) -> list:
        """
        The list of source keys that will be queried on a live lookup.

        Returns the full ``DEFAULT_SOURCES`` list when no explicit
        ``sources`` were provided at construction time.

        Examples
        --------
            Scrapper().active_sources
            # → ["wiktionary", "shabdkosh", "english_bangla"]

            Scrapper(sources=["wiktionary"]).active_sources
            # → ["wiktionary"]
        """
        return self.sources if self.sources is not None else list(DEFAULT_SOURCES)

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        if self.offline:
            mode = "offline"
        else:
            src = ", ".join(self.active_sources)
            mode = f"online [sources={src}, delay={self.delay}s, merge={self.merge}]"
        return f"Scrapper(mode={mode}, auto_save={self.auto_save})"

    def __dir__(self) -> list:
        """Expose only public Scrapper attributes in autocomplete."""
        return [
            "download",
            "get",
            "get_many",
            "active_sources",
            "offline",
            "auto_save",
            "delay",
            "timeout",
            "sources",
            "merge",
        ]
