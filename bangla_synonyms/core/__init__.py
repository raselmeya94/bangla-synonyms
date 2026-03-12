# """
# bangla_synonyms.core
# ---------------------
# Advanced features for power users and researchers.

# Classes
# -------
# DatasetManager   -- load, save, merge, export the synonym dataset
# WordlistFetcher  -- pull Bangla word lists from Wiktionary
# BatchScraper     -- scrape many words with progress tracking + resume

# Source control
# --------------
# Three scrapers are available. Use ``sources=`` to choose:

#     SOURCES = {
#         "wiktionary":     bn.wiktionary.org  (most reliable, structured data)
#         "shabdkosh":      shabdkosh.com       (good coverage, clean output)
#         "english_bangla": english-bangla.com  (last resort, near-synonyms)
#     }

#     DEFAULT_SOURCES = ["wiktionary", "shabdkosh", "english_bangla"]

# By default all three sources are tried and results are merged.
# Use ``merge=False`` to stop at the first source that returns results.

# Quick start
# -----------
#     from bangla_synonyms.core import DatasetManager, WordlistFetcher, BatchScraper

#     dm = DatasetManager()
#     dm.stats()
#     dm.merge("extra.json")
#     dm.export("output.csv", fmt="csv")

#     wf    = WordlistFetcher()
#     words = wf.fetch(limit=500)

#     bs = BatchScraper(delay=1.0)
#     bs.run(words)
#     bs.run(words, sources=["wiktionary"])
#     bs.run(words, sources=["wiktionary", "shabdkosh"])
# """
# from __future__ import annotations

# import csv
# import json
# import logging
# import time
# from pathlib import Path

# from ._wikitext       import fetch_synonyms       as _fetch_wiktionary
# from ._wikitext       import fetch_word_list, make_session
# from ._shabdkosh      import fetch_shabdkosh      as _fetch_shabdkosh
# from ._english_bangla import fetch_english_bangla as _fetch_english_bangla

# log = logging.getLogger(__name__)

# __all__ = [
#     "SOURCES", "DEFAULT_SOURCES",
#     "fetch_with_sources", "fetch_with_sources_raw",
#     "DatasetManager", "WordlistFetcher", "BatchScraper",
#     "reload_dataset", "make_session",
# ]


# # ═══════════════════════════════════════════════════════════════
# # SOURCE REGISTRY
# # ═══════════════════════════════════════════════════════════════

# #: All available scraping sources.
# #: প্রতিটা function: ``(word, session, timeout) -> list[str] | None``
# SOURCES: dict[str, object] = {
#     "wiktionary":     _fetch_wiktionary,
#     "shabdkosh":      _fetch_shabdkosh,
#     "english_bangla": _fetch_english_bangla,
# }

# #: Default cascade order — most reliable first.
# DEFAULT_SOURCES: list[str] = ["wiktionary", "shabdkosh", "english_bangla"]


# def fetch_with_sources(
#     word:    str,
#     session,
#     timeout: int        = 10,
#     sources: list | None = None,
#     merge:   bool       = True,
# ) -> list | None:
#     """
#     নির্দিষ্ট sources থেকে cascade করে synonym fetch করে।

#     Parameters
#     ----------
#     word    : Bangla শব্দ
#     session : requests.Session (make_session() দিয়ে তৈরি)
#     timeout : HTTP timeout (seconds, default: 10)
#     sources : কোন sources ব্যবহার করবে।
#               ``None``                        → DEFAULT_SOURCES (সব তিনটা)
#               ``["wiktionary"]``              → শুধু Wiktionary
#               ``["wiktionary","shabdkosh"]``  → দুটো
#     merge   : ``True``  → সব source এর result একসাথে দেয় (default)
#               ``False`` → প্রথম যে source এ পাওয়া গেল সেটাই দেয়

#     Returns
#     -------
#     list[str]
#         পাওয়া synonyms (খালি হতে পারে)
#     None
#         সব active source এ network error হয়েছে

#     Examples
#     --------
#         fetch_with_sources("চোখ", session)
#         fetch_with_sources("চোখ", session, sources=["wiktionary"])
#         fetch_with_sources("চোখ", session, merge=False)
#     """
#     raw = fetch_with_sources_raw(word, session, timeout, sources, merge)
#     if raw is None:
#         return None
#     return raw["words"]


# def fetch_with_sources_raw(
#     word:    str,
#     session,
#     timeout: int        = 10,
#     sources: list | None = None,
#     merge:   bool       = True,
# ) -> dict | None:
#     """
#     Source metadata সহ synonym fetch করে।

#     Parameters
#     ----------
#     word, session, timeout, sources, merge : ``fetch_with_sources`` এর মতোই

#     Returns
#     -------
#     dict  যদি কিছু পাওয়া যায় বা সব source empty দেয়::

#         {
#             "word": "চোখ",
#             "results": [
#                 {"synonym": "চক্ষু", "source": "wiktionary"},
#                 {"synonym": "নেত্র", "source": "wiktionary"},
#                 {"synonym": "আঁখি", "source": "shabdkosh"},
#             ],
#             "words": ["চক্ষু", "নেত্র", "আঁখি"],   # flat list, backward-compatible
#             "sources_hit": ["wiktionary", "shabdkosh"],
#             "sources_tried": ["wiktionary", "shabdkosh", "english_bangla"],
#         }

