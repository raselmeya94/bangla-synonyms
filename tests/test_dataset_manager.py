"""
tests/test_dataset_manager.py
------------------------------
Tests for DatasetManager — read, write, merge, export, stats.

Based on: data_manager_api_test.py
"""
import json
import pytest
from bangla_synonyms.core import DatasetManager


@pytest.fixture
def dm():
    return DatasetManager()


@pytest.fixture
def extra_json(tmp_path):
    """Create a small extra.json file for merge tests."""
    data = {
        "ছোট":  ["ক্ষুদ্র", "নগণ্য", "অল্প"],
        "দ্রুত": ["ত্বরিত", "দ্রুতগামী", "বেগবান"],
    }
    p = tmp_path / "extra.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)


# ── Stats ──────────────────────────────────────────────────────────────────

class TestStats:
    def test_stats_returns_dict(self, dm):
        info = dm.stats()
        assert isinstance(info, dict)

    def test_stats_keys(self, dm):
        info = dm.stats()
        assert "total_words" in info
        assert "total_synonyms" in info
        assert "avg_per_word" in info
        assert "source" in info

    def test_stats_total_words_positive(self, dm):
        assert dm.stats()["total_words"] > 0


# ── Read ───────────────────────────────────────────────────────────────────

class TestRead:
    def test_get_known_word(self, dm):
        result = dm.get("সুন্দর")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_unknown_word_returns_empty(self, dm):
        assert dm.get("xyznotaword") == []

    def test_has_known_word(self, dm):
        assert dm.has("সুন্দর") is True

    def test_has_unknown_word(self, dm):
        assert dm.has("xyznotaword") is False

    def test_contains_operator(self, dm):
        assert "সুন্দর" in dm
        assert "xyznotaword" not in dm

    def test_len(self, dm):
        assert len(dm) > 0

    def test_all_words_sorted(self, dm):
        words = dm.all_words()
        assert isinstance(words, list)
        assert words == sorted(words)

    def test_get_returns_copy(self, dm):
        """Mutating the returned list must not affect the dataset."""
        result = dm.get("সুন্দর")
        original_len = len(result)
        result.append("fake_entry")
        assert len(dm.get("সুন্দর")) == original_len


# ── Write ──────────────────────────────────────────────────────────────────

class TestWrite:
    def test_add_new_word(self, dm):
        dm.add("শব্দ", ["প্রতিশব্দ১", "প্রতিশব্দ২"])
        assert dm.has("শব্দ")
        assert "প্রতিশব্দ১" in dm.get("শব্দ")

    def test_add_merges_with_existing(self, dm):
        dm.add("সুন্দর", ["নতুনশব্দ"])
        assert "নতুনশব্দ" in dm.get("সুন্দর")
        assert "মনোরম" in dm.get("সুন্দর")

    def test_add_ignores_duplicates(self, dm):
        before = len(dm.get("সুন্দর"))
        dm.add("সুন্দর", ["মনোরম"])   # already exists
        assert len(dm.get("সুন্দর")) == before

    def test_add_ignores_self_synonym(self, dm):
        dm.add("সুন্দর", ["সুন্দর"])
        assert dm.get("সুন্দর").count("সুন্দর") == 0

    def test_update_replaces_list(self, dm):
        dm.update("সুন্দর", ["নতুন১", "নতুন২"])
        result = dm.get("সুন্দর")
        assert result == ["নতুন১", "নতুন২"]

    def test_remove_existing_word(self, dm):
        dm.add("টেস্টশব্দ", ["ক", "খ"])
        removed = dm.remove("টেস্টশব্দ")
        assert removed is True
        assert not dm.has("টেস্টশব্দ")

    def test_remove_nonexistent_word(self, dm):
        removed = dm.remove("xyznotaword")
        assert removed is False

    def test_add_save_false_does_not_crash(self, dm):
        dm.add("ক", ["খ", "গ"], save=False)
        dm.add("ঘ", ["ঙ"],      save=False)
        assert dm.has("ক")
        assert dm.has("ঘ")


# ── Merge ──────────────────────────────────────────────────────────────────

class TestMerge:
    def test_merge_adds_new_words(self, dm, extra_json):
        before = len(dm)
        added = dm.merge(extra_json)
        assert added == 2
        assert len(dm) == before + 2

    def test_merge_new_words_content(self, dm, extra_json):
        dm.merge(extra_json)
        assert "ক্ষুদ্র" in dm.get("ছোট")
        assert "ত্বরিত" in dm.get("দ্রুত")

    def test_merge_existing_word_appends(self, dm, extra_json, tmp_path):
        """Merging a word that already exists appends new synonyms."""
        overlap = {"সুন্দর": ["নতুনমার্জ"]}
        p = tmp_path / "overlap.json"
        p.write_text(json.dumps(overlap, ensure_ascii=False), encoding="utf-8")
        dm.merge(str(p))
        assert "নতুনমার্জ" in dm.get("সুন্দর")

    def test_merge_invalid_file_raises(self, dm):
        with pytest.raises(ValueError):
            dm.merge("nonexistent_file.json")


# ── Export ─────────────────────────────────────────────────────────────────

class TestExport:
    def test_export_json(self, dm, tmp_path):
        out = tmp_path / "output.json"
        dm.export(str(out))
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "সুন্দর" in data

    def test_export_csv(self, dm, tmp_path):
        out = tmp_path / "output.csv"
        dm.export(str(out), fmt="csv")
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "word,synonyms,count" in content
        assert "সুন্দর" in content

    def test_export_invalid_format_raises(self, dm, tmp_path):
        with pytest.raises(ValueError, match="Unknown format"):
            dm.export(str(tmp_path / "out.txt"), fmt="txt")

    def test_export_json_sorted(self, dm, tmp_path):
        out = tmp_path / "sorted.json"
        dm.export(str(out))
        data = json.loads(out.read_text(encoding="utf-8"))
        keys = list(data.keys())
        assert keys == sorted(keys)
