# Contributing to bangla-synonyms

Bengali is spoken by 230 million people but remains one of the most underserved
languages in NLP. Every contribution to this project — whether a one-line bug
fix or a new scraping source — directly improves the tools available to the
entire Bangla NLP community.

We're glad you're here.

---

## Architecture

```
bangla_synonyms/
│
├── __init__.py             top-level API: download(), get(), get_many(), stats()
│                           public exports: Scrapper
│                           _default = Scrapper()  ← shared singleton
│
├── _scrapper.py            Scrapper class — lookup, source selection, raw mode,
│                           download classmethod, dataset helpers
├── cli.py                  Click-based CLI and importable helpers
│
└── core/
    ├── __init__.py         DatasetManager, BatchScraper, WordlistFetcher
    │                       fetch_with_sources(), fetch_with_sources_raw()
    │                       SOURCES registry, DEFAULT_SOURCES
    │
    ├── _quality.py         Quality filtering pipeline — noise removal,
    │                       cross-source validation, source-tier logic
    ├── _wikitext.py        bn.wiktionary.org scraper (wikitext API + HTML fallback)
    ├── _shabdkosh.py       shabdkosh.com scraper
    ├── _english_bangla.py  english-bangla.com scraper
    └── _embedding.py       BNLP word vectors — opt-in, offline after download
```

### Lookup flow

```
bs.get("চোখ")  /  sc.get("চোখ")
    │
    ▼
Check local dataset  (no network call)
    │
    ├── Found ──────────────────────────► return list / raw dict  (quality: "local")
    │
    └── Not found
            │
            ▼
        offline=True? ──► return []
            │
            ▼
        Scrape sources in order
            │
            ├── wiktionary      fetch → collect results
            ├── shabdkosh       fetch → merge results        (merge=True)
            └── english_bangla  fetch → merge results        (merge=True)
            │
            │   merge=False: stop at the first source that returns results
            │
            ▼
        Quality pipeline  (noise filter → cross-source validation)
            │
            ▼
        auto_save=True? → write to local dataset
            │
            ▼
        return list / raw dict
```

### Quality pipeline

```
Raw scraper output
    │
    ├── Noise filter
    │     drops: phrases, hyphenated entries, numbered items,
    │            entries with digits / Latin chars / zero-width chars
    │
    └── Cross-source validation
          │
          Wiktionary present?
          │
          YES → "wikiconfirmed"
          │       keep: all Wiktionary entries  (authoritative)
          │       keep: Shabdkosh entries confirmed by Wiktionary
          │       keep: English-Bangla entries confirmed by ≥1 other source
          │
          NO  → check cross-source agreement
                  ≥2 sources agree → "cross_source"
                  single source    → "single_source"  (cleaned only)
```

---

## How this project works

```
User calls bs.get("চোখ")
    │
    ├── checks local dataset first  (dataset.json)
    │
    └── not found → scrapes sources in order
            │
            ├── Wiktionary   (most reliable)
            ├── Shabdkosh    (good coverage)
            └── English-Bangla (last resort)
            │
            └── quality pipeline (noise filter + cross-source validation)
                    │
                    └── returns clean synonym list
```

The codebase is intentionally small and modular. Each scraping source is an
independent file in `core/`. The quality pipeline lives entirely in
`core/_quality.py`. New sources or improvements can be made without touching
anything else.

---

## Ways to contribute

### Report a bug

Open an issue with the label **`bug`**. Include:

- The word you looked up
- What you got vs what you expected
- Which source returned the wrong result (`raw=True` output helps)

### Suggest a feature

Open an issue with the label **`feature`**. Describe what you want and why it
would be useful. Good examples: new scraping source, CLI flag, export format.

### Improve quality

Open an issue with the label **`improve`**. The quality pipeline
(`core/_quality.py`) is the highest-impact area — better noise filtering and
smarter cross-source validation directly affects every result.

### Add a new source

Any Bangla dictionary or thesaurus with a stable URL can become a source.
Use `core/_shabdkosh.py` as a reference. The contract is simple:

```python
def fetch_mysource(word: str, session, timeout: int = 10) -> list | None:
    # return list[str] of synonyms, [] if not found, None on network error
```

Register it in `core/__init__.py`:

```python
from ._mysource import fetch_mysource as _fetch_mysource
SOURCES["mysource"] = _fetch_mysource
```

### Expand the dataset

If you have a curated list of Bangla synonyms, contribute it as a JSON file
or use `DatasetManager.merge("your_file.json")` to add it locally and share
the file via PR.

---

## Development workflow

**1. Fork and set up**

```bash
git clone https://github.com/your-username/bangla-synonyms.git
cd bangla-synonyms
pip install -e ".[dev]"
```

**2. Always open an issue first**
Describe what you plan to do. This avoids duplicate work and lets us agree
on the approach before you write any code.

**3. Create a branch from `main`**

Use a prefix that matches your work:

```bash
git checkout -b feature/embedding-source    # new feature
git checkout -b fix/shabdkosh-parser        # bug fix
git checkout -b improve/quality-pipeline    # improvement to existing code
```

**4. Make your changes and run tests**

```bash
# offline tests only (fast, no network)
pytest

# include live scraping tests
pytest -m network
```

**5. Open a pull request**

- Base branch: `main`
- Title: short description of what changed (`fix: shabdkosh timeout handling`)
- Link the issue: `Closes #123`
- Include before/after output examples for quality changes

---

## Future directions

These areas are open for contribution. Open an issue with the relevant label
before starting.

| Area                                                                 | Notes                                         | Branch                            |
| -------------------------------------------------------------------- | --------------------------------------------- | --------------------------------- |
| **Embedding source** — Word2Vec / FastText / GloVe cosine similarity | Opt-in; model download required               | `feature/embedding-source`        |
| **BanglaBERT contextual scoring** — sense-aware synonym ranking      | Ranks candidates by fit in context            | `feature/bert-contextual-scoring` |
| **Morphological variants** — inflected forms map to same root        | "সুন্দর" / "সুন্দরভাবে" → same synonyms       | `improve/morphological-variants`  |
| **Evaluation dataset** — gold-standard synonym lists for ~500 words  | Enables regression testing on quality changes | `improve/evaluation-dataset`      |
| **Quality feedback** — `bs.flag(word, synonym, reason)`              | Community-driven dataset improvement          | `feature/quality-feedback`        |

---

## Community

Bangla NLP deserves the same quality tooling that English takes for granted.
Every word added, every bug fixed, and every source scraped makes that a
little more true.

If you use this library in a project, we'd love to hear about it — open a
discussion or add it to the README's _Used by_ section.
