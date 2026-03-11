"""Tests for Scrapper (offline mode — no network)."""
from unittest.mock import patch, MagicMock
from bangla_synonyms import Scrapper


def test_offline_returns_empty_for_unknown():
    sc = Scrapper(offline=True)
    assert sc.get("xyz_not_in_dataset") == []


def test_get_many_returns_dict():
    sc = Scrapper(offline=True)
    result = sc.get_many(["চোখ", "মা"])
    assert isinstance(result, dict)
    assert set(result.keys()) == {"চোখ", "মা"}


def test_auto_save_false_does_not_persist(tmp_path, monkeypatch):
    monkeypatch.setattr("bangla_synonyms.core._USER_FILE", tmp_path / "ds.json")
    mock_session = MagicMock()
    with patch("bangla_synonyms._scrapper.fetch_synonyms", return_value=["চক্ষু"]):
        with patch("bangla_synonyms._scrapper.make_session", return_value=mock_session):
            sc = Scrapper(offline=False, auto_save=False)
            result = sc.get("চোখ")
    assert result == ["চক্ষু"]
    assert not (tmp_path / "ds.json").exists()
