"""
bangla_synonyms.cli
--------------------
Command-line interface — also importable as a Python module.

Terminal usage
--------------
    bangla-synonyms download
    bangla-synonyms download --version mini
    bangla-synonyms download --force

    bangla-synonyms get চোখ
    bangla-synonyms get চোখ মা সুন্দর
    bangla-synonyms get চোখ --offline
    bangla-synonyms get চোখ --sources wiktionary
    bangla-synonyms get চোখ --sources wiktionary --sources shabdkosh
    bangla-synonyms get চোখ --no-merge
    bangla-synonyms get চোখ --raw

    bangla-synonyms build
    bangla-synonyms build --limit 500 --delay 2.0
    bangla-synonyms build --sources wiktionary
    bangla-synonyms build --no-merge

    bangla-synonyms stats
    bangla-synonyms export synonyms.json
    bangla-synonyms export synonyms.csv --format csv

In-code usage
-------------
    from bangla_synonyms.cli import get, build, stats

    get(["চোখ", "মা"])
    get(["চোখ"], offline=True)
    get(["চোখ"], sources=["wiktionary"], merge=False)
    get(["চোখ"], raw=True)
    build(limit=200, delay=1.0)
    stats()
"""
from __future__ import annotations

import json
import sys

import click

from bangla_synonyms import Scrapper
from bangla_synonyms.core import (DEFAULT_SOURCES, SOURCES, BatchScraper,
                                  DatasetManager)

# ── Importable helpers ────────────────────────────────────────


def get(
    words: list,
    offline: bool = False,
    sources: list | None = None,
    merge: bool = True,
    delay: float = 1.0,
    raw: bool = False,
) -> dict:
    """
    Look up synonyms for a list of words and print the results.

    Parameters
    ----------
    words   : list of Bangla words
    offline : use local dataset only (no internet)
    sources : which sources to use (default: all)
    merge   : merge all source results (True) or stop at first hit (False)
    delay   : seconds between requests
    raw     : print and return full source metadata instead of plain lists

    Returns dict[word -> list[str]] when raw=False,
            dict[word -> dict]      when raw=True.
    """
    sc = Scrapper(offline=offline, sources=sources, merge=merge, delay=delay)
    result = sc.get_many(words, raw=raw)
    for word, syns in result.items():
        if raw:
            print(f"{word}:")
            print(json.dumps(syns, ensure_ascii=False, indent=2))
        else:
            print(f"{word}: {', '.join(syns) if syns else '—'}")
    return result


def build(
    limit: int = 200,
    delay: float = 1.0,
    sources: list | None = None,
    merge: bool = True,
) -> int:
    """
    Build / expand the local dataset by scraping.

    Parameters
    ----------
    limit   : number of words to scrape
    delay   : seconds between requests
    sources : which sources to use (default: all)
    merge   : merge all source results (True) or stop at first hit (False)

    Returns number of words newly added.
    """
    scraper = BatchScraper(
        dataset=DatasetManager(),
        delay=delay,
        sources=sources,
        merge=merge,
    )
    return len(scraper.run_from_wiktionary(limit=limit))


def stats() -> dict:
    """Print and return dataset statistics."""
    return DatasetManager().stats()


# ── CLI ───────────────────────────────────────────────────────

_SOURCE_CHOICES = list(SOURCES.keys())
_SOURCES_HELP = (
    "Source to use (repeatable). "
    "Choices: "
    + ", ".join(_SOURCE_CHOICES)
    + f". Default: all ({', '.join(DEFAULT_SOURCES)})"
)


@click.group()
@click.version_option("1.0.0", prog_name="bangla-synonyms")
def main() -> None:
    """Bangla synonym lookup — offline dataset + live scraping."""


@main.command("download")
@click.option(
    "--version",
    "-v",
    default="latest",
    show_default=True,
    type=click.Choice(["latest", "mini"]),
    help="Dataset version to download.",
)
@click.option("--force", is_flag=True, help="Re-download even if dataset exists.")
def download_cmd(version: str, force: bool) -> None:
    """
    Download the community dataset from GitHub Releases.

    \b
    Examples:
        bangla-synonyms download
        bangla-synonyms download --version mini
        bangla-synonyms download --force
    """
    Scrapper.download(version=version, force=force)


@main.command("get")
@click.argument("words", nargs=-1, required=True)
@click.option("--offline", is_flag=True, help="Local dataset only, no internet.")
@click.option(
    "--sources",
    "-s",
    multiple=True,
    type=click.Choice(_SOURCE_CHOICES),
    help=_SOURCES_HELP,
)
@click.option(
    "--no-merge",
    "no_merge",
    is_flag=True,
    help="Stop at first source that returns results.",
)
@click.option(
    "--delay", "-d", default=1.0, show_default=True, help="Seconds between requests."
)
@click.option(
    "--raw",
    "raw",
    is_flag=True,
    help="Show full source metadata (per-source breakdown, quality) instead of plain synonym list.",
)
def get_cmd(
    words: tuple, offline: bool, sources: tuple, no_merge: bool, delay: float, raw: bool
) -> None:
    """
    Look up synonyms for one or more words.

    \b
    Examples:
        bangla-synonyms get চোখ
        bangla-synonyms get চোখ মা সুন্দর
        bangla-synonyms get চোখ --offline
        bangla-synonyms get চোখ --sources wiktionary
        bangla-synonyms get চোখ --no-merge
        bangla-synonyms get চোখ --raw
    """
    sc = Scrapper(
        offline=offline, delay=delay, sources=list(sources) or None, merge=not no_merge
    )
    result = sc.get_many(list(words), raw=raw)
    for word, syns in result.items():
        if raw:
            print(f"{word}:")
            print(json.dumps(syns, ensure_ascii=False, indent=2))
        else:
            print(f"{word}: {', '.join(syns) if syns else '—'}")


@main.command("build")
@click.option("--limit", "-l", default=200, show_default=True, help="Words to scrape.")
@click.option(
    "--delay", "-d", default=1.0, show_default=True, help="Seconds between requests."
)
@click.option(
    "--sources",
    "-s",
    multiple=True,
    type=click.Choice(_SOURCE_CHOICES),
    help=_SOURCES_HELP,
)
@click.option(
    "--no-merge", "no_merge", is_flag=True, help="Stop at first source with results."
)
def build_cmd(limit: int, delay: float, sources: tuple, no_merge: bool) -> None:
    """
    Scrape and build / expand the local dataset.

    \b
    Examples:
        bangla-synonyms build
        bangla-synonyms build --limit 500
        bangla-synonyms build --sources wiktionary --sources shabdkosh
    """
    added = build(
        limit=limit, delay=delay, sources=list(sources) or None, merge=not no_merge
    )
    print(f"[bangla-synonyms] {added} new word(s) added to dataset.")


@main.command("stats")
def stats_cmd() -> None:
    """Show local dataset statistics."""
    stats()


@main.command("export")
@click.argument("output")
@click.option(
    "--format",
    "-f",
    "fmt",
    default="json",
    show_default=True,
    type=click.Choice(["json", "csv"]),
    help="Output format.",
)
def export_cmd(output: str, fmt: str) -> None:
    """
    Export the local dataset to a file.

    \b
    Examples:
        bangla-synonyms export synonyms.json
        bangla-synonyms export synonyms.csv --format csv
    """
    try:
        DatasetManager().export(output, fmt=fmt)
    except (OSError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
