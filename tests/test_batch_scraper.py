"""
tests/test_batch_scraper.py
----------------------------
Tests for BatchScraper — all six usage patterns.
Network tests are marked and skipped by default.

Based on: batchscrapper_api_test.py
"""
import pytest

from bangla_synonyms.core import BatchScraper, DatasetManager


@pytest.fixture
def dm():
    return DatasetManager()


# ── Offline / structural tests ─────────────────────────────────────────────


class TestBatchScraperOffline:
    def test_run_skips_existing_words(self, dm):
        """Words already in the dataset must be skipped."""
        known = list(dm.all_words())
        scraper = BatchScraper(dataset=dm, sources=["wiktionary"])
        result = scraper.run(known, skip_existing=True, show_progress=False)
        assert result == {}

    def test_run_returns_dict(self, dm):
        scraper = BatchScraper(dataset=dm, sources=["wiktionary"])
        result = scraper.run([], show_progress=False)
        assert isinstance(result, dict)

    def test_run_empty_word_list(self, dm):
        scraper = BatchScraper(dataset=dm)
        result = scraper.run([], show_progress=False)
        assert result == {}

    def test_constructor_defaults(self, dm):
        scraper = BatchScraper(dataset=dm)
        assert scraper.delay == 1.0
        assert scraper.timeout == 10
        assert scraper.save_every == 50
        assert scraper.merge is True
        assert scraper.sources is None

    def test_constructor_custom(self, dm):
        scraper = BatchScraper(
            dataset=dm,
            delay=2.0,
            timeout=20,
            save_every=5,
            sources=["wiktionary"],
            merge=False,
        )
        assert scraper.delay == 2.0
        assert scraper.timeout == 20
        assert scraper.save_every == 5
        assert scraper.sources == ["wiktionary"]
        assert scraper.merge is False


# ── Network tests — skipped by default ────────────────────────────────────


@pytest.mark.slow
@pytest.mark.network
class TestBatchScraperOnline:
    """
    Live scraping with all six BatchScraper patterns.
    Run with: pytest -m network
    """

    WORDS = ["তটিনী", "গগন", "বারি"]  # words unlikely to be in local dataset

    def test_all_sources_merge_true(self, dm):
        """Demo 1 — default, all sources, merge=True."""
        scraper = BatchScraper(
            dataset=dm,
            delay=1.0,
            timeout=10,
            save_every=10,
            sources=None,
            merge=True,
        )
        result = scraper.run(self.WORDS[:2], skip_existing=True, show_progress=False)
        assert isinstance(result, dict)

    def test_wiktionary_only(self, dm):
        """Demo 2 — Wiktionary only, best quality."""
        scraper = BatchScraper(
            dataset=dm, delay=1.0, sources=["wiktionary"], merge=True
        )
        result = scraper.run(self.WORDS[:2], skip_existing=True, show_progress=False)
        assert isinstance(result, dict)

    def test_two_sources(self, dm):
        """Demo 3 — Wiktionary + Shabdkosh."""
        scraper = BatchScraper(
            dataset=dm,
            delay=1.0,
            sources=["wiktionary", "shabdkosh"],
            merge=True,
        )
        result = scraper.run(self.WORDS[:2], skip_existing=True, show_progress=False)
        assert isinstance(result, dict)

    def test_merge_false(self, dm):
        """Demo 4 — stop at first source with results."""
        scraper = BatchScraper(dataset=dm, delay=0.5, sources=None, merge=False)
        result = scraper.run(self.WORDS[:2], skip_existing=True, show_progress=False)
        assert isinstance(result, dict)

    def test_save_every_one(self, dm):
        """Demo 5 — checkpoint after every word."""
        scraper = BatchScraper(
            dataset=dm,
            delay=1.0,
            save_every=1,
            sources=["wiktionary"],
            merge=True,
        )
        result = scraper.run(self.WORDS[:1], skip_existing=True, show_progress=False)
        assert isinstance(result, dict)

    def test_run_from_wiktionary(self, dm):
        """Demo 6 — one-step fetch + scrape."""
        scraper = BatchScraper(
            dataset=dm,
            delay=1.0,
            sources=["wiktionary", "shabdkosh"],
            merge=True,
        )
        result = scraper.run_from_wiktionary(limit=5)
        assert isinstance(result, dict)

    def test_skip_existing_true(self, dm):
        """Running twice on the same words — second run returns empty."""
        scraper = BatchScraper(dataset=dm, delay=1.0, sources=["wiktionary"])
        scraper.run(self.WORDS[:1], skip_existing=False, show_progress=False)
        result2 = scraper.run(self.WORDS[:1], skip_existing=True, show_progress=False)
        assert result2 == {}

    def test_sources_override_per_run(self, dm):
        """sources param on run() overrides instance sources."""
        scraper = BatchScraper(dataset=dm, delay=1.0, sources=["shabdkosh"])
        result = scraper.run(
            self.WORDS[:1],
            sources=["wiktionary"],
            skip_existing=True,
            show_progress=False,
        )
        assert isinstance(result, dict)

    def test_result_values_are_lists(self, dm):
        scraper = BatchScraper(dataset=dm, delay=1.0, sources=["wiktionary"])
        result = scraper.run(self.WORDS, skip_existing=True, show_progress=False)
        for synonyms in result.values():
            assert isinstance(synonyms, list)
