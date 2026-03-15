"""
tests/test_top_level_api.py
----------------------------
Tests for the top-level bs.get() and bs.get_many() API.
Covers both offline (local dataset) and online (live scrape) paths.

Based on: top_level_api_test_[offline].py
          top_level_api_test_[online].py
"""
import pytest
import bangla_synonyms as bs


# ── Offline tests (local dataset only) ────────────────────────────────────

class TestTopLevelOffline:
    """bs.get() and bs.get_many() served from local dataset."""

    def test_get_single_word_returns_list(self):
        result = bs.get("সুন্দর")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_single_word_known_synonyms(self):
        result = bs.get("সুন্দর")
        assert "মনোরম" in result or "চমৎকার" in result

    def test_get_unknown_word_returns_empty(self):
        result = bs.get("xyznotaword")
        assert result == []

    def test_get_raw_structure(self):
        result = bs.get("সুন্দর", raw=True)
        assert isinstance(result, dict)
        assert result["word"] == "সুন্দর"
        assert "words" in result
        assert "results" in result
        assert "sources_hit" in result
        assert "sources_tried" in result
        assert "quality" in result
        assert "source" in result
        assert "sources_results" in result

    def test_get_raw_local_quality(self):
        result = bs.get("সুন্দর", raw=True)
        assert result["quality"] == "local"
        assert result["source"] == "local"
        assert result["sources_hit"] == ["local"]

    def test_get_raw_sources_results_populated(self):
        """sources_results should have 'local' key, not be empty."""
        result = bs.get("সুন্দর", raw=True)
        assert "local" in result["sources_results"]
        assert len(result["sources_results"]["local"]) > 0

    def test_get_raw_results_entries(self):
        result = bs.get("সুন্দর", raw=True)
        for entry in result["results"]:
            assert "synonym" in entry
            assert "source" in entry
            assert entry["source"] == "local"

    def test_get_many_returns_dict(self):
        words = ["সুন্দর", "বড়", "ভাল"]
        result = bs.get_many(words)
        assert isinstance(result, dict)
        assert set(result.keys()) == set(words)

    def test_get_many_all_words_have_results(self):
        words = ["সুন্দর", "বড়", "চোখ"]
        result = bs.get_many(words)
        for word in words:
            assert isinstance(result[word], list)
            assert len(result[word]) > 0

    def test_get_many_unknown_word_returns_empty(self):
        result = bs.get_many(["সুন্দর", "xyznotaword"])
        assert result["xyznotaword"] == []

    def test_get_many_raw_structure(self):
        words = ["সুন্দর", "বড়"]
        result = bs.get_many(words, raw=True)
        assert isinstance(result, dict)
        for word in words:
            assert "word" in result[word]
            assert "words" in result[word]
            assert "quality" in result[word]

    def test_get_many_sources_filter(self):
        """sources param is accepted without error even in offline hit."""
        result = bs.get_many(["সুন্দর"], sources=["wiktionary", "shabdkosh"])
        assert isinstance(result["সুন্দর"], list)

    def test_stats_returns_dict(self):
        info = bs.stats()
        assert isinstance(info, dict)
        assert "total_words" in info
        assert "total_synonyms" in info
        assert "avg_per_word" in info
        assert info["total_words"] > 0


# ── Online tests (live scraping) — marked slow, skipped by default ────────

@pytest.mark.slow
@pytest.mark.network
class TestTopLevelOnline:
    """
    bs.get() falling back to live web scraping.
    Run with: pytest -m network
    """

    def test_get_online_returns_list(self):
        result = bs.get("তটিনী")
        assert isinstance(result, list)

    def test_get_online_sources_wiktionary_only(self):
        result = bs.get("নদী", sources=["wiktionary"])
        assert isinstance(result, list)

    def test_get_online_sources_two(self):
        result = bs.get("নদী", sources=["wiktionary", "shabdkosh"])
        assert isinstance(result, list)

    def test_get_online_raw_structure(self):
        result = bs.get("নদী", sources=["wiktionary", "shabdkosh"], raw=True)
        assert isinstance(result, dict)
        assert result["word"] == "নদী"
        assert result["quality"] in ("wikiconfirmed", "cross_source", "single_source", "empty")
        assert "sources_results" in result

    def test_get_many_online(self):
        words = ["নদী", "আকাশ"]
        result = bs.get_many(words, sources=["wiktionary"])
        assert set(result.keys()) == set(words)
        for word in words:
            assert isinstance(result[word], list)

    def test_get_many_online_raw(self):
        words = ["নদী", "আকাশ"]
        result = bs.get_many(words, sources=["wiktionary", "shabdkosh"], raw=True)
        for word in words:
            assert "quality" in result[word]
            assert "sources_results" in result[word]
