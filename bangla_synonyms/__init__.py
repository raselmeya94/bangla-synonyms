"""
bangla_synonyms
================
Bangla synonym lookup — offline dataset + live web scraping.

Simplest usage
--------------
    import bangla_synonyms as bs

    bs.download()                           # download dataset once
    bs.get("চোখ")                           # → ['চক্ষু', 'নেত্র', 'লোচন', ...]
    bs.get_many(["চোখ", "মা"])              # → {'চোখ': [...], 'মা': [...]}
    bs.stats()                              # dataset statistics

Full control (lookup)
---------------------
    from bangla_synonyms import Scrapper

    sc = Scrapper()                         # online, all sources
    sc = Scrapper(offline=True)             # local dataset only
    sc = Scrapper(sources=["wiktionary"])   # Wiktionary only
    sc = Scrapper(merge=False)              # stop at first source with results
    sc = Scrapper(auto_save=True)           # persist scraped results to disk
    sc = Scrapper(delay=2.0, timeout=15)    # slow connection / polite scraping

    sc.get("চোখ")
    sc.get_many(["চোখ", "মা", "নদী"])

Dataset management
------------------
    from bangla_synonyms.core import DatasetManager

    dm = DatasetManager()
    dm.add("নদী", ["তটিনী", "প্রবাহিনী"])
    dm.remove("শব্দ")
    dm.stats()
    dm.export("output.csv", fmt="csv")

Bulk scraping
-------------
    from bangla_synonyms.core import BatchScraper

    scraper = BatchScraper(delay=1.0)
    scraper.run_from_wiktionary(limit=500)

CLI
---
    bangla-synonyms download
    bangla-synonyms get চোখ
    bangla-synonyms get চোখ মা সুন্দর --sources wiktionary
    bangla-synonyms build --limit 500
    bangla-synonyms stats
    bangla-synonyms export synonyms.json
"""
from __future__ import annotations

from ._scrapper import Scrapper
from .core import DatasetManager

__version__ = "1.0.0"
__all__ = ["Scrapper", "download", "get", "get_many", "stats"]

# Shared instance — avoids creating a new HTTP session on every bs.get() call.
# When ``sources`` is None the default, this singleton handles all requests.
_default = Scrapper()


def download(version: str = "latest", force: bool = False) -> None:
    """
    Download the pre-built Bangla synonym dataset from GitHub Releases.

    Saves to ``./bangla_synonyms_data/dataset.json``.  All running
    instances pick up the new data immediately — no restart needed.

    Parameters
    ----------
    version : str, default "latest"
        ``"latest"`` — full dataset (~10 000 words).
        ``"mini"``   — small starter set (~500 words).
    force : bool, default False
        Re-download even if the dataset file already exists.

    Examples
    --------
        import bangla_synonyms as bs

        bs.download()
        bs.download("mini")
        bs.download(force=True)
    """
    Scrapper.download(version=version, force=force)


def get(word: str, sources: list | None = None, raw: bool = False) -> list | dict:
    """
    Return synonyms for a single Bangla word.

    Checks the local dataset first; falls back to live scraping when the
    word is not cached.  Returns ``[]`` when nothing is found.

    Parameters
    ----------
    word : str
        The Bangla word to look up.
    sources : list[str] | None, default None
        Which sources to query.  ``None`` uses all three in default order:
        Wiktionary → Shabdkosh → English-Bangla.
    raw : bool, default False
        ``False`` — plain ``list[str]``.
        ``True``  — metadata dict with per-source breakdown and quality field.

    Examples
    --------
        import bangla_synonyms as bs

        bs.get("চোখ")
        bs.get("চোখ", sources=["wiktionary"])
        bs.get("চোখ", raw=True)
        bs.get("xyz")   # → []
    """
    if sources:
        return Scrapper(sources=sources).get(word, raw=raw)
    return _default.get(word, raw=raw)


def get_many(words: list, sources: list | None = None, raw: bool = False) -> dict:
    """
    Return synonyms for multiple Bangla words.

    Parameters
    ----------
    words : list[str]
        Bangla words to look up.
    sources : list[str] | None, default None
        Which sources to query (default: all three).
    raw : bool, default False
        ``False`` — ``{word: list[str]}``.
        ``True``  — ``{word: dict}`` with source metadata per word.

    Examples
    --------
        import bangla_synonyms as bs

        bs.get_many(["চোখ", "মা", "দুঃখ"])
        bs.get_many(["চোখ", "মা"], raw=True)
    """
    if sources:
        return Scrapper(sources=sources).get_many(words, raw=raw)
    return _default.get_many(words, raw=raw)


def stats() -> dict:
    """
    Print local dataset statistics and return them as a dict.

    Delegates to ``DatasetManager.stats()``.

    Returns
    -------
    dict
        Keys: ``total_words``, ``total_synonyms``, ``avg_per_word``, ``source``.

    Examples
    --------
        import bangla_synonyms as bs

        info = bs.stats()
        # Words         : 9842
        # Total synonyms: 47391
        # Avg / word    : 4.82
    """
    return DatasetManager().stats()
