"""
bangla-synonyms
================
Bangla synonym lookup — offline dataset + live web scraping.

Three sources, smart fallback, offline mode, batch scraping.

─────────────────────────────────────────────────────────
THE SIMPLEST WAY:
─────────────────────────────────────────────────────────
    import bangla_synonyms as bs

    bs.download()                          # dataset একবার download করো
    bs.get("চোখ")                          # → ['চক্ষু', 'নেত্র', 'লোচন', ...]
    bs.get_many(["চোখ", "মা"])             # → {'চোখ': [...], 'মা': [...]}
    bs.stats()                             # dataset info

─────────────────────────────────────────────────────────
SCRAPER WITH FULL CONTROL  (Scrapper):
─────────────────────────────────────────────────────────
    from bangla_synonyms import Scrapper

    sc = Scrapper()                        # online, all sources, delay=1s
    sc = Scrapper(offline=True)            # local dataset only
    sc = Scrapper(sources=["wiktionary"])  # Wiktionary only
    sc = Scrapper(merge=False)             # stop at first source with results
    sc = Scrapper(auto_save=False)         # scrape but don't write to disk
    sc = Scrapper(delay=2.0, timeout=15)   # slow connection / polite scraping

    sc.get("চোখ")
    sc.get_many(["চোখ", "মা", "নদী"])

    # Sources available:
    # "wiktionary"     — bn.wiktionary.org (most reliable)
    # "shabdkosh"      — shabdkosh.com (good coverage)
    # "english_bangla" — english-bangla.com (last resort)

─────────────────────────────────────────────────────────
ADVANCED  (bangla_synonyms.core):
─────────────────────────────────────────────────────────
    from bangla_synonyms.core import DatasetManager, WordlistFetcher, BatchScraper

    dm = DatasetManager()
    dm.stats()
    dm.add("নদী", ["তটিনী", "প্রবাহিনী"])
    dm.remove("শব্দ")
    dm.merge("extra.json")
    dm.export("output.csv", fmt="csv")

    wf    = WordlistFetcher()
    words = wf.fetch(limit=500)
    new   = wf.filter_new(words, dm)      # skip already known words

    bs = BatchScraper(delay=1.0)
    bs.run(words)
    bs.run(words, sources=["wiktionary"])
    bs.run_from_wiktionary(limit=500)

─────────────────────────────────────────────────────────
CLI:
─────────────────────────────────────────────────────────
    bangla-synonyms download
    bangla-synonyms download --version mini
    bangla-synonyms get চোখ
    bangla-synonyms get চোখ মা সুন্দর --sources wiktionary
    bangla-synonyms get চোখ --offline
    bangla-synonyms build --limit 500 --delay 1.5
    bangla-synonyms build --sources wiktionary --sources shabdkosh
    bangla-synonyms stats
    bangla-synonyms export synonyms.json
    bangla-synonyms export synonyms.csv --format csv
"""
from __future__ import annotations

from .synonyms  import BanglaSynonyms
from ._scrapper import Scrapper

__version__ = "1.0.0"
__all__ = [
    "BanglaSynonyms", "Scrapper",
    "download", "get", "get_many", "stats",
]


# ── Module-level convenience API ──────────────────────────────
# nltk.download() এর মতো — class বা instance লাগবে না।
#
#   import bangla_synonyms as bs
#   bs.download()
#   bs.get("চোখ")

def download(version: str = "latest", force: bool = False) -> None:
    """
    Bangla synonym dataset download করে।

    Saves to: ``./bangla_synonyms_data/dataset.json``

    Parameters
    ----------
    version : ``"latest"`` (default, ~10 000 words) or ``"mini"`` (small starter set)
    force   : re-download even if dataset already exists

    Examples
    --------
        import bangla_synonyms as bs

        bs.download()                  # full dataset
        bs.download("mini")            # small version
        bs.download(force=True)        # force re-download
    """
    BanglaSynonyms.download(version=version, force=force)


def get(word: str, sources: list | None = None, raw: bool = False) -> list[str] | dict:
    """
    একটা শব্দের synonym list return করে।

    Local dataset এ না পেলে automatically online fallback করে।
    কিছু না পেলে empty list ``[]`` return করে।

    Parameters
    ----------
    word    : Bangla শব্দ
    sources : কোন sources ব্যবহার করবে (default: সব তিনটা)
    raw     : False (default) → flat list
              True            → source metadata সহ dict

    Examples
    --------
        import bangla_synonyms as bs

        bs.get("চোখ")                          # → ['চক্ষু', 'নেত্র', ...]
        bs.get("চোখ", sources=["wiktionary"])  # Wiktionary only
        bs.get("চোখ", raw=True)
        # → {
        #     "word":          "চোখ",
        #     "source":        "wiktionary",
        #     "results":       [{"synonym": "চক্ষু", "source": "wiktionary"}, ...],
        #     "words":         ["চক্ষু", "নেত্র", ...],
        #     "sources_hit":   ["wiktionary"],
        #     "sources_tried": ["wiktionary", "shabdkosh", "english_bangla"],
        # }
    """
    return Scrapper(sources=sources).get(word, raw=raw)


def get_many(words: list[str], sources: list | None = None, raw: bool = False) -> dict:
    """
    একাধিক শব্দের synonym lookup করে।

    Parameters
    ----------
    words   : Bangla শব্দের list
    sources : কোন sources ব্যবহার করবে (default: সব তিনটা)
    raw     : False (default) → ``{word: [synonyms]}``
              True            → ``{word: raw_dict}`` (source metadata সহ)

    Examples
    --------
        import bangla_synonyms as bs

        bs.get_many(["চোখ", "মা", "দুঃখ"])
        # → {'চোখ': [...], 'মা': [...], 'দুঃখ': [...]}

        bs.get_many(["চোখ", "মা"], raw=True)
        # → {
        #     'চোখ': {"word": "চোখ", "results": [...], "words": [...], ...},
        #     'মা':  {"word": "মা",  "results": [...], "words": [...], ...},
        #   }
    """
    return Scrapper(sources=sources).get_many(words, raw=raw)


def stats() -> dict:
    """
    Local dataset statistics print করে এবং dict হিসেবে return করে।

    Examples
    --------
        import bangla_synonyms as bs

        bs.stats()
        # Words         : 9842
        # Total synonyms: 47391
        # Avg / word    : 4.82
    """
    from .core import DatasetManager
    return DatasetManager().stats()
