"""
bangla_synonyms.core
---------------------
Lower-level building blocks for power users and researchers.

This module is not needed for everyday synonym lookup — use the top-level
``bangla_synonyms`` API (``bs.get``, ``bs.get_many``) or ``Scrapper`` for
that.  Import from here when you need direct control over the dataset,
bulk scraping, or word-list management.

Classes
-------
DatasetManager
    Direct read/write/export access to the local synonym dataset.
    All instances share the same in-memory store, so changes made through
    one instance are immediately visible through any other.

WordlistFetcher
    Fetches Bangla word lists from Wiktionary's ``allpages`` API.
    Used to seed ``BatchScraper`` with words to scrape.

BatchScraper
    Scrapes synonyms for large word lists with progress tracking,
    periodic checkpointing, and safe resume support.

Source registry
---------------
Sources are plain callables registered in the ``SOURCES`` dict.  The
default cascade queries all three web sources in reliability order:

    SOURCES = {
        "wiktionary":     bn.wiktionary.org  — structured wikitext, most reliable
        "shabdkosh":      shabdkosh.com       — good coverage, clean output
        "english_bangla": english-bangla.com  — last resort, near-synonyms only
    }

    DEFAULT_SOURCES = ["wiktionary", "shabdkosh", "english_bangla"]

Pass ``sources=["wiktionary"]`` anywhere to restrict to a single source,
or ``merge=False`` to stop at the first source that returns any results.

Embedding source (future / opt-in)
------------------------------------
A BNLP word-vector source is planned but not yet active.  It will not be
in ``DEFAULT_SOURCES`` even when released because it requires a separate
model download (~hundreds of MB).  It will be opt-in only:

    # NOT YET AVAILABLE — shown here for future reference
    from bangla_synonyms.core import register_embedding_source

    register_embedding_source()                      # word2vec, top-10
    register_embedding_source(backend="fasttext")    # FastText (handles OOV)
    register_embedding_source(add_to_defaults=True)  # add to default pipeline

    # once registered, use like any other source:
    bs.get("চোখ", sources=["wiktionary", "embedding"])
    bs.get("চোখ", sources=["embedding"])

Quick start
-----------
    from bangla_synonyms.core import DatasetManager, WordlistFetcher, BatchScraper

    # Dataset management
    dm = DatasetManager()
    dm.stats()
    dm.add("নদী", ["তটিনী", "প্রবাহিনী"])
    dm.remove("শব্দ")
    dm.merge("extra.json")
    dm.export("output.csv", fmt="csv")

    # Word list + bulk scraping
    wf    = WordlistFetcher()
    words = wf.fetch(limit=500)
    new   = wf.filter_new(words, dm)   # skip words already in the dataset

    scraper = BatchScraper(delay=1.0)
    scraper.run(new)
    scraper.run(new, sources=["wiktionary"])
    scraper.run_from_wiktionary(limit=1000)
"""
from __future__ import annotations

import csv
import json
import logging
import time
from pathlib import Path

from ._embedding import EmbeddingSource
from ._embedding import fetch_embedding as _fetch_embedding
from ._embedding import register_embedding_source
from ._english_bangla import fetch_english_bangla as _fetch_english_bangla
from ._quality import apply_quality
from ._shabdkosh import fetch_shabdkosh as _fetch_shabdkosh
from ._wikitext import fetch_synonyms as _fetch_wiktionary
from ._wikitext import fetch_word_list, make_session

log = logging.getLogger(__name__)

__all__ = [
    "SOURCES",
    "DEFAULT_SOURCES",
    "fetch_with_sources",
    "fetch_with_sources_raw",
    "apply_quality",
    "DatasetManager",
    "WordlistFetcher",
    "BatchScraper",
    "reload_dataset",
    "make_session",
    "EmbeddingSource",
    "register_embedding_source",
]


# ===========================================================================
# Source registry
# ===========================================================================

#: All registered scraping sources.
#: Each value is a callable: ``(word, session, timeout) -> list[str] | None``.
#: Returns ``None`` on network error, ``[]`` when the word is not found.
SOURCES: dict[str, object] = {
    "wiktionary": _fetch_wiktionary,
    "shabdkosh": _fetch_shabdkosh,
    "english_bangla": _fetch_english_bangla,
}

