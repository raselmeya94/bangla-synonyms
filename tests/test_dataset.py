"""Tests for DatasetManager."""
import json
import pytest
from bangla_synonyms.core import DatasetManager


def test_add_and_get(tmp_path, monkeypatch):
    monkeypatch.setattr("bangla_synonyms.core._USER_FILE", tmp_path / "ds.json")
    dm = DatasetManager()
    dm.add("চোখ", ["চক্ষু", "নেত্র"])
    assert dm.get("চোখ") == ["চক্ষু", "নেত্র"]


def test_add_merges_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr("bangla_synonyms.core._USER_FILE", tmp_path / "ds.json")
    dm = DatasetManager()
    dm.add("চোখ", ["চক্ষু"])
    dm.add("চোখ", ["চক্ষু", "নেত্র"])
    assert dm.get("চোখ") == ["চক্ষু", "নেত্র"]


def test_remove(tmp_path, monkeypatch):
    monkeypatch.setattr("bangla_synonyms.core._USER_FILE", tmp_path / "ds.json")
    dm = DatasetManager()
    dm.add("চোখ", ["চক্ষু"])
    assert dm.remove("চোখ") is True
    assert dm.get("চোখ") == []


def test_export_json(tmp_path, monkeypatch):
    monkeypatch.setattr("bangla_synonyms.core._USER_FILE", tmp_path / "ds.json")
    dm = DatasetManager()
    dm.add("চোখ", ["চক্ষু"])
    out = tmp_path / "out.json"
    dm.export(str(out))
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "চোখ" in data


def test_merge(tmp_path, monkeypatch):
    monkeypatch.setattr("bangla_synonyms.core._USER_FILE", tmp_path / "ds.json")
    extra = tmp_path / "extra.json"
    extra.write_text(json.dumps({"মা": ["জননী", "মাতা"]}), encoding="utf-8")
    dm = DatasetManager()
    added = dm.merge(str(extra))
    assert added == 1
    assert dm.get("মা") == ["জননী", "মাতা"]
