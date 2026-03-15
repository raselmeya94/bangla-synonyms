"""
tests/test_wordlist_fetcher.py
-------------------------------
Tests for WordlistFetcher — fetch, filter_new, save, load.
Network tests are marked and skipped by default.

Based on: wordlist_fetcher_api_text.py
"""
import pytest

from bangla_synonyms.core import DatasetManager, WordlistFetcher


@pytest.fixture
def wf():
    return WordlistFetcher()


@pytest.fixture
def dm():
    return DatasetManager()


# ── Offline / no-network tests ─────────────────────────────────────────────


class TestWordlistFetcherOffline:
    def test_filter_new_removes_known_words(self, wf, dm):
        """Words already in the dataset should be filtered out."""
        known = list(dm.all_words())
        new = wf.filter_new(known, dm)
        assert new == []

    def test_filter_new_keeps_unknown_words(self, wf, dm):
        words = ["xyznotaword1", "xyznotaword2"]
        filtered = wf.filter_new(words, dm)
        assert filtered == words

    def test_filter_new_mixed(self, wf, dm):
        known = dm.all_words()[:2]
        unknown = ["xyznotaword"]
        result = wf.filter_new(list(known) + unknown, dm)
        assert unknown[0] in result
        for w in known:
            assert w not in result

    def test_save_and_load(self, wf, tmp_path):
        words = ["চোখ", "মা", "নদী", "আকাশ"]
        path = str(tmp_path / "wordlist.txt")
        wf.save(words, path)
        reloaded = wf.load(path)
        assert reloaded == words

    def test_save_load_preserves_order(self, wf, tmp_path):
        words = ["ঘ", "ক", "চ", "খ"]
        path = str(tmp_path / "ordered.txt")
        wf.save(words, path)
        assert wf.load(path) == words

    def test_load_nonexistent_raises(self, wf):
        with pytest.raises(OSError):
            wf.load("nonexistent_wordlist.txt")


# ── Network tests — skipped by default ────────────────────────────────────


@pytest.mark.slow
@pytest.mark.network
class TestWordlistFetcherOnline:
    """
    Live Wiktionary API calls.
    Run with: pytest -m network
    """

    def test_fetch_returns_list(self, wf):
        words = wf.fetch(limit=10)
        assert isinstance(words, list)

    def test_fetch_respects_limit(self, wf):
        words = wf.fetch(limit=20)
        assert len(words) <= 20

    def test_fetch_small_limit(self, wf):
        words = wf.fetch(limit=5)
        assert len(words) <= 5

    def test_fetch_words_are_strings(self, wf):
        words = wf.fetch(limit=10)
        for w in words:
            assert isinstance(w, str)

    def test_fetch_no_multiword_titles(self, wf):
        """Multi-word titles like 'অ আ ক খ' must be filtered out."""
        words = wf.fetch(limit=50)
        for w in words:
            assert " " not in w, f"Multi-word title found: '{w}'"

    def test_fetch_100_words(self, wf):
        words = wf.fetch(limit=100)
        assert isinstance(words, list)
        assert len(words) <= 100

    def test_filter_new_after_fetch(self, wf, dm):
        words = wf.fetch(limit=20)
        new_words = wf.filter_new(words, dm)
        assert isinstance(new_words, list)
        assert len(new_words) <= len(words)

    def test_save_reload_after_fetch(self, wf, tmp_path):
        words = wf.fetch(limit=10)
        path = str(tmp_path / "fetched.txt")
        wf.save(words, path)
        reloaded = wf.load(path)
        assert reloaded == words
