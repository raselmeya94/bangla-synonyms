"""
bangla_synonyms.synonyms
-------------------------
BanglaSynonyms — simple, beginner-friendly interface.

For full control over sources and scraping behaviour, use
``Scrapper`` directly (see ``_scrapper.py``).
"""
from __future__ import annotations

import logging

from ._scrapper import Scrapper
from .core import DatasetManager, reload_dataset, DEFAULT_SOURCES

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


class BanglaSynonyms:
    """
    Simple Bangla synonym lookup.

    Download the dataset once, then look up any word:

        BanglaSynonyms.download()

        bn = BanglaSynonyms()
        bn.get("চোখ")    # → ['চক্ষু', 'নেত্র', 'লোচন', ...]

    For words not in the local dataset, it automatically falls back
    to live web scraping (Wiktionary → Shabdkosh → English-Bangla).

    Parameters
    ----------
    sources   : list|None — which scraping sources to use when a word
                is not found locally. Default: all three sources.
                Options: "wiktionary", "shabdkosh", "english_bangla"
    merge     : bool — merge results from all sources (True, default)
                or stop at the first source that returns results (False)
    auto_save : bool — save scraped results to local dataset (default: False)
                set True if you want online lookups to persist for next time
    delay     : float — seconds between online requests (default: 1.0)
    timeout   : int   — HTTP timeout in seconds (default: 10)

    Examples
    --------
        bn = BanglaSynonyms()                           # no auto-save (default)
        bn = BanglaSynonyms(auto_save=True)             # save scraped results
        bn = BanglaSynonyms(sources=["wiktionary"])     # Wiktionary only
        bn = BanglaSynonyms(merge=False)                # first-match mode
    """

    # ── Class method — no instance needed ─────────────────────

    @classmethod
    def download(cls, version: str = "latest", force: bool = False) -> None:
        """
        Bangla synonym dataset download করে current directory তে save করে।

        Saves to: ``./bangla_synonyms_data/dataset.json``

        Parameters
        ----------
        version : ``"latest"`` (default) — full dataset (~10 000 words)
                  ``"mini"``             — small starter dataset
        force   : re-download even if dataset already exists

        Examples
        --------
            BanglaSynonyms.download()            # latest
            BanglaSynonyms.download("mini")      # small version
            BanglaSynonyms.download(force=True)  # force re-download
        """
        import requests
        from pathlib import Path

        url = _DATASET_URLS.get(version)
        if url is None:
            available = ", ".join(f'"{v}"' for v in _DATASET_URLS)
            print(f"[bangla-synonyms] unknown version '{version}'. available: {available}")
            return

        save_path = Path.cwd() / "bangla_synonyms_data" / "dataset.json"

        if save_path.exists() and not force:
            print(f"[bangla-synonyms] dataset already exists at {save_path}")
            print("[bangla-synonyms] use BanglaSynonyms.download(force=True) to re-download.")
            return

        save_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[bangla-synonyms] downloading '{version}' dataset...")
        print(f"[bangla-synonyms] source : {url}")
        print(f"[bangla-synonyms] saving : {save_path}")

        try:
            resp = requests.get(url, stream=True, timeout=30)
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            print("[bangla-synonyms] download timed out. check your connection and try again.")
            return
        except requests.exceptions.ConnectionError:
            print("[bangla-synonyms] could not connect. check your internet connection.")
            return
        except requests.exceptions.HTTPError as e:
            print(f"[bangla-synonyms] server returned HTTP {e.response.status_code}.")
            return
        except requests.exceptions.RequestException as e:
            print(f"[bangla-synonyms] download failed: {e}")
            return

        total     = int(resp.headers.get("content-length", 0))
        received  = 0
        bar_width = 30

        try:
            with open(save_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    fh.write(chunk)
                    received += len(chunk)
                    if total:
                        pct    = received / total
                        filled = int(bar_width * pct)
                        bar    = "█" * filled + "░" * (bar_width - filled)
                        kb     = received // 1024
                        print(f"\r  [{bar}] {kb} KB", end="", flush=True)
        except OSError as e:
            print(f"\n[bangla-synonyms] failed to write file: {e}")
            return

        print(f"\r  [{'█' * bar_width}] done          ")
        print(f"[bangla-synonyms] ✓ dataset ready at {save_path}")

        # Reload in-memory cache so existing instances see new data immediately
        reload_dataset()

    # ── Instance ───────────────────────────────────────────────

    def __init__(
        self,
        sources:   list | None = None,
        merge:     bool        = True,
        auto_save: bool        = False,  # False by default — user must opt in
        delay:     float       = 1.0,
        timeout:   int         = 10,
    ) -> None:
        self._sc = Scrapper(
            offline=False,
            auto_save=auto_save,
            delay=delay,
            timeout=timeout,
            sources=sources,
            merge=merge,
        )

    # ── Lookup ────────────────────────────────────────────────

    def get(self, word: str, raw: bool = False) -> list[str] | dict:
        """
        একটা শব্দের synonym list return করে।

        Local dataset এ না পেলে automatically online fallback করে।
        কিছু না পেলে empty list ``[]`` return করে।

        Parameters
        ----------
        word : Bangla শব্দ
        raw  : False (default) → flat list
               True            → source metadata সহ dict

        Examples
        --------
            bn.get("চোখ")
            # → ['চক্ষু', 'নেত্র', 'লোচন', 'আঁখি']

            bn.get("চোখ", raw=True)
            # → {
            #     "word":          "চোখ",
            #     "source":        "wiktionary",
            #     "results":       [{"synonym": "চক্ষু", "source": "wiktionary"}, ...],
            #     "words":         ["চক্ষু", "নেত্র", ...],
            #     "sources_hit":   ["wiktionary"],
            #     "sources_tried": ["wiktionary", "shabdkosh", "english_bangla"],
            # }
        """
        return self._sc.get(word, raw=raw)

    def get_many(self, words: list[str], raw: bool = False) -> dict:
        """
        একাধিক শব্দের synonym lookup করে।

        Parameters
        ----------
        words : Bangla শব্দের list
        raw   : False (default) → ``{word: [synonyms]}``
                True            → ``{word: raw_dict}`` (source metadata সহ)

        Examples
        --------
            bn.get_many(["চোখ", "মা", "দুঃখ"])
            # → {'চোখ': [...], 'মা': [...], 'দুঃখ': [...]}

            bn.get_many(["চোখ", "মা"], raw=True)
            # → {
            #     'চোখ': {"word": "চোখ", "results": [...], "words": [...], ...},
            #     'মা':  {"word": "মা",  "results": [...], "words": [...], ...},
            #   }
        """
        return self._sc.get_many(words, raw=raw)

    # ── Dataset management ────────────────────────────────────

    def add(self, word: str, synonyms: list[str]) -> None:
        """
        Manually add synonyms to local dataset.

        Examples
        --------
            bn.add("পরিবেশ", ["প্রকৃতি", "জগত"])
        """
        self._sc._dm.add(word, synonyms)

    def stats(self) -> dict:
        """Print and return dataset statistics."""
        return self._sc._dm.stats()

    def export(self, path: str, fmt: str = "json") -> None:
        """
        Export dataset to file.

        Parameters
        ----------
        path : output file path
        fmt  : ``"json"`` (default) or ``"csv"``

        Examples
        --------
            bn.export("synonyms.json")
            bn.export("synonyms.csv", fmt="csv")
        """
        self._sc._dm.export(path, fmt)

    def __repr__(self) -> str:
        src = ", ".join(self._sc.active_sources)
        return (
            f"BanglaSynonyms("
            f"words={len(self._sc._dm)}, "
            f"sources=[{src}], "
            f"merge={self._sc.merge})"
        )