#     None
#         সব active source এ network error হয়েছে

#     Examples
#     --------
#         raw = fetch_with_sources_raw("চোখ", session)
#         raw["words"]        # → ['চক্ষু', 'নেত্র', ...]
#         raw["results"]      # → [{'synonym': 'চক্ষু', 'source': 'wiktionary'}, ...]
#         raw["sources_hit"]  # → ['wiktionary']
#     """
#     active    = sources if sources is not None else DEFAULT_SOURCES
#     results:  list[dict] = []   # {"synonym": str, "source": str}
#     seen:     set[str]   = set()
#     any_error    = False
#     sources_hit: list[str] = []

#     for name in active:
#         fn = SOURCES.get(name)
#         if fn is None:
#             log.warning("[sources] unknown source '%s' — skipping", name)
#             continue

#         log.debug("[sources] trying '%s' for '%s'", name, word)
#         result = fn(word, session, timeout)  # type: ignore[call-arg]

#         if result is None:
#             log.warning("[sources] '%s' network error for '%s'", name, word)
#             any_error = True
#             continue

#         if result:
#             new_count = 0
#             for w in result:
#                 if w not in seen:
#                     seen.add(w)
#                     results.append({"synonym": w, "source": name})
#                     new_count += 1
#             if new_count:
#                 sources_hit.append(name)
#                 log.debug("[sources] '%s' added %d word(s) for '%s'", name, new_count, word)

#             if not merge:
#                 break

#     if results:
#         return {
#             "word":          word,
#             "results":       results,
#             "words":         [r["synonym"] for r in results],
#             "sources_hit":   sources_hit,
#             "sources_tried": list(active),
#         }

#     if any_error and not results:
#         return None

#     # found nothing, no error
#     return {
#         "word":          word,
#         "results":       [],
#         "words":         [],
#         "sources_hit":   [],
#         "sources_tried": list(active),
#     }


# # ═══════════════════════════════════════════════════════════════
# # DATASET PATH
# # ═══════════════════════════════════════════════════════════════

# def _dataset_path() -> Path:
#     """Current working directory তে dataset এর standard path।"""
#     return Path.cwd() / "bangla_synonyms_data" / "dataset.json"


# # ═══════════════════════════════════════════════════════════════
# # Shared in-memory store (module-level singleton)
# # ═══════════════════════════════════════════════════════════════

# _SHARED: dict | None = None


# def _ensure_shared() -> dict:
#     global _SHARED
#     if _SHARED is None:
#         _SHARED = _load()
#     return _SHARED


# def reload_dataset() -> None:
#     """
#     Disk থেকে dataset পুনরায় পড়ে in-memory cache replace করে।

#     ``BanglaSynonyms.download()`` এর পরে automatically call হয়।
#     নতুন data তাৎক্ষণিকভাবে সব instances এ দেখা যাবে।
#     """
#     global _SHARED
#     _SHARED = _load()


# # ═══════════════════════════════════════════════════════════════
# # Disk I/O helpers
# # ═══════════════════════════════════════════════════════════════

# def _load() -> dict:
#     path = _dataset_path()
#     if path.exists():
#         try:
#             data = json.loads(path.read_text(encoding="utf-8"))
#             log.debug("[dataset] loaded %d words from %s", len(data), path)
#             return data
#         except (json.JSONDecodeError, OSError) as e:
#             log.error("[dataset] failed to read %s: %s", path, e)
#     log.info("[dataset] no dataset found at %s", path)
#     return {}


# def _save(data: dict) -> None:
#     path = _dataset_path()
#     try:
#         path.parent.mkdir(parents=True, exist_ok=True)
#         path.write_text(
#             json.dumps(data, ensure_ascii=False, indent=2),
#             encoding="utf-8",
#         )
#         log.debug("[dataset] saved %d words to %s", len(data), path)
#     except OSError as e:
#         log.error("[dataset] failed to save dataset: %s", e)
#         raise


# # ═══════════════════════════════════════════════════════════════
# # DatasetManager
# # ═══════════════════════════════════════════════════════════════

# class DatasetManager:
#     """
#     Local synonym dataset পড়া, লেখা, merge, export করার class।

#     Dataset location:
#         ``./bangla_synonyms_data/dataset.json``

#     সব instance একই shared in-memory data দেখে — একটায় পরিবর্তন
#     সবখানে reflect হয়।

#     Usage
#     -----
#         from bangla_synonyms.core import DatasetManager

#         dm = DatasetManager()
#         dm.stats()
#         dm.add("শব্দ", ["প্রতিশব্দ১", "প্রতিশব্দ২"])
#         dm.remove("শব্দ")
#         dm.merge("extra.json")
#         dm.export("output.json")
#         dm.export("output.csv", fmt="csv")
#     """

#     def __init__(self) -> None:
#         pass  # data _SHARED এ থাকে, instance এ না

#     @property
#     def _data(self) -> dict:
#         return _ensure_shared()

#     @_data.setter
#     def _data(self, value: dict) -> None:
#         global _SHARED
#         _SHARED = value

#     def reload(self) -> None:
#         """Disk থেকে dataset পুনরায় load করে।"""
#         reload_dataset()