#: Default source order — most reliable first.
#: The embedding source is intentionally excluded; it must be opted into
#: explicitly via ``register_embedding_source(add_to_defaults=True)``.
DEFAULT_SOURCES: list[str] = ["wiktionary", "shabdkosh", "english_bangla"]


# ===========================================================================
# Source-level fetch helpers
# ===========================================================================


def fetch_with_sources(
    word: str,
    session,
    timeout: int = 10,
    sources: list | None = None,
    merge: bool = True,
) -> list | None:
    """
    Fetch synonyms from the configured sources and return a flat list.

    A convenience wrapper around ``fetch_with_sources_raw`` that strips
    source metadata and returns only the synonym list.  Use
    ``fetch_with_sources_raw`` directly when you need per-source
    attribution or the ``quality`` field.

    Parameters
    ----------
    word : str
        The Bangla word to look up.
    session : requests.Session
        A session created by ``make_session()``.  Reuse across calls to
        benefit from connection pooling and retry logic.
    timeout : int, default 10
        HTTP request timeout in seconds per source.
    sources : list[str] | None, default None
        Which sources to query.  ``None`` uses all three in default order.
        Examples: ``["wiktionary"]``, ``["wiktionary", "shabdkosh"]``.
    merge : bool, default True
        ``True``  — query every active source and merge their results.
        ``False`` — stop at the first source that returns any results.

    Returns
    -------
    list[str]
        Synonyms found after quality filtering.  May be empty.
    None
        Every active source returned a network error — no data at all.

    Examples
    --------
        from bangla_synonyms.core import fetch_with_sources, make_session

        session = make_session()
        fetch_with_sources("চোখ", session)
        fetch_with_sources("চোখ", session, sources=["wiktionary"])
        fetch_with_sources("চোখ", session, merge=False)
    """
    raw = fetch_with_sources_raw(word, session, timeout, sources, merge)
    if raw is None:
        return None
    return raw["words"]


def fetch_with_sources_raw(
    word: str,
    session,
    timeout: int = 10,
    sources: list | None = None,
    merge: bool = True,
) -> dict | None:
    """
    Fetch synonyms from the configured sources and return full metadata.

    Queries each active source in order, merges the raw results, applies
    the quality pipeline (noise filter + cross-source validation), and
    returns a structured result dict.

    Parameters
    ----------
    word : str
        The Bangla word to look up.
    session : requests.Session
        A session created by ``make_session()``.
    timeout : int, default 10
        HTTP request timeout in seconds per source.
    sources : list[str] | None, default None
        Which sources to query.  ``None`` uses all three in default order.
    merge : bool, default True
        ``True``  — query every active source and merge their results.
        ``False`` — stop at the first source that returns any results.

    Returns
    -------
    dict
        Always returned when at least one source responded (even if all
        returned empty lists)::

            {
                "word": "চোখ",

                "sources_results": {
                    # raw unfiltered output from each source
                    "wiktionary":     ["চক্ষু", "নেত্র", "লোচন", "আঁখি", "নয়ন"],
                    "shabdkosh":      ["অক্ষি", "আঁখি", "চক্ষু", "কেন্দ্র", "মাঝে"],
                    "english_bangla": ["চক্ষু", "দৃষ্টি", "নয়ন"],
                },

                "results": [
                    # filtered entries that survived the quality pipeline
                    {"synonym": "চক্ষু", "source": "wiktionary"},
                    {"synonym": "নেত্র", "source": "wiktionary"},
                    {"synonym": "আঁখি", "source": "shabdkosh", "confirmed": True},
                ],

                "words":         ["চক্ষু", "নেত্র", "আঁখি"],
                "sources_hit":   ["wiktionary", "shabdkosh"],
                "sources_tried": ["wiktionary", "shabdkosh", "english_bangla"],
                "quality":       "wikiconfirmed",
            }

        ``sources_results`` shows what each scraper returned *before*
        quality filtering.  Comparing it with ``results`` reveals exactly
        which entries were dropped and why.

        ``confirmed: True`` is set on entries from secondary sources that
        were validated against Wiktionary.  Wiktionary entries are always
        authoritative and never carry this flag.

        ``quality`` values:

        ==================  =====================================================
        ``"wikiconfirmed"`` Wiktionary present; secondaries filtered by it.
        ``"cross_source"``  No Wiktionary; entries confirmed by ≥2 sources.
        ``"single_source"`` Only one source; noise-cleaned results as-is.
        ``"empty"``         Nothing survived filtering or word not found.
        ==================  =====================================================

    None
        Every active source returned a network error — no data at all.
        Distinct from an empty result: here we have no information, not
        just a word that happens to have no synonyms.

    Examples
    --------
        from bangla_synonyms.core import fetch_with_sources_raw, make_session

        session = make_session()
        raw = fetch_with_sources_raw("চোখ", session)
        raw["words"]        # → ['চক্ষু', 'নেত্র', ...]
        raw["sources_hit"]  # → ['wiktionary', 'shabdkosh']
        raw["quality"]      # → 'wikiconfirmed'
    """
    active = sources if sources is not None else DEFAULT_SOURCES
    results: list[dict] = []
    seen: set[str] = set()
    any_error = False
    sources_hit: list[str] = []
    sources_results: dict[str, list[str]] = {}

    for name in active:
        fn = SOURCES.get(name)
        if fn is None:
            log.warning("[sources] unknown source '%s' — skipping", name)
            continue

        log.debug("[sources] querying '%s' for '%s'", name, word)
        result = fn(word, session, timeout)  # type: ignore[call-arg]

        if result is None:
            log.warning("[sources] network error from '%s' for '%s'", name, word)
            any_error = True
            continue

        if result:
            sources_results[name] = list(result)
            added = 0
            for w in result:
                if w not in seen:
                    seen.add(w)
                    results.append({"synonym": w, "source": name})
                    added += 1
            if added:
                sources_hit.append(name)
                log.debug(
                    "[sources] '%s' contributed %d synonym(s) for '%s'",
                    name,
                    added,
                    word,
                )

            if not merge:
                break

    if results:
        raw_out = {
            "word": word,
            "sources_results": sources_results,
            "results": results,
            "words": [r["synonym"] for r in results],
            "sources_hit": sources_hit,
            "sources_tried": list(active),
        }
        return apply_quality(raw_out)

    if any_error and not results:
        return None

    return {
        "word": word,
        "sources_results": {},
        "results": [],
        "words": [],
        "sources_hit": [],
        "sources_tried": list(active),
        "quality": "empty",
    }


