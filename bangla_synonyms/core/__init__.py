"""
bangla_synonyms.core
---------------------
Advanced features for power users and researchers.

Classes
-------
DatasetManager   — load, save, merge, export the synonym dataset
WordlistFetcher  — pull Bangla word lists from Wiktionary
BatchScraper     — scrape many words with progress tracking + resume

Quick start
-----------
    from bangla_synonyms.core import DatasetManager, WordlistFetcher, BatchScraper

    # Inspect / edit the local dataset
    dm = DatasetManager()
    dm.stats()
    dm.merge("extra.json")
    dm.export("output.csv", fmt="csv")

    # Get a word list from Wiktionary
    wf    = WordlistFetcher()
    words = wf.fetch(limit=500)

    # Bulk-scrape with progress + auto-resume
    bs     = BatchScraper(dataset=dm, delay=1.0)
    result = bs.run(words)

    # One-liner: fetch word list then scrape all
    bs.run_from_wiktionary(limit=200)
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from ._wikitext import fetch_synonyms, fetch_word_list, make_session

# ── Paths ─────────────────────────────────────────────────────
_BUILTIN   = Path(__file__).parent.parent / "data" / "builtin_dataset.json"
_USER_FILE = Path.home() / ".bangla_synonyms" / "dataset.json"


# ── DatasetManager ────────────────────────────────────────────

class DatasetManager:
    """
    Load, inspect, merge, and export the synonym dataset.

    The manager resolves data from two layers (in priority order):

    1. **User dataset** — ``~/.bangla_synonyms/dataset.json``
       Words scraped at runtime are written here automatically.
    2. **Built-in dataset** — bundled with the package.

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
        self._data: dict[str, list[str]] = _load()

    # ── Read ──────────────────────────────────────────────────

    def get(self, word: str) -> list[str]:
        """Return synonyms for *word*, or ``[]`` if absent."""
        return self._data.get(word, [])

    def has(self, word: str) -> bool:
        """Return ``True`` if *word* is in the dataset."""
        return word in self._data

    def all_words(self) -> list[str]:
        """Return all words (sorted alphabetically)."""
        return sorted(self._data.keys())

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, word: str) -> bool:
        return word in self._data

    # ── Write ─────────────────────────────────────────────────

    def add(self, word: str, synonyms: list[str]) -> None:
        """
        Add or update synonyms for *word* (persists to disk).

        New synonyms are merged with any existing ones —
        duplicates are silently ignored.

        Example
        -------
            dm.add("চোখ", ["চক্ষু", "নেত্র"])
        """
        if not synonyms:
            return
        if word in self._data:
            existing = set(self._data[word])
            self._data[word] += [s for s in synonyms if s not in existing]
        else:
            self._data[word] = list(synonyms)
        _save(self._data)

    def remove(self, word: str) -> bool:
        """
        Remove *word* from the dataset.

        Returns ``True`` if the word existed and was removed.
        """
        if word in self._data:
            del self._data[word]
            _save(self._data)
            return True
        return False

    # ── File operations ───────────────────────────────────────

    def load(self, path: str) -> None:
        """
        Replace the current in-memory dataset with a JSON file.

        Does **not** save automatically — call ``export`` to persist.
        """
        with open(path, encoding="utf-8") as f:
            self._data = json.load(f)

    def merge(self, path: str) -> int:
        """
        Merge another JSON dataset into the current one.

        Returns the number of *new* words added.

        Example
        -------
            added = dm.merge("community_dataset.json")
            print(f"{added} new words merged")
        """
        with open(path, encoding="utf-8") as f:
            incoming: dict[str, list[str]] = json.load(f)

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

    def export(self, path: str, fmt: str = "json") -> None:
        """
        Export the dataset to a file.

        Parameters
        ----------
        path : output file path
        fmt  : ``"json"`` (default) or ``"csv"``

        Example
        -------
            dm.export("synonyms.json")
            dm.export("synonyms.csv", fmt="csv")
        """
        p = Path(path)
        if fmt == "json":
            p.write_text(
                json.dumps(dict(sorted(self._data.items())),
                           ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        elif fmt == "csv":
            with open(p, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["word", "synonyms", "count"])
                for word, syns in sorted(self._data.items()):
                    w.writerow([word, " | ".join(syns), len(syns)])
        print(f"Exported {len(self._data)} words → {path}")

    # ── Stats ─────────────────────────────────────────────────

    def stats(self) -> dict:
        """
        Print and return dataset statistics.

        Example
        -------
            dm.stats()
            # Words         : 1 250
            # Total synonyms: 6 430
            # Avg per word  : 5.14
        """
        total_syns = sum(len(v) for v in self._data.values())
        avg        = round(total_syns / len(self._data), 2) if self._data else 0
        top5       = sorted(
            self._data.items(), key=lambda x: len(x[1]), reverse=True
        )[:5]
        source     = str(_USER_FILE) if _USER_FILE.exists() else "built-in"

        result = {
            "total_words":    len(self._data),
            "total_synonyms": total_syns,
            "avg_per_word":   avg,
            "source":         source,
        }

        print(f"Words         : {result['total_words']}")
        print(f"Total synonyms: {result['total_synonyms']}")
        print(f"Avg per word  : {result['avg_per_word']}")
        print(f"Source        : {result['source']}")
        if top5:
            print("\nTop 5 words:")
            for word, syns in top5:
                preview = ", ".join(syns[:4])
                suffix  = "..." if len(syns) > 4 else ""
                print(f"  {word}: {preview}{suffix}")

        return result

    def download(self, url: str | None = None, force: bool = False) -> bool:
        """
        Download the full community dataset (~10 000 words) from GitHub Releases.

        Parameters
        ----------
        url   : custom download URL (defaults to official GitHub release)
        force : re-download even if a local dataset already exists

        Returns ``True`` on success.
        """
        import requests
        from rich.progress import (
            Progress, DownloadColumn, TransferSpeedColumn, BarColumn, TextColumn,
        )

        _DATASET_URL = (
            "https://github.com/bangla-nlp/bangla-synonyms/releases/latest/download/"
            "bangla_synonyms_full.json"
        )
        target_url = url or _DATASET_URL

        if _USER_FILE.exists() and not force:
            print(f"Dataset already exists at {_USER_FILE}")
            print("Use force=True or --force flag to re-download.")
            return True

        _USER_FILE.parent.mkdir(parents=True, exist_ok=True)

        try:
            resp = requests.get(target_url, stream=True, timeout=30)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))

            with Progress(
                TextColumn("[bold blue]Downloading..."),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
            ) as progress:
                task = progress.add_task("download", total=total)
                with open(_USER_FILE, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=8192):
                        fh.write(chunk)
                        progress.update(task, advance=len(chunk))

            self._data = _load()   # reload after download
            return True

        except Exception as exc:
            print(f"Download failed: {exc}")
            return False