#     # ── Read ──────────────────────────────────────────────────

#     def get(self, word: str) -> list:
#         """Dataset থেকে একটা শব্দের synonym list return করে।"""
#         return list(self._data.get(word, []))

#     def has(self, word: str) -> bool:
#         """শব্দটা dataset এ আছে কিনা check করে।"""
#         return word in self._data

#     def all_words(self) -> list:
#         """Sorted alphabetical word list return করে।"""
#         return sorted(self._data.keys())

#     def __contains__(self, word: str) -> bool:
#         return self.has(word)

#     def __len__(self) -> int:
#         return len(self._data)

#     # ── Write ─────────────────────────────────────────────────

#     def add(self, word: str, synonyms: list, save: bool = True) -> None:
#         """
#         Dataset এ শব্দ ও তার synonym যোগ করে।

#         শব্দ আগে থেকে থাকলে নতুন synonym merge হয়।
#         ``save=True`` হলে disk এ persist হয়।
#         """
#         word = word.strip()
#         if not word:
#             return

#         existing = set(self._data.get(word, []))
#         merged   = list(self._data.get(word, []))
#         for s in synonyms:
#             s = s.strip()
#             if s and s not in existing and s != word:
#                 merged.append(s)
#                 existing.add(s)

#         self._data[word] = merged
#         if save:
#             _save(self._data)

#     def remove(self, word: str, save: bool = True) -> bool:
#         """
#         Dataset থেকে শব্দ মুছে দেয়।

#         Return করে True যদি শব্দটা ছিল, False যদি না থাকে।
#         """
#         if word in self._data:
#             del self._data[word]
#             if save:
#                 _save(self._data)
#             return True
#         return False

#     def update(self, word: str, synonyms: list, save: bool = True) -> None:
#         """
#         শব্দের synonym list replace করে (merge নয়)।
#         """
#         word = word.strip()
#         if not word:
#             return
#         self._data[word] = [s.strip() for s in synonyms if s.strip() and s.strip() != word]
#         if save:
#             _save(self._data)

#     # ── Merge ─────────────────────────────────────────────────

#     def merge(self, path: str) -> int:
#         """
#         JSON file থেকে dataset merge করে।

#         নতুন শব্দ add হয়, পুরনো শব্দে নতুন synonym append হয়।
#         নতুন যোগ হওয়া শব্দের সংখ্যা return করে।
#         """
#         try:
#             with open(path, encoding="utf-8") as f:
#                 incoming: dict = json.load(f)
#         except (json.JSONDecodeError, OSError) as e:
#             raise ValueError(f"Failed to merge dataset from '{path}': {e}") from e

#         added = 0
#         for word, syns in incoming.items():
#             if word not in self._data:
#                 self._data[word] = syns
#                 added += 1
#             else:
#                 existing = set(self._data[word])
#                 self._data[word] += [s for s in syns if s not in existing]

#         _save(self._data)
#         return added

#     # ── Export ────────────────────────────────────────────────

#     def export(self, path: str, fmt: str = "json") -> None:
#         """
#         Dataset file এ export করে।

#         Parameters
#         ----------
#         path : output file path
#         fmt  : ``"json"`` (default) or ``"csv"``
#         """
#         if fmt not in ("json", "csv"):
#             raise ValueError(f"Unknown format '{fmt}'. Use 'json' or 'csv'.")

#         p = Path(path)
#         try:
#             if fmt == "json":
#                 p.write_text(
#                     json.dumps(dict(sorted(self._data.items())),
#                                ensure_ascii=False, indent=2),
#                     encoding="utf-8",
#                 )
#             else:
#                 with open(p, "w", encoding="utf-8", newline="") as f:
#                     writer = csv.writer(f)
#                     writer.writerow(["word", "synonyms", "count"])
#                     for word, syns in sorted(self._data.items()):
#                         writer.writerow([word, " | ".join(syns), len(syns)])
#         except OSError as e:
#             raise OSError(f"Failed to export to '{path}': {e}") from e

#         print(f"[bangla-synonyms] exported {len(self._data)} words → {path}")

#     # ── Stats ─────────────────────────────────────────────────

#     def stats(self) -> dict:
#         """Dataset statistics print করে এবং dict হিসেবে return করে।"""
#         total_syns = sum(len(v) for v in self._data.values())
#         avg        = round(total_syns / len(self._data), 2) if self._data else 0
#         top5       = sorted(
#             self._data.items(), key=lambda x: len(x[1]), reverse=True
#         )[:5]
#         path   = _dataset_path()
#         source = str(path) if path.exists() else "no dataset — run BanglaSynonyms.download()"

#         result = {
#             "total_words":    len(self._data),
#             "total_synonyms": total_syns,
#             "avg_per_word":   avg,
#             "source":         source,
#         }

#         print(f"Words         : {result['total_words']}")
#         print(f"Total synonyms: {result['total_synonyms']}")
#         print(f"Avg / word    : {result['avg_per_word']}")
#         print(f"Source        : {result['source']}")
#         if top5:
#             print("Top 5 words   :")
#             for word, syns in top5:
#                 preview = ", ".join(syns[:4])
#                 suffix  = " ..." if len(syns) > 4 else ""
#                 print(f"  {word}: {preview}{suffix}")