# ===========================================================================
# Dataset path + shared in-memory store
# ===========================================================================


def _dataset_path() -> Path:
    """Return the dataset path relative to the current working directory."""
    return Path.cwd() / "bangla_synonyms_data" / "dataset.json"


# Module-level singleton — all DatasetManager instances share the same dict.
# This means a write through one instance is instantly visible through all
# others, including the one held by the module-level ``_default`` Scrapper.
_SHARED: dict | None = None


def _ensure_shared() -> dict:
    global _SHARED
    if _SHARED is None:
        _SHARED = _load()
    return _SHARED


def reload_dataset() -> None:
    """
    Reload the dataset from disk and replace the in-memory cache.

    Called automatically after ``Scrapper.download()`` so all running
    instances see the new data without a restart.  You can also call this
    manually after editing ``dataset.json`` externally.
    """
    global _SHARED
    _SHARED = _load()


# ===========================================================================
# Disk I/O helpers (internal)
# ===========================================================================


def _load() -> dict:
    """Load the dataset JSON from disk. Returns {} if missing or unreadable."""
    path = _dataset_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            log.debug("[dataset] loaded %d words from %s", len(data), path)
            return data
        except (json.JSONDecodeError, OSError) as exc:
            log.error("[dataset] failed to read %s: %s", path, exc)
    log.info("[dataset] no dataset at %s", path)
    return {}


def _save(data: dict) -> None:
    """Flush ``data`` to disk as pretty-printed JSON. Raises OSError on failure."""
    path = _dataset_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.debug("[dataset] saved %d words to %s", len(data), path)
    except OSError as exc:
        log.error("[dataset] failed to write dataset: %s", exc)
        raise


# ===========================================================================
# DatasetManager
# ===========================================================================


