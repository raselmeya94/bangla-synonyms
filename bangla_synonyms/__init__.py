"""
bangla-synonyms
================
Bangla synonym lookup — offline dataset + live Wiktionary scraping.

─────────────────────────────────────────────────────────
BASIC USE  (BanglaSynonyms):
─────────────────────────────────────────────────────────
    from bangla_synonyms import BanglaSynonyms

    bn = BanglaSynonyms()
    bn.get("চোখ")                     # → ['চক্ষু', 'নেত্র', 'লোচন', ...]
    bn.get("সুন্দর")                   # → ['মনোরম', 'চমৎকার', ...]
    bn.get_many(["চোখ", "মা"])         # → {'চোখ': [...], 'মা': [...]}
    bn.add("পরিবেশ", ["প্রকৃতি"])       # manually add
    bn.stats()                         # dataset info
    bn.export("synonyms.json")

─────────────────────────────────────────────────────────
SCRAPER WITH CONTROL  (Scrapper):
─────────────────────────────────────────────────────────
    from bangla_synonyms import Scrapper

    sc = Scrapper()                              # online, auto-save, delay=1s
    sc = Scrapper(offline=True)                  # local dataset only
    sc = Scrapper(auto_save=False, delay=2.0)    # scrape but don't save

    sc.get("চোখ")
    sc.get_many(["চোখ", "মা", "নদী"])

─────────────────────────────────────────────────────────
ADVANCED  (bangla_synonyms.core):
─────────────────────────────────────────────────────────
    from bangla_synonyms.core import DatasetManager, WordlistFetcher, BatchScraper

    dm = DatasetManager()
    dm.stats()
    dm.merge("extra.json")
    dm.export("output.csv", fmt="csv")

    wf    = WordlistFetcher()
    words = wf.fetch(limit=500)

    bs     = BatchScraper(delay=1.0)
    result = bs.run(words)

─────────────────────────────────────────────────────────
CLI:
─────────────────────────────────────────────────────────
    bangla-synonyms get চোখ
    bangla-synonyms get চোখ মা সুন্দর
    bangla-synonyms build --limit 200
    bangla-synonyms stats
    bangla-synonyms export out.json
"""

from .synonyms import BanglaSynonyms
from ._scrapper import Scrapper

__version__ = "1.0.0"
__all__     = ["BanglaSynonyms", "Scrapper"]