#         return result


# # ═══════════════════════════════════════════════════════════════
# # WordlistFetcher
# # ═══════════════════════════════════════════════════════════════

# class WordlistFetcher:
#     """
#     Wiktionary থেকে বাংলা শব্দের list fetch করার class।

#     Usage
#     -----
#         from bangla_synonyms.core import WordlistFetcher

#         wf    = WordlistFetcher()
#         words = wf.fetch(limit=500)
#         new   = wf.filter_new(words, dm)
#         wf.save(words, "word_list.txt")
#     """

#     def __init__(self, timeout: int = 10) -> None:
#         self.timeout  = timeout
#         self._session = make_session()

#     def fetch(self, limit: int = 500) -> list:
#         """Wiktionary থেকে সর্বোচ্চ ``limit`` টা বাংলা শব্দ fetch করে।"""
#         print(f"[bangla-synonyms] fetching up to {limit} words from Wiktionary...")
#         words = fetch_word_list(limit, self._session, self.timeout)
#         print(f"[bangla-synonyms] fetched {len(words)} Bangla words")
#         return words

#     def filter_new(self, words: list, dm: DatasetManager) -> list:
#         """Dataset এ নেই এমন শব্দগুলো return করে (resume সুবিধার জন্য)।"""
#         return [w for w in words if w not in dm]

#     def save(self, words: list, path: str) -> None:
#         """Word list text file এ save করে।"""
#         try:
#             Path(path).write_text("\n".join(words), encoding="utf-8")
#             print(f"[bangla-synonyms] saved {len(words)} words → {path}")
#         except OSError as e:
#             raise OSError(f"Failed to save word list to '{path}': {e}") from e

#     def load(self, path: str) -> list:
#         """Text file থেকে word list load করে।"""
#         try:
#             return Path(path).read_text(encoding="utf-8").strip().splitlines()
#         except OSError as e:
#             raise OSError(f"Failed to load word list from '{path}': {e}") from e


# # ═══════════════════════════════════════════════════════════════
# # BatchScraper
# # ═══════════════════════════════════════════════════════════════

# class BatchScraper:
#     """
#     অনেকগুলো শব্দের synonym একসাথে scrape করার class।

#     Parameters
#     ----------
#     dataset    : DatasetManager — না দিলে shared instance ব্যবহার করে
#     delay      : প্রতিটা HTTP request এর মাঝে অপেক্ষা (seconds, default: 1.0)
#     timeout    : HTTP request timeout (seconds, default: 10)
#     save_every : প্রতি N শব্দ পরে disk এ flush করে (default: 50)
#     sources    : কোন sources ব্যবহার করবে (default: সব তিনটা)
#     merge      : True → সব source merge করে, False → প্রথম hit এ থামে

#     Usage
#     -----
#         bs = BatchScraper(delay=1.0)
#         bs.run(["চোখ", "মা", "আকাশ"])
#         bs.run(words, sources=["wiktionary"])
#         bs.run_from_wiktionary(limit=500)
#     """

#     def __init__(
#         self,
#         dataset:    DatasetManager | None = None,
#         delay:      float = 1.0,
#         timeout:    int   = 10,
#         save_every: int   = 50,
#         sources:    list | None = None,
#         merge:      bool  = True,
#     ) -> None:
#         self.dataset    = dataset or DatasetManager()
#         self.delay      = delay
#         self.timeout    = timeout
#         self.save_every = save_every
#         self.sources    = sources
#         self.merge      = merge
#         self._session   = make_session()

#     def run(
#         self,
#         words:         list,
#         skip_existing: bool       = True,
#         show_progress: bool       = True,
#         sources:       list | None = None,
#     ) -> dict:
#         """
#         শব্দের list এর synonym scrape করে।

#         Parameters
#         ----------
#         words          : scrape করার বাংলা শব্দের list
#         skip_existing  : dataset এ আছে এমন শব্দ skip করে (resume সুবিধা)
#         show_progress  : [i/total] progress দেখায়
#         sources        : এই run এর জন্য sources override (None = instance default)

#         Returns
#         -------
#         dict
#             নতুন scrape হওয়া ``{word: [synonyms]}``
#         """
#         active_sources = sources if sources is not None else self.sources

#         if skip_existing:
#             words = [w for w in words if w not in self.dataset]

#         total   = len(words)
#         scraped: dict = {}
#         found = skipped = errors = 0

#         for i, word in enumerate(words):
#             try:
#                 syns = fetch_with_sources(
#                     word, self._session, self.timeout,
#                     active_sources, self.merge,
#                 )
#             except Exception as e:
#                 log.error("[batch] unexpected error for '%s': %s", word, e)
#                 syns = None

#             if syns is None:
#                 errors += 1
#                 status  = "❌ network error"
#             elif syns:
#                 scraped[word] = syns
#                 self.dataset.add(word, syns, save=False)
#                 found  += 1
#                 preview = ", ".join(syns[:3])
#                 suffix  = " ..." if len(syns) > 3 else ""
#                 status  = f"✓ {preview}{suffix}"
#             else:
#                 skipped += 1
#                 status   = "— not found"

#             if show_progress:
#                 print(f"  [{i + 1:>{len(str(total))}}/{total}] {word}: {status}")

