"""
tests/test_scrapper.py
-----------------------
Tests for the Scrapper class — offline and online modes,
all constructor variations, get(), get_many(), active_sources.

Based on: scrapper_api_test_[offline].py
          scrapper_api_test_[online].py
"""
import pytest
from bangla_synonyms import Scrapper


# ── Offline mode ───────────────────────────────────────────────────────────

class TestScrapperOffline:
    """Scrapper(offline=True) — no network calls, local dataset only."""

    def test_default_offline_returns_list(self):
        sc = Scrapper(offline=True)
        result = sc.get("সুন্দর")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_offline_unknown_word_returns_empty(self):
        sc = Scrapper(offline=True)
        assert sc.get("xyznotaword") == []

    def test_offline_autosave_no_effect(self):
        """auto_save=True offline should not crash."""
        sc = Scrapper(offline=True, auto_save=True)
        result = sc.get("সুন্দর")
        assert isinstance(result, list)

    def test_offline_custom_delay(self):
        sc = Scrapper(offline=True, delay=2)
        result = sc.get("সুন্দর")
        assert isinstance(result, list)

    def test_offline_custom_timeout(self):
        sc = Scrapper(offline=True, timeout=20)
        result = sc.get("সুন্দর")
        assert isinstance(result, list)

    def test_offline_full_custom(self):
        sc = Scrapper(offline=True, auto_save=True, delay=2, timeout=20, merge=True)
        result = sc.get("সুন্দর")
        assert isinstance(result, list)

    def test_offline_raw_structure(self):
        sc = Scrapper(offline=True)
        result = sc.get("সুন্দর", raw=True)
        assert isinstance(result, dict)
        assert result["word"] == "সুন্দর"
        assert result["quality"] == "local"
        assert result["source"] == "local"
        assert "local" in result["sources_results"]

    def test_offline_raw_unknown_word(self):
        sc = Scrapper(offline=True)
        result = sc.get("xyznotaword", raw=True)
        assert result["quality"] == "empty"
        assert result["words"] == []

    def test_offline_get_many(self):
        sc = Scrapper(offline=True)
        words = ["সুন্দর", "বড়", "ভাল"]
        result = sc.get_many(words)
        assert set(result.keys()) == set(words)
        for word in words:
            assert isinstance(result[word], list)

    def test_offline_active_sources_default(self):
        sc = Scrapper(offline=True)
        assert sc.active_sources == ["wiktionary", "shabdkosh", "english_bangla"]

    def test_offline_active_sources_custom(self):
        sc = Scrapper(offline=True, sources=["wiktionary"])
        assert sc.active_sources == ["wiktionary"]

    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="Unknown source"):
            Scrapper(sources=["not_a_source"])

    def test_repr_offline(self):
        sc = Scrapper(offline=True)
        assert "offline" in repr(sc)

    def test_repr_online(self):
        sc = Scrapper()
        assert "online" in repr(sc)


# ── Online mode — marked slow, skipped by default ─────────────────────────

@pytest.mark.slow
@pytest.mark.network
class TestScrapperOnline:
    """
    Scrapper() — live web scraping fallback.
    Run with: pytest -m network
    """

    def test_default_online(self):
        sc = Scrapper()
        result = sc.get("নদী")
        assert isinstance(result, list)

    def test_autosave(self):
        sc = Scrapper(auto_save=True)
        result = sc.get("নদী")
        assert isinstance(result, list)

    def test_custom_delay(self):
        sc = Scrapper(delay=2)
        result = sc.get("নদী")
        assert isinstance(result, list)

    def test_two_sources(self):
        sc = Scrapper(sources=["wiktionary", "shabdkosh"])
        result = sc.get("নদী")
        assert isinstance(result, list)

    def test_no_merge(self):
        sc = Scrapper(merge=False)
        result = sc.get("নদী")
        assert isinstance(result, list)

    def test_full_custom(self):
        sc = Scrapper(
            auto_save=True, delay=2, timeout=20,
            sources=["wiktionary", "shabdkosh"], merge=True,
        )
        result = sc.get("নদী")
        assert isinstance(result, list)

    def test_raw_online_structure(self):
        sc = Scrapper(sources=["wiktionary", "shabdkosh"])
        result = sc.get("নদী", raw=True)
        assert isinstance(result, dict)
        assert result["word"] == "নদী"
        assert "sources_results" in result
        assert result["quality"] in ("wikiconfirmed", "cross_source", "single_source", "empty")

    def test_raw_confirmed_flag(self):
        sc = Scrapper(sources=["wiktionary", "shabdkosh"])
        result = sc.get("নদী", raw=True)
        for entry in result.get("results", []):
            assert "synonym" in entry
            assert "source" in entry

    def test_get_many_online(self):
        sc = Scrapper(sources=["wiktionary", "shabdkosh"])
        words = ["নদী", "আকাশ"]
        result = sc.get_many(words)
        assert set(result.keys()) == set(words)

    def test_get_many_raw_online(self):
        sc = Scrapper(sources=["wiktionary", "shabdkosh"])
        result = sc.get_many(["নদী"], raw=True)
        assert "quality" in result["নদী"]
