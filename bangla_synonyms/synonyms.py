"""
bangla_synonyms.synonyms
-------------------------
BanglaSynonyms — simple, beginner-friendly interface.
"""
from __future__ import annotations
from ._scrapper import Scrapper
from .core import DatasetManager

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

    Download dataset:
        BanglaSynonyms.download("latest")   # full dataset (~10 000 words)
        BanglaSynonyms.download("mini")     # small starter dataset

    Then use:
        bn = BanglaSynonyms()
        bn.get("চোখ")    # → ['চক্ষু', 'নেত্র', 'লোচন', ...]
    """

    # ── Class method — no instance needed ─────────────────────

    @classmethod
    def download(cls, version: str = "latest", force: bool = False) -> None:
        """
        Download the Bangla synonym dataset into the current directory.

        Saves to: ./bangla_synonyms_data/dataset.json

        Parameters
        ----------
        version : "latest" (default) — full dataset (~10 000 words)
                  "mini"             — small starter dataset
        force   : re-download even if dataset already exists

        Example
        -------
            from bangla_synonyms import BanglaSynonyms

            BanglaSynonyms.download()            # latest
            BanglaSynonyms.download("mini")      # small version
            BanglaSynonyms.download(force=True)  # re-download
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
            print(f"[bangla-synonyms] dataset already exists → {save_path}")
            print("[bangla-synonyms] use BanglaSynonyms.download(force=True) to re-download.")
            return

        save_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[bangla-synonyms] downloading '{version}' dataset...")
        print(f"[bangla-synonyms] source  : {url}")
        print(f"[bangla-synonyms] saving  : {save_path}")

        try:
            resp = requests.get(url, stream=True, timeout=30)
            resp.raise_for_status()

            total     = int(resp.headers.get("content-length", 0))
            received  = 0
            bar_width = 30

            with open(save_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    fh.write(chunk)
                    received += len(chunk)
                    if total:
                        pct   = received / total
                        filled = int(bar_width * pct)
                        bar   = "█" * filled + "░" * (bar_width - filled)
                        kb    = received // 1024
                        print(f"\r  [{bar}] {kb} KB", end="", flush=True)

            print(f"\r  [{'█' * bar_width}] done          ")
            print(f"[bangla-synonyms] ✓ dataset ready — {save_path}")

        except Exception as exc:
            print(f"\n[bangla-synonyms] download failed: {exc}")

    # ── Instance methods ───────────────────────────────────────

    def __init__(self) -> None:
        self._sc = Scrapper(offline=False, auto_save=True, delay=1.0)

    # ── Lookup ────────────────────────────────────────────────

    def get(self, word: str) -> list[str]:
        """
        Get synonyms for a single word.

        Returns an empty list if nothing is found.

        Example
        -------
            bn.get("চোখ")    # → ['চক্ষু', 'নেত্র', 'লোচন', 'আঁখি']
            bn.get("xyz")    # → []
        """
        return self._sc.get(word)

    def get_many(self, words: list[str]) -> dict[str, list[str]]:
        """
        Get synonyms for multiple words.

        Example
        -------
            bn.get_many(["চোখ", "মা", "দুঃখ"])
            # → {'চোখ': [...], 'মা': [...], 'দুঃখ': [...]}
        """
        return self._sc.get_many(words)

    # ── Dataset ───────────────────────────────────────────────

    def add(self, word: str, synonyms: list[str]) -> None:
        """
        Manually add synonyms to local dataset.

        Example
        -------
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
        fmt  : "json" (default) or "csv"

        Example
        -------
            bn.export("synonyms.json")
            bn.export("synonyms.csv", fmt="csv")
        """
        self._sc._dm.export(path, fmt)

    def __repr__(self) -> str:
        return f"BanglaSynonyms(words={len(self._sc._dm)})"