#             if (i + 1) % self.save_every == 0:
#                 try:
#                     _save(self.dataset._data)
#                     log.debug("[batch] checkpoint saved at %d words", i + 1)
#                 except OSError as e:
#                     log.error("[batch] failed to save checkpoint: %s", e)

#             if i < total - 1:
#                 time.sleep(self.delay)

#         # final save
#         try:
#             _save(self.dataset._data)
#         except OSError as e:
#             log.error("[batch] failed to save final dataset: %s", e)

#         if show_progress:
#             print(f"\n[bangla-synonyms] done: {found} found, {skipped} not found, {errors} errors")

#         return scraped

#     def run_from_wiktionary(self, limit: int = 200) -> dict:
#         """
#         Wiktionary থেকে word list fetch করে সব scrape করে।

#         Parameters
#         ----------
#         limit : সর্বোচ্চ কত শব্দ scrape করবে (default: 200)
#         """
#         print(f"[bangla-synonyms] fetching word list from Wiktionary (limit={limit})...")
#         words = fetch_word_list(limit, self._session, self.timeout)
#         print(f"[bangla-synonyms] {len(words)} words fetched — starting scrape...")
#         return self.run(words, skip_existing=True)




"""
bangla_synonyms.core
---------------------
Advanced features for power users and researchers.

Classes
-------
DatasetManager   -- load, save, merge, export the synonym dataset
WordlistFetcher  -- pull Bangla word lists from Wiktionary
BatchScraper     -- scrape many words with progress tracking + resume

Source control
--------------
Three scrapers are available. Use ``sources=`` to choose:

    SOURCES = {
        "wiktionary":     bn.wiktionary.org  (most reliable, structured data)
        "shabdkosh":      shabdkosh.com       (good coverage, clean output)
        "english_bangla": english-bangla.com  (last resort, near-synonyms)
    }

    DEFAULT_SOURCES = ["wiktionary", "shabdkosh", "english_bangla"]

By default all three sources are tried and results are merged.
Use ``merge=False`` to stop at the first source that returns results.

Quick start
-----------
    from bangla_synonyms.core import DatasetManager, WordlistFetcher, BatchScraper

    dm = DatasetManager()
    dm.stats()
    dm.merge("extra.json")
    dm.export("output.csv", fmt="csv")

    wf    = WordlistFetcher()
    words = wf.fetch(limit=500)

    bs = BatchScraper(delay=1.0)
    bs.run(words)
    bs.run(words, sources=["wiktionary"])
    bs.run(words, sources=["wiktionary", "shabdkosh"])
"""
from __future__ import annotations

import csv
import json
import logging
import time
from pathlib import Path

from ._wikitext       import fetch_synonyms       as _fetch_wiktionary
from ._wikitext       import fetch_word_list, make_session
from ._shabdkosh      import fetch_shabdkosh      as _fetch_shabdkosh
from ._english_bangla import fetch_english_bangla as _fetch_english_bangla
from ._quality        import apply_quality

log = logging.getLogger(__name__)

__all__ = [
    "SOURCES", "DEFAULT_SOURCES",
    "fetch_with_sources", "fetch_with_sources_raw",
    "apply_quality",
    "DatasetManager", "WordlistFetcher", "BatchScraper",
    "reload_dataset", "make_session",
]


# ═══════════════════════════════════════════════════════════════
# SOURCE REGISTRY
# ═══════════════════════════════════════════════════════════════

#: All available scraping sources.
#: প্রতিটা function: ``(word, session, timeout) -> list[str] | None``
SOURCES: dict[str, object] = {
    "wiktionary":     _fetch_wiktionary,
    "shabdkosh":      _fetch_shabdkosh,
    "english_bangla": _fetch_english_bangla,
}

#: Default cascade order — most reliable first.
DEFAULT_SOURCES: list[str] = ["wiktionary", "shabdkosh", "english_bangla"]


def fetch_with_sources(
    word:    str,
    session,
    timeout: int        = 10,
    sources: list | None = None,
    merge:   bool       = True,
) -> list | None:
    """
    নির্দিষ্ট sources থেকে cascade করে synonym fetch করে।

    Parameters
    ----------
    word    : Bangla শব্দ
    session : requests.Session (make_session() দিয়ে তৈরি)
    timeout : HTTP timeout (seconds, default: 10)
    sources : কোন sources ব্যবহার করবে।
              ``None``                        → DEFAULT_SOURCES (সব তিনটা)
              ``["wiktionary"]``              → শুধু Wiktionary
              ``["wiktionary","shabdkosh"]``  → দুটো
    merge   : ``True``  → সব source এর result একসাথে দেয় (default)
              ``False`` → প্রথম যে source এ পাওয়া গেল সেটাই দেয়

    Returns
    -------
    list[str]
        পাওয়া synonyms (খালি হতে পারে)
    None
        সব active source এ network error হয়েছে

    Examples
    --------
        fetch_with_sources("চোখ", session)
        fetch_with_sources("চোখ", session, sources=["wiktionary"])
        fetch_with_sources("চোখ", session, merge=False)
    """
    raw = fetch_with_sources_raw(word, session, timeout, sources, merge)
    if raw is None:
        return None
    return raw["words"]