# ── WordlistFetcher ───────────────────────────────────────────

class WordlistFetcher:
    """
    Fetch Bangla word lists from the Wiktionary API.

    Usage
    -----
        from bangla_synonyms.core import WordlistFetcher

        wf    = WordlistFetcher()
        words = wf.fetch(limit=500)
        wf.save(words, "word_list.txt")

        # Only words not yet in your dataset
        new = wf.filter_new(words, dataset_manager)
    """

    def __init__(self, timeout: int = 10) -> None:
        self.timeout  = timeout
        self._session = make_session()

    def fetch(self, limit: int = 500) -> list[str]:
        """
        Fetch up to *limit* Bangla words from Wiktionary.

        Example
        -------
            words = WordlistFetcher().fetch(limit=1000)
            print(f"Fetched {len(words)} words")
        """
        print(f"Fetching up to {limit} words from Wiktionary…")
        words = fetch_word_list(limit, self._session, self.timeout)
        print(f"Got {len(words)} Bangla words")
        return words

    def filter_new(self, words: list[str], dm: "DatasetManager") -> list[str]:
        """Return only words not already in *dm*."""
        return [w for w in words if w not in dm]

    def save(self, words: list[str], path: str) -> None:
        """Save word list to a text file (one word per line)."""
        Path(path).write_text("\n".join(words), encoding="utf-8")
        print(f"Saved {len(words)} words → {path}")

    def load(self, path: str) -> list[str]:
        """Load word list from a text file (one word per line)."""
        return Path(path).read_text(encoding="utf-8").strip().splitlines()


