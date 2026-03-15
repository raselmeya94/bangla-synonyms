"""
tests/conftest.py
-----------------
Shared fixtures for all test modules.
"""
import json
import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def dataset_dir(tmp_path_factory):
    """Create a temporary dataset directory with a small dataset."""
    d = tmp_path_factory.mktemp("bangla_synonyms_data")
    dataset = {
        "সুন্দর": ["মনোরম", "চমৎকার", "অপূর্ব", "মনোহর", "রমণীয়", "খুবসুরত"],
        "বড়":    ["বিশাল", "বৃহৎ", "বিরাট", "মহান", "বৃহদাকার"],
        "ভাল":   ["ভালো", "উত্তম", "শ্রেয়"],
        "চোখ":   ["চক্ষু", "নেত্র", "লোচন", "আঁখি"],
        "মা":    ["জননী", "আম্মা", "জন্মদাত্রী", "মাতা"],
    }
    (d / "dataset.json").write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return d


@pytest.fixture(autouse=True)
def patch_dataset_path(dataset_dir, monkeypatch):
    """
    Redirect all DatasetManager disk I/O to the temp directory.
    Applied automatically to every test.
    """
    import bangla_synonyms.core as core
    monkeypatch.chdir(dataset_dir.parent)
    # Reload so _SHARED picks up the temp dataset
    core._SHARED = None
