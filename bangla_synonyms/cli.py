"""
bangla_synonyms.cli
--------------------
Command-line interface — also fully importable as a Python module.

Terminal usage
--------------
    bangla-synonyms get চোখ
    bangla-synonyms get চোখ মা সুন্দর
    bangla-synonyms get চোখ --offline
    bangla-synonyms build
    bangla-synonyms build --limit 500 --delay 2.0
    bangla-synonyms stats
    bangla-synonyms export synonyms.json
    bangla-synonyms export synonyms.csv --format csv
    bangla-synonyms download
    bangla-synonyms download --force

In-code usage
-------------
    from bangla_synonyms.cli import get, build, stats

    get(["চোখ", "মা"])
    get(["চোখ"], offline=True)
    build(limit=200, delay=1.0)
    stats()
"""
from __future__ import annotations

import click
from bangla_synonyms import Scrapper
from bangla_synonyms.core import DatasetManager, BatchScraper, WordlistFetcher


# ── Importable helpers ────────────────────────────────────────

def get(words: list[str], offline: bool = False) -> dict[str, list[str]]:
    """
    Look up synonyms for a list of words and print the results.

    Parameters
    ----------
    words   : list of Bangla words
    offline : use local dataset only (no internet)

    Returns
    -------
    dict mapping each word to its synonym list

    Example
    -------
        from bangla_synonyms.cli import get

        get(["চোখ", "মা"])
        get(["চোখ"], offline=True)
    """
    sc     = Scrapper(offline=offline)
    result = sc.get_many(words)
    for word, syns in result.items():
        line = ", ".join(syns) if syns else "—"
        print(f"{word}: {line}")
    return result


def build(limit: int = 200, delay: float = 1.0) -> int:
    """
    Build / expand the local dataset by scraping Wiktionary.

    Parameters
    ----------
    limit : number of words to scrape (default: 200)
    delay : seconds between requests  (default: 1.0)

    Returns
    -------
    Number of words newly added

    Example
    -------
        from bangla_synonyms.cli import build

        build(limit=500)
    """
    dm      = DatasetManager()
    scraper = BatchScraper(dataset=dm, delay=delay)
    result  = scraper.run_from_wiktionary(limit=limit)
    return len(result)


def stats() -> dict:
    """
    Print and return dataset statistics.

    Example
    -------
        from bangla_synonyms.cli import stats

        stats()
    """
    return DatasetManager().stats()


# ── CLI group ─────────────────────────────────────────────────

@click.group()
@click.version_option("1.0.0", prog_name="bangla-synonyms")
def main() -> None:
    """🇧🇩 Bangla synonym lookup — offline dataset + live Wiktionary."""


# ── get ───────────────────────────────────────────────────────

@main.command("get")
@click.argument("words", nargs=-1, required=True)
@click.option("--offline", is_flag=True, help="Local dataset only, no internet")
@click.option(
    "--delay", "-d", default=1.0, show_default=True,
    help="Seconds between requests",
)
def get_cmd(words: tuple[str, ...], offline: bool, delay: float) -> None:
    """
    Look up synonyms for one or more words.

    \b
    Examples:
        bangla-synonyms get চোখ
        bangla-synonyms get চোখ মা সুন্দর
        bangla-synonyms get চোখ --offline
    """
    get(list(words), offline=offline)


# ── build ─────────────────────────────────────────────────────

@main.command("build")
@click.option(
    "--limit", "-l", default=200, show_default=True,
    help="Number of words to scrape",
)
@click.option(
    "--delay", "-d", default=1.0, show_default=True,
    help="Delay between requests (seconds)",
)
def build_cmd(limit: int, delay: float) -> None:
    """
    Scrape Wiktionary and build / expand the local dataset.

    \b
    Examples:
        bangla-synonyms build
        bangla-synonyms build --limit 500
        bangla-synonyms build --delay 2.0
    """
    build(limit=limit, delay=delay)


# ── stats ─────────────────────────────────────────────────────

@main.command("stats")
def stats_cmd() -> None:
    """Show local dataset statistics."""
    stats()


# ── export ────────────────────────────────────────────────────

@main.command("export")
@click.argument("output")
@click.option(
    "--format", "-f", "fmt", default="json", show_default=True,
    type=click.Choice(["json", "csv"]),
    help="Output format",
)
def export_cmd(output: str, fmt: str) -> None:
    """
    Export the local dataset to a file.

    \b
    Examples:
        bangla-synonyms export synonyms.json
        bangla-synonyms export synonyms.csv --format csv
    """
    DatasetManager().export(output, fmt=fmt)


# ── download ──────────────────────────────────────────────────

@main.command("download")
@click.option("--url", default=None, help="Custom download URL")
@click.option("--force", is_flag=True, help="Re-download even if dataset exists")
def download_cmd(url: str | None, force: bool) -> None:
    """
    Download the full community dataset (~10 000 words) from GitHub Releases.

    \b
    Examples:
        bangla-synonyms download
        bangla-synonyms download --force
    """
    DatasetManager().download(url=url, force=force)


# ── entry-point ───────────────────────────────────────────────

if __name__ == "__main__":
    main()
