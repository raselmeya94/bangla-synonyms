"""Tests for CLI helpers."""
from bangla_synonyms.cli import get, stats


def test_get_offline_returns_dict():
    result = get(["xyz_unknown"], offline=True)
    assert isinstance(result, dict)
    assert "xyz_unknown" in result


def test_stats_returns_dict():
    result = stats()
    assert "total_words" in result