class DatasetManager:
    """
    Direct read/write/export access to the local synonym dataset.

    All instances share the same in-memory dictionary (module-level
    ``_SHARED``).  A change made through one instance is immediately
    visible through any other — including the instance held internally
    by ``Scrapper``.

    Dataset location
    ----------------
    ``./bangla_synonyms_data/dataset.json`` relative to the current
    working directory when the module is first imported.

    Write behaviour
    ---------------
    Every write method (``add``, ``remove``, ``update``) flushes to disk
    immediately by default.  Pass ``save=False`` to batch multiple writes
    into a single flush::

        dm.add("ক", ["খ", "গ"], save=False)
        dm.add("ঘ", ["ঙ"],      save=False)
        dm.export("synonyms.json")   # single flush

    Examples
    --------
        from bangla_synonyms.core import DatasetManager

        dm = DatasetManager()
        dm.stats()
        dm.add("শব্দ", ["প্রতিশব্দ১", "প্রতিশব্দ২"])
        dm.update("শব্দ", ["নতুন১", "নতুন২"])   # replaces, not merges
        dm.remove("শব্দ")
        dm.merge("extra.json")
        dm.export("output.json")
        dm.export("output.csv", fmt="csv")
    """

    def __init__(self) -> None:
        # No instance state — all data lives in the module-level _SHARED dict.
        pass

    @property
    def _data(self) -> dict:
        return _ensure_shared()

    @_data.setter
    def _data(self, value: dict) -> None:
        global _SHARED
        _SHARED = value

    def reload(self) -> None:
        """Reload the dataset from disk, picking up any external changes."""
        reload_dataset()

    # -----------------------------------------------------------------------
    # Read
    # -----------------------------------------------------------------------

    def get(self, word: str) -> list:
        """
        Return the synonym list for ``word``.

        Returns an empty list ``[]`` if the word is not in the dataset.
        The returned list is a copy — mutating it does not affect the dataset.
        """
        return list(self._data.get(word, []))

    def has(self, word: str) -> bool:
        """Return ``True`` if ``word`` is present in the dataset."""
        return word in self._data

    def all_words(self) -> list:
        """Return a sorted list of every word in the dataset."""
        return sorted(self._data.keys())

    def __contains__(self, word: str) -> bool:
        """Support ``"চোখ" in dm`` membership test."""
        return self.has(word)

    def __len__(self) -> int:
        """Return the number of words in the dataset."""
        return len(self._data)

    # -----------------------------------------------------------------------
    # Write
    # -----------------------------------------------------------------------

    def add(self, word: str, synonyms: list, save: bool = True) -> None:
        """
        Add synonyms for ``word``, merging with any existing entries.

        Duplicate synonyms (already in the dataset for this word) are
        silently ignored.  The lookup word itself is never added as its
        own synonym.

        Parameters
        ----------
        word : str
            The Bangla word to add synonyms for.
        synonyms : list[str]
            Synonyms to add.  Whitespace is stripped from each entry.
        save : bool, default True
            Flush to disk immediately.  Pass ``False`` when batching
            many writes — call ``export()`` manually at the end.

        Examples
        --------
            dm.add("পরিবেশ", ["প্রকৃতি", "জগত", "বিশ্ব"])
            dm.add("পরিবেশ", ["আবহাওয়া"])   # appends, does not replace
        """
        word = word.strip()
        if not word:
            return

        existing = set(self._data.get(word, []))
        merged = list(self._data.get(word, []))
        for s in synonyms:
            s = s.strip()
            if s and s not in existing and s != word:
                merged.append(s)
                existing.add(s)

        self._data[word] = merged
        if save:
            _save(self._data)

    def remove(self, word: str, save: bool = True) -> bool:
        """
        Remove ``word`` and all its synonyms from the dataset.

        Parameters
        ----------
        word : str
            The word to remove.
        save : bool, default True
            Flush to disk immediately.

        Returns
        -------
        bool
            ``True`` if the word existed and was removed, ``False`` if it
            was not in the dataset.
        """
        if word in self._data:
            del self._data[word]
            if save:
                _save(self._data)
            return True
        return False

    def update(self, word: str, synonyms: list, save: bool = True) -> None:
        """
        Replace the synonym list for ``word`` entirely.

        Unlike ``add()``, this discards any existing synonyms and sets the
        list to exactly ``synonyms``.  Use ``add()`` when you want to
        preserve existing entries.

        Parameters
        ----------
        word : str
            The word whose synonym list will be replaced.
        synonyms : list[str]
            The new synonym list.  Whitespace is stripped; the word itself
            is excluded if it appears in the list.
        save : bool, default True
            Flush to disk immediately.
        """
        word = word.strip()
        if not word:
            return
        self._data[word] = [
            s.strip() for s in synonyms if s.strip() and s.strip() != word
        ]
        if save:
            _save(self._data)

    # -----------------------------------------------------------------------
    # Merge
    # -----------------------------------------------------------------------

    def merge(self, path: str) -> int:
        """
        Merge synonyms from an external JSON file into the dataset.

        New words are added in full.  For words already in the dataset,
        only new synonyms (not already present) are appended — existing
        entries are never overwritten.

        Parameters
        ----------
        path : str
            Path to a JSON file in the same format as ``dataset.json``::

                {
                    "নদী": ["তটিনী", "প্রবাহিনী", "সরিৎ"],
                    "আকাশ": ["গগন", "অম্বর", "নভ"]
                }

        Returns
        -------
        int
            Number of *new* words added (words not previously in the
            dataset).  Words that were already present but received new
            synonyms are not counted.

        Raises
        ------
        ValueError
            If the file cannot be read or is not valid JSON.
        """
        try:
            with open(path, encoding="utf-8") as fh:
                incoming: dict = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"Failed to merge dataset from '{path}': {exc}") from exc

        added = 0
        for word, syns in incoming.items():
            if word not in self._data:
                self._data[word] = syns
                added += 1
            else:
                existing = set(self._data[word])
                self._data[word] += [s for s in syns if s not in existing]

        _save(self._data)
        return added

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------

    def export(self, path: str, fmt: str = "json") -> None:
        """
        Export the entire dataset to a file.

        Parameters
        ----------
        path : str
            Output file path.  The parent directory must already exist.
        fmt : str, default "json"
            ``"json"`` — pretty-printed JSON, alphabetically sorted by word.
            ``"csv"``  — one row per word, pipe-separated synonyms::

                word,synonyms,count
                চোখ,চক্ষু | নেত্র | লোচন | আঁখি,4
                মা,জননী | আম্মা | জন্মদাত্রী,3

        Raises
        ------
        ValueError
            If ``fmt`` is not ``"json"`` or ``"csv"``.
        OSError
            If the file cannot be written.

        Examples
        --------
            dm.export("synonyms.json")
            dm.export("synonyms.csv", fmt="csv")
        """
        if fmt not in ("json", "csv"):
            raise ValueError(f"Unknown format '{fmt}'. Choose 'json' or 'csv'.")

        p = Path(path)
        try:
            if fmt == "json":
                p.write_text(
                    json.dumps(
                        dict(sorted(self._data.items())),
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            else:
                with open(p, "w", encoding="utf-8", newline="") as fh:
                    writer = csv.writer(fh)
                    writer.writerow(["word", "synonyms", "count"])
                    for word, syns in sorted(self._data.items()):
                        writer.writerow([word, " | ".join(syns), len(syns)])
        except OSError as exc:
            raise OSError(f"Failed to export to '{path}': {exc}") from exc

        print(f"[bangla-synonyms] exported {len(self._data)} words → {path}")

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    def stats(self) -> dict:
        """
        Print dataset statistics to stdout and return them as a dict.

        Output example::

            Words         : 9842
            Total synonyms: 47391
            Avg / word    : 4.82
            Source        : /home/user/bangla_synonyms_data/dataset.json
            Top 5 words   :
              চোখ: চক্ষু, নেত্র, লোচন, আঁখি ...
              মা: জননী, আম্মা, জন্মদাত্রী ...

        Returns
        -------
        dict
            Keys: ``total_words``, ``total_synonyms``, ``avg_per_word``,
            ``source``.
        """
        total_syns = sum(len(v) for v in self._data.values())
        avg = round(total_syns / len(self._data), 2) if self._data else 0
        top5 = sorted(self._data.items(), key=lambda x: len(x[1]), reverse=True)[:5]
        path = _dataset_path()
        source = str(path) if path.exists() else "no dataset — run Scrapper.download()"

        result = {
            "total_words": len(self._data),
            "total_synonyms": total_syns,
            "avg_per_word": avg,
            "source": source,
        }

        print(f"Words         : {result['total_words']}")
        print(f"Total synonyms: {result['total_synonyms']}")
        print(f"Avg / word    : {result['avg_per_word']}")
        print(f"Source        : {result['source']}")
        if top5:
            print("Top 5 words   :")
            for word, syns in top5:
                preview = ", ".join(syns[:4])
                suffix = " ..." if len(syns) > 4 else ""
                print(f"  {word}: {preview}{suffix}")

        return result


# ===========================================================================
# WordlistFetcher
# ===========================================================================


class WordlistFetcher:
    """
    Fetch Bangla word lists from Wiktionary's ``allpages`` API.

    Used to seed ``BatchScraper`` with a large set of real Bangla words.
    Wiktionary is the only word-list source available — ``_shabdkosh.py``
    and ``_english_bangla.py`` have no equivalent API.

    Parameters
    ----------
    timeout : int, default 10
        HTTP request timeout in seconds for each Wiktionary API call.

    Examples
    --------
        from bangla_synonyms.core import WordlistFetcher, DatasetManager

        wf = WordlistFetcher()
        dm = DatasetManager()

        words     = wf.fetch(limit=500)
        new_words = wf.filter_new(words, dm)   # skip already-scraped words

        wf.save(words, "wordlist.txt")          # persist for later
        words = wf.load("wordlist.txt")         # reload
    """

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout
        self._session = make_session()

    def fetch(self, limit: int = 500) -> list:
        """
        Fetch up to ``limit`` Bangla words from Wiktionary.

        Uses the ``allpages`` API (namespace 0) starting from the first
        Bangla character.  Pages whose titles contain non-Bangla characters
        are filtered out automatically.

        Parameters
        ----------
        limit : int, default 500
            Maximum number of words to return.  Actual count may be lower
            if Wiktionary returns fewer pages.

        Returns
        -------
        list[str]
            Bangla word strings, in Wiktionary page order.
        """
        print(f"[bangla-synonyms] fetching up to {limit} words from Wiktionary...")
        words = fetch_word_list(limit, self._session, self.timeout)
        print(f"[bangla-synonyms] fetched {len(words)} Bangla words")
        return words

    def filter_new(self, words: list, dm: DatasetManager) -> list:
        """
        Return only the words that are not yet in the local dataset.

        Pass the result directly to ``BatchScraper.run()`` to safely resume
        an interrupted scraping session without re-scraping words that are
        already cached.

        Parameters
        ----------
        words : list[str]
            Word list to filter, typically from ``fetch()``.
        dm : DatasetManager
            The dataset to check against.

        Returns
        -------
        list[str]
            Subset of ``words`` not present in ``dm``.
        """
        return [w for w in words if w not in dm]

    def save(self, words: list, path: str) -> None:
        """
        Write a word list to a plain-text file (one word per line).

        Parameters
        ----------
        words : list[str]
            Words to write.
        path : str
            Output file path.

        Raises
        ------
        OSError
            If the file cannot be written.
        """
        try:
            Path(path).write_text("\n".join(words), encoding="utf-8")
            print(f"[bangla-synonyms] saved {len(words)} words → {path}")
        except OSError as exc:
            raise OSError(f"Failed to save word list to '{path}': {exc}") from exc

    def load(self, path: str) -> list:
        """
        Load a word list from a plain-text file (one word per line).

        Parameters
        ----------
        path : str
            Path to the word-list file previously saved by ``save()``.

        Returns
        -------
        list[str]
            One word per line, blank lines removed.

        Raises
        ------
        OSError
            If the file cannot be read.
        """
        try:
            return Path(path).read_text(encoding="utf-8").strip().splitlines()
        except OSError as exc:
            raise OSError(f"Failed to load word list from '{path}': {exc}") from exc


# ===========================================================================
# BatchScraper
# ===========================================================================


class BatchScraper:
    """
    Scrape synonyms for large word lists with progress tracking and resume.

    Writes results to a ``DatasetManager`` instance as it goes, flushing
    to disk every ``save_every`` words so a crash never loses more than
    that many results.

    Parameters
    ----------
    dataset : DatasetManager | None, default None
        The dataset to write into.  Uses the shared singleton when ``None``.
    delay : float, default 1.0
        Seconds to wait between HTTP requests.  Applies only to live
        network calls — words already in the dataset incur no delay.
    timeout : int, default 10
        HTTP request timeout in seconds per source.
    save_every : int, default 50
        Flush results to disk every N words (checkpoint interval).
        Lower values reduce data loss on crash at the cost of more I/O.
    sources : list[str] | None, default None
        Which sources to query.  ``None`` uses all three in default order.
    merge : bool, default True
        ``True``  — merge results from all sources.
        ``False`` — stop at the first source that returns any results.

    Examples
    --------
        from bangla_synonyms.core import BatchScraper

        scraper = BatchScraper(delay=1.0)
        scraper.run(["চোখ", "মা", "নদী"])
        scraper.run(words, sources=["wiktionary"])
        scraper.run_from_wiktionary(limit=1000)
    """

    def __init__(
        self,
        dataset: DatasetManager | None = None,
        delay: float = 1.0,
        timeout: int = 10,
        save_every: int = 50,
        sources: list | None = None,
        merge: bool = True,
    ) -> None:
        self.dataset = dataset or DatasetManager()
        self.delay = delay
        self.timeout = timeout
        self.save_every = save_every
        self.sources = sources
        self.merge = merge
        self._session = make_session()

    def run(
        self,
        words: list,
        skip_existing: bool = True,
        show_progress: bool = True,
        sources: list | None = None,
    ) -> dict:
        """
        Scrape synonyms for every word in ``words``.

        Parameters
        ----------
        words : list[str]
            Bangla words to scrape.
        skip_existing : bool, default True
            Skip words already in the local dataset.  Set ``True`` to
            safely re-run after an interruption without duplicate work.
        show_progress : bool, default True
            Print one progress line per word to stdout.
        sources : list[str] | None, default None
            Override the instance-level source list for this run only.
            ``None`` falls back to the instance default.

        Returns
        -------
        dict
            ``{word: [synonyms]}`` for *newly scraped* words only.
            Words already in the dataset or with no results are excluded.

        Progress output::

            [  1/200] চোখ:  ✓ চক্ষু, নেত্র, লোচন ...
            [  2/200] xyz:  — not found
            [  3/200] মা:   ❌ network error
            …
            [bangla-synonyms] done: 180 found, 15 not found, 5 errors
        """
        active_sources = sources if sources is not None else self.sources

        if skip_existing:
            words = [w for w in words if w not in self.dataset]

        total = len(words)
        scraped: dict = {}
        found = skipped = errors = 0
        width = len(str(total))

        for i, word in enumerate(words):
            try:
                syns = fetch_with_sources(
                    word,
                    self._session,
                    self.timeout,
                    active_sources,
                    self.merge,
                )
            except Exception as exc:
                log.error("[batch] unexpected error for '%s': %s", word, exc)
                syns = None

            if syns is None:
                errors += 1
                status = "❌ network error"
            elif syns:
                scraped[word] = syns
                self.dataset.add(word, syns, save=False)
                found += 1
                preview = ", ".join(syns[:3])
                suffix = " ..." if len(syns) > 3 else ""
                status = f"✓ {preview}{suffix}"
            else:
                skipped += 1
                status = "— not found"

            if show_progress:
                print(f"  [{i + 1:>{width}}/{total}] {word}: {status}")

            if (i + 1) % self.save_every == 0:
                try:
                    _save(self.dataset._data)
                    log.debug("[batch] checkpoint at word %d", i + 1)
                except OSError as exc:
                    log.error("[batch] checkpoint save failed: %s", exc)

            if i < total - 1:
                time.sleep(self.delay)

        try:
            _save(self.dataset._data)
        except OSError as exc:
            log.error("[batch] final save failed: %s", exc)

        if show_progress:
            print(
                f"\n[bangla-synonyms] done: "
                f"{found} found, {skipped} not found, {errors} errors"
            )

        return scraped

    def run_from_wiktionary(self, limit: int = 200) -> dict:
        """
        Fetch a word list from Wiktionary and scrape all of them in one step.

        Equivalent to calling ``WordlistFetcher.fetch()`` followed by
        ``run()`` with ``skip_existing=True``.  Words already in the
        local dataset are automatically skipped.

        Parameters
        ----------
        limit : int, default 200
            Maximum number of words to fetch from Wiktionary.

        Returns
        -------
        dict
            ``{word: [synonyms]}`` for newly scraped words, same as ``run()``.
        """
        print(
            f"[bangla-synonyms] fetching word list from Wiktionary (limit={limit})..."
        )
        words = fetch_word_list(limit, self._session, self.timeout)
        print(f"[bangla-synonyms] {len(words)} words fetched — starting scrape...")
        return self.run(words, skip_existing=True)