# ── BatchScraper ──────────────────────────────────────────────

class BatchScraper:
    """
    Scrape synonyms for many words with progress tracking and resume support.

    Parameters
    ----------
    dataset    : DatasetManager to use (creates a fresh one if omitted)
    delay      : seconds between HTTP requests (default: 1.0)
    timeout    : request timeout in seconds (default: 10)
    save_every : flush to disk every N words (default: 50)

    Usage
    -----
        from bangla_synonyms.core import BatchScraper, DatasetManager

        dm      = DatasetManager()
        scraper = BatchScraper(dataset=dm, delay=1.0)
        result  = scraper.run(["চোখ", "মা", "আকাশ", "নদী"])

        # Resume: words already in `dm` are skipped automatically
        result  = scraper.run(words, skip_existing=True)

        # One-liner — fetch word list then scrape
        scraper.run_from_wiktionary(limit=500)
    """

    def __init__(
        self,
        dataset:    "DatasetManager | None" = None,
        delay:      float = 1.0,
        timeout:    int   = 10,
        save_every: int   = 50,
    ) -> None:
        self.dataset    = dataset or DatasetManager()
        self.delay      = delay
        self.timeout    = timeout
        self.save_every = save_every
        self._session   = make_session()

    def run(
        self,
        words:         list[str],
        skip_existing: bool = True,
        show_progress: bool = True,
    ) -> dict[str, list[str]]:
        """
        Scrape synonyms for *words*.

        Parameters
        ----------
        words          : list of Bangla words to scrape
        skip_existing  : skip words already in dataset (enables safe resume)
        show_progress  : print ``[i/total] word: status`` lines

        Returns
        -------
        dict mapping each *newly scraped* word to its synonyms.

        Example
        -------
            result = BatchScraper().run(["চোখ", "মা", "নদী"])
        """
        if skip_existing:
            words = [w for w in words if w not in self.dataset]

        total   = len(words)
        scraped: dict[str, list[str]] = {}
        found   = errors = 0

        for i, word in enumerate(words):
            syns = fetch_synonyms(word, self._session, self.timeout)

            if syns is None:
                errors += 1
                status  = "✗ error"
            elif syns:
                scraped[word] = syns
                self.dataset.add(word, syns)
                found  += 1
                preview = ", ".join(syns[:3])
                suffix  = "..." if len(syns) > 3 else ""
                status  = f"✓ {preview}{suffix}"
            else:
                status = "— not found"

            if show_progress:
                print(f"[{i + 1}/{total}] {word}: {status}")

            if (i + 1) % self.save_every == 0:
                _save(self.dataset._data)

            if i < total - 1:
                time.sleep(self.delay)

        _save(self.dataset._data)

        if show_progress:
            not_found = total - found - errors
            print(f"\nDone: {found} found, {errors} errors, {not_found} not found")

        return scraped

    def run_from_wiktionary(self, limit: int = 200) -> dict[str, list[str]]:
        """
        Fetch word list from Wiktionary then scrape all of them.

        Example
        -------
            BatchScraper().run_from_wiktionary(limit=500)
        """
        words = fetch_word_list(limit, self._session, self.timeout)
        return self.run(words, skip_existing=True)


# ── Shared helpers (also used by _scrapper.py) ────────────────

def _load() -> dict[str, list[str]]:
    """Load dataset: user file takes priority over built-in."""
    if _USER_FILE.exists():
        try:
            return json.loads(_USER_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    if _BUILTIN.exists():
        return json.loads(_BUILTIN.read_text(encoding="utf-8"))
    return {}


def _save(data: dict) -> None:
    """Persist *data* to the user dataset file."""
    _USER_FILE.parent.mkdir(parents=True, exist_ok=True)
    _USER_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