def fetch_with_sources_raw(
    word:    str,
    session,
    timeout: int        = 10,
    sources: list | None = None,
    merge:   bool       = True,
) -> dict | None:
    """
    Source metadata সহ synonym fetch করে।

    Parameters
    ----------
    word, session, timeout, sources, merge : ``fetch_with_sources`` এর মতোই

    Returns
    -------
    dict  যদি কিছু পাওয়া যায় বা সব source empty দেয়::

        {
            "word": "চোখ",
            "results": [
                {"synonym": "চক্ষু", "source": "wiktionary"},
                {"synonym": "নেত্র", "source": "wiktionary"},
                {"synonym": "আঁখি", "source": "shabdkosh"},
            ],
            "words": ["চক্ষু", "নেত্র", "আঁখি"],   # flat list, backward-compatible
            "sources_hit": ["wiktionary", "shabdkosh"],
            "sources_tried": ["wiktionary", "shabdkosh", "english_bangla"],
        }

    None
        সব active source এ network error হয়েছে

    Examples
    --------
        raw = fetch_with_sources_raw("চোখ", session)
        raw["words"]        # → ['চক্ষু', 'নেত্র', ...]
        raw["results"]      # → [{'synonym': 'চক্ষু', 'source': 'wiktionary'}, ...]
        raw["sources_hit"]  # → ['wiktionary']
    """
    active    = sources if sources is not None else DEFAULT_SOURCES
    results:  list[dict] = []   # {"synonym": str, "source": str}
    seen:     set[str]   = set()
    any_error    = False
    sources_hit: list[str] = []

    for name in active:
        fn = SOURCES.get(name)
        if fn is None:
            log.warning("[sources] unknown source '%s' — skipping", name)
            continue

        log.debug("[sources] trying '%s' for '%s'", name, word)
        result = fn(word, session, timeout)  # type: ignore[call-arg]

        if result is None:
            log.warning("[sources] '%s' network error for '%s'", name, word)
            any_error = True
            continue

        if result:
            new_count = 0
            for w in result:
                if w not in seen:
                    seen.add(w)
                    results.append({"synonym": w, "source": name})
                    new_count += 1
            if new_count:
                sources_hit.append(name)
                log.debug("[sources] '%s' added %d word(s) for '%s'", name, new_count, word)

            if not merge:
                break

    if results:
        raw_out = {
            "word":          word,
            "results":       results,
            "words":         [r["synonym"] for r in results],
            "sources_hit":   sources_hit,
            "sources_tried": list(active),
        }
        return apply_quality(raw_out)

    if any_error and not results:
        return None

    # found nothing, no error
    return {
        "word":          word,
        "results":       [],
        "words":         [],
        "sources_hit":   [],
        "sources_tried": list(active),
        "quality":       "empty",
    }


# ═══════════════════════════════════════════════════════════════
# DATASET PATH
# ═══════════════════════════════════════════════════════════════

def _dataset_path() -> Path:
    """Current working directory তে dataset এর standard path।"""
    return Path.cwd() / "bangla_synonyms_data" / "dataset.json"


# ═══════════════════════════════════════════════════════════════
# Shared in-memory store (module-level singleton)
# ═══════════════════════════════════════════════════════════════

_SHARED: dict | None = None


def _ensure_shared() -> dict:
    global _SHARED
    if _SHARED is None:
        _SHARED = _load()
    return _SHARED


def reload_dataset() -> None:
    """
    Disk থেকে dataset পুনরায় পড়ে in-memory cache replace করে।

    ``BanglaSynonyms.download()`` এর পরে automatically call হয়।
    নতুন data তাৎক্ষণিকভাবে সব instances এ দেখা যাবে।
    """
    global _SHARED
    _SHARED = _load()


# ═══════════════════════════════════════════════════════════════
# Disk I/O helpers
# ═══════════════════════════════════════════════════════════════

def _load() -> dict:
    path = _dataset_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            log.debug("[dataset] loaded %d words from %s", len(data), path)
            return data
        except (json.JSONDecodeError, OSError) as e:
            log.error("[dataset] failed to read %s: %s", path, e)
    log.info("[dataset] no dataset found at %s", path)
    return {}


def _save(data: dict) -> None:
    path = _dataset_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.debug("[dataset] saved %d words to %s", len(data), path)
    except OSError as e:
        log.error("[dataset] failed to save dataset: %s", e)
        raise


# ═══════════════════════════════════════════════════════════════
# DatasetManager
# ═══════════════════════════════════════════════════════════════

class DatasetManager:
    """
    Local synonym dataset পড়া, লেখা, merge, export করার class।

    Dataset location:
        ``./bangla_synonyms_data/dataset.json``

    সব instance একই shared in-memory data দেখে — একটায় পরিবর্তন
    সবখানে reflect হয়।

    Usage
    -----
        from bangla_synonyms.core import DatasetManager

        dm = DatasetManager()
        dm.stats()
        dm.add("শব্দ", ["প্রতিশব্দ১", "প্রতিশব্দ২"])
        dm.remove("শব্দ")
        dm.merge("extra.json")
        dm.export("output.json")
        dm.export("output.csv", fmt="csv")
    """

    def __init__(self) -> None:
        pass  # data _SHARED এ থাকে, instance এ না

    @property
    def _data(self) -> dict:
        return _ensure_shared()

    @_data.setter
    def _data(self, value: dict) -> None:
        global _SHARED
        _SHARED = value

    def reload(self) -> None:
        """Disk থেকে dataset পুনরায় load করে।"""
        reload_dataset()

    # ── Read ──────────────────────────────────────────────────

    def get(self, word: str) -> list:
        """Dataset থেকে একটা শব্দের synonym list return করে।"""
        return list(self._data.get(word, []))

    def has(self, word: str) -> bool:
        """শব্দটা dataset এ আছে কিনা check করে।"""
        return word in self._data

    def all_words(self) -> list:
        """Sorted alphabetical word list return করে।"""
        return sorted(self._data.keys())

    def __contains__(self, word: str) -> bool:
        return self.has(word)

    def __len__(self) -> int:
        return len(self._data)

    # ── Write ─────────────────────────────────────────────────

    def add(self, word: str, synonyms: list, save: bool = True) -> None:
        """
        Dataset এ শব্দ ও তার synonym যোগ করে।

        শব্দ আগে থেকে থাকলে নতুন synonym merge হয়।
        ``save=True`` হলে disk এ persist হয়।
        """
        word = word.strip()
        if not word:
            return

        existing = set(self._data.get(word, []))
        merged   = list(self._data.get(word, []))
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
        Dataset থেকে শব্দ মুছে দেয়।

        Return করে True যদি শব্দটা ছিল, False যদি না থাকে।
        """
        if word in self._data:
            del self._data[word]
            if save:
                _save(self._data)
            return True
        return False

    def update(self, word: str, synonyms: list, save: bool = True) -> None:
        """
        শব্দের synonym list replace করে (merge নয়)।
        """
        word = word.strip()
        if not word:
            return
        self._data[word] = [s.strip() for s in synonyms if s.strip() and s.strip() != word]
        if save:
            _save(self._data)

    # ── Merge ─────────────────────────────────────────────────

    def merge(self, path: str) -> int:
        """
        JSON file থেকে dataset merge করে।

        নতুন শব্দ add হয়, পুরনো শব্দে নতুন synonym append হয়।
        নতুন যোগ হওয়া শব্দের সংখ্যা return করে।
        """
        try:
            with open(path, encoding="utf-8") as f:
                incoming: dict = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise ValueError(f"Failed to merge dataset from '{path}': {e}") from e

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

    # ── Export ────────────────────────────────────────────────

    def export(self, path: str, fmt: str = "json") -> None:
        """
        Dataset file এ export করে।

        Parameters
        ----------
        path : output file path
        fmt  : ``"json"`` (default) or ``"csv"``
        """
        if fmt not in ("json", "csv"):
            raise ValueError(f"Unknown format '{fmt}'. Use 'json' or 'csv'.")

        p = Path(path)
        try:
            if fmt == "json":
                p.write_text(
                    json.dumps(dict(sorted(self._data.items())),
                               ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            else:
                with open(p, "w", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["word", "synonyms", "count"])
                    for word, syns in sorted(self._data.items()):
                        writer.writerow([word, " | ".join(syns), len(syns)])
        except OSError as e:
            raise OSError(f"Failed to export to '{path}': {e}") from e

        print(f"[bangla-synonyms] exported {len(self._data)} words → {path}")

    # ── Stats ─────────────────────────────────────────────────

    def stats(self) -> dict:
        """Dataset statistics print করে এবং dict হিসেবে return করে।"""
        total_syns = sum(len(v) for v in self._data.values())
        avg        = round(total_syns / len(self._data), 2) if self._data else 0
        top5       = sorted(
            self._data.items(), key=lambda x: len(x[1]), reverse=True
        )[:5]
        path   = _dataset_path()
        source = str(path) if path.exists() else "no dataset — run BanglaSynonyms.download()"

        result = {
            "total_words":    len(self._data),
            "total_synonyms": total_syns,
            "avg_per_word":   avg,
            "source":         source,
        }

        print(f"Words         : {result['total_words']}")
        print(f"Total synonyms: {result['total_synonyms']}")
        print(f"Avg / word    : {result['avg_per_word']}")
        print(f"Source        : {result['source']}")
        if top5:
            print("Top 5 words   :")
            for word, syns in top5:
                preview = ", ".join(syns[:4])
                suffix  = " ..." if len(syns) > 4 else ""
                print(f"  {word}: {preview}{suffix}")

        return result


# ═══════════════════════════════════════════════════════════════
# WordlistFetcher
# ═══════════════════════════════════════════════════════════════

class WordlistFetcher:
    """
    Wiktionary থেকে বাংলা শব্দের list fetch করার class।

    Usage
    -----
        from bangla_synonyms.core import WordlistFetcher

        wf    = WordlistFetcher()
        words = wf.fetch(limit=500)
        new   = wf.filter_new(words, dm)
        wf.save(words, "word_list.txt")
    """

    def __init__(self, timeout: int = 10) -> None:
        self.timeout  = timeout
        self._session = make_session()

    def fetch(self, limit: int = 500) -> list:
        """Wiktionary থেকে সর্বোচ্চ ``limit`` টা বাংলা শব্দ fetch করে।"""
        print(f"[bangla-synonyms] fetching up to {limit} words from Wiktionary...")
        words = fetch_word_list(limit, self._session, self.timeout)
        print(f"[bangla-synonyms] fetched {len(words)} Bangla words")
        return words

    def filter_new(self, words: list, dm: DatasetManager) -> list:
        """Dataset এ নেই এমন শব্দগুলো return করে (resume সুবিধার জন্য)।"""
        return [w for w in words if w not in dm]

    def save(self, words: list, path: str) -> None:
        """Word list text file এ save করে।"""
        try:
            Path(path).write_text("\n".join(words), encoding="utf-8")
            print(f"[bangla-synonyms] saved {len(words)} words → {path}")
        except OSError as e:
            raise OSError(f"Failed to save word list to '{path}': {e}") from e

    def load(self, path: str) -> list:
        """Text file থেকে word list load করে।"""
        try:
            return Path(path).read_text(encoding="utf-8").strip().splitlines()
        except OSError as e:
            raise OSError(f"Failed to load word list from '{path}': {e}") from e


# ═══════════════════════════════════════════════════════════════
# BatchScraper
# ═══════════════════════════════════════════════════════════════

class BatchScraper:
    """
    অনেকগুলো শব্দের synonym একসাথে scrape করার class।

    Parameters
    ----------
    dataset    : DatasetManager — না দিলে shared instance ব্যবহার করে
    delay      : প্রতিটা HTTP request এর মাঝে অপেক্ষা (seconds, default: 1.0)
    timeout    : HTTP request timeout (seconds, default: 10)
    save_every : প্রতি N শব্দ পরে disk এ flush করে (default: 50)
    sources    : কোন sources ব্যবহার করবে (default: সব তিনটা)
    merge      : True → সব source merge করে, False → প্রথম hit এ থামে

    Usage
    -----
        bs = BatchScraper(delay=1.0)
        bs.run(["চোখ", "মা", "আকাশ"])
        bs.run(words, sources=["wiktionary"])
        bs.run_from_wiktionary(limit=500)
    """

    def __init__(
        self,
        dataset:    DatasetManager | None = None,
        delay:      float = 1.0,
        timeout:    int   = 10,
        save_every: int   = 50,
        sources:    list | None = None,
        merge:      bool  = True,
    ) -> None:
        self.dataset    = dataset or DatasetManager()
        self.delay      = delay
        self.timeout    = timeout
        self.save_every = save_every
        self.sources    = sources
        self.merge      = merge
        self._session   = make_session()

    def run(
        self,
        words:         list,
        skip_existing: bool       = True,
        show_progress: bool       = True,
        sources:       list | None = None,
    ) -> dict:
        """
        শব্দের list এর synonym scrape করে।

        Parameters
        ----------
        words          : scrape করার বাংলা শব্দের list
        skip_existing  : dataset এ আছে এমন শব্দ skip করে (resume সুবিধা)
        show_progress  : [i/total] progress দেখায়
        sources        : এই run এর জন্য sources override (None = instance default)

        Returns
        -------
        dict
            নতুন scrape হওয়া ``{word: [synonyms]}``
        """
        active_sources = sources if sources is not None else self.sources

        if skip_existing:
            words = [w for w in words if w not in self.dataset]

        total   = len(words)
        scraped: dict = {}
        found = skipped = errors = 0

        for i, word in enumerate(words):
            try:
                syns = fetch_with_sources(
                    word, self._session, self.timeout,
                    active_sources, self.merge,
                )
            except Exception as e:
                log.error("[batch] unexpected error for '%s': %s", word, e)
                syns = None

            if syns is None:
                errors += 1
                status  = "❌ network error"
            elif syns:
                scraped[word] = syns
                self.dataset.add(word, syns, save=False)
                found  += 1
                preview = ", ".join(syns[:3])
                suffix  = " ..." if len(syns) > 3 else ""
                status  = f"✓ {preview}{suffix}"
            else:
                skipped += 1
                status   = "— not found"

            if show_progress:
                print(f"  [{i + 1:>{len(str(total))}}/{total}] {word}: {status}")

            if (i + 1) % self.save_every == 0:
                try:
                    _save(self.dataset._data)
                    log.debug("[batch] checkpoint saved at %d words", i + 1)
                except OSError as e:
                    log.error("[batch] failed to save checkpoint: %s", e)

            if i < total - 1:
                time.sleep(self.delay)

        # final save
        try:
            _save(self.dataset._data)
        except OSError as e:
            log.error("[batch] failed to save final dataset: %s", e)

        if show_progress:
            print(f"\n[bangla-synonyms] done: {found} found, {skipped} not found, {errors} errors")

        return scraped

    def run_from_wiktionary(self, limit: int = 200) -> dict:
        """
        Wiktionary থেকে word list fetch করে সব scrape করে।

        Parameters
        ----------
        limit : সর্বোচ্চ কত শব্দ scrape করবে (default: 200)
        """
        print(f"[bangla-synonyms] fetching word list from Wiktionary (limit={limit})...")
        words = fetch_word_list(limit, self._session, self.timeout)
        print(f"[bangla-synonyms] {len(words)} words fetched — starting scrape...")
        return self.run(words, skip_existing=True)