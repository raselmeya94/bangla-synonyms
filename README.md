# bangla-synonyms

<p align="center">
  <strong>Bangla synonym lookup for the NLP community</strong><br>
  Offline dataset &nbsp;·&nbsp; Live web scraping &nbsp;·&nbsp; Source metadata &nbsp;·&nbsp; CLI included
</p>

<p align="center">
  <img src="https://img.shields.io/pypi/v/bangla-synonyms" alt="PyPI version">
  <img src="https://img.shields.io/pypi/pyversions/bangla-synonyms" alt="Python versions">
  <img src="https://img.shields.io/pypi/l/bangla-synonyms" alt="License">
</p>

---

```bash
pip install bangla-synonyms
```

---

## Why

Bengali is spoken by over 230 million people, yet it remains one of the most underserved languages in the NLP ecosystem. Finding synonyms programmatically — something trivially easy for English — has no reliable solution for Bangla.

`bangla-synonyms` fills that gap. Common use cases:

- **Text augmentation** — expand training data for Bangla ML models
- **Search and indexing** — build synonym-aware search in Bangla applications
- **Writing tools** — avoid word repetition in Bangla text editors
- **Education** — vocabulary builders and language learning tools
- **Linguistics research** — corpus building and lexical analysis

Results are cached locally on first lookup, so the dataset grows automatically the more you use it. No API key required. No internet connection needed for cached words.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Scraping Sources](#scraping-sources)
- [Top-level API](#top-level-api)
  - [download()](#download)
  - [get()](#get)
  - [get_many()](#get_many)
  - [stats()](#stats)
- [Raw Mode](#raw-mode)
- [Scrapper](#scrapper)
- [Core API](#core-api)
  - [DatasetManager](#datasetmanager)
  - [WordlistFetcher](#wordlistfetcher)
  - [BatchScraper](#batchscraper)
- [CLI Reference](#cli-reference)
- [Dataset](#dataset)
- [Contributing](#contributing)
- [Acknowledgements](#acknowledgements)

---

## Features

|                        |                                                                     |
| ---------------------- | ------------------------------------------------------------------- |
| **Offline-first**      | Checks local dataset before making any network call                 |
| **Live fallback**      | Cascades through Wiktionary → Shabdkosh → English-Bangla            |
| **Quality filtering**  | Cross-source validation removes noise and wrong-sense entries       |
| **Source metadata**    | `raw=True` returns per-synonym source attribution and confidence    |
| **Source control**     | Choose exactly which sources to query                               |
| **Merge or first-hit** | Combine results from all sources, or stop at the first match        |
| **Opt-in persistence** | Scraped results are saved to disk only when `auto_save=True`        |
| **Batch scraping**     | Scrape thousands of words with progress tracking and resume support |
| **Dataset download** | One-command download of a pre-built dataset (~2,915 words, 18,158 synonym entries) |
| **CLI**                | Full command-line interface for scripting and one-off lookups       |
| **Python 3.9+**        | Type-annotated, minimal dependencies                                |

---

## Installation

```bash
pip install bangla-synonyms
```

---

## Quick Start

```python
import bangla_synonyms as bs

# Download the dataset once
bs.download()

# Look up a single word
bs.get("চোখ")
# → ['চক্ষু', 'নেত্র', 'লোচন', 'আঁখি', 'অক্ষি']

# Look up multiple words at once
bs.get_many(["চোখ", "মা", "সুন্দর"])
# → {
#     'চোখ':    ['চক্ষু', 'নেত্র', 'লোচন', 'আঁখি'],
#     'মা':     ['জননী', 'আম্মা', 'জন্মদাত্রী', 'মাতা'],
#     'সুন্দর': ['খুবসুরত', 'হাসিন', 'মনোরম', 'মনোহর'],
#   }
```

Words not found in the local dataset are scraped automatically:

```python
bs.get("তটিনী")
# → ['নদী', 'প্রবাহিনী', 'সরিৎ', 'স্রোতস্বিনী']
```

---

## Scraping Sources

Three sources are available. All three are used by default, tried in order from most to least reliable.

| Key                | Site                                                 | Type                | Notes                                        |
| ------------------ | ---------------------------------------------------- | ------------------- | -------------------------------------------- |
| `"wiktionary"`     | [bn.wiktionary.org](https://bn.wiktionary.org)       | Structured wikitext | Most reliable; queried first                 |
| `"shabdkosh"`      | [shabdkosh.com](https://www.shabdkosh.com)           | Dictionary          | Good coverage; clean output                  |
| `"english_bangla"` | [english-bangla.com](https://www.english-bangla.com) | bn→bn dictionary    | Last resort; near-synonyms and related words |

By default all three sources are tried and their results are merged and deduplicated.

### Quality filtering

Raw scraper output is passed through a multi-stage quality pipeline before being returned:

1. **Noise removal** — drops phrases, hyphenated entries, numbered items, entries containing digits or Latin characters, and zero-width characters.
2. **Cross-source validation** — when Wiktionary is present, its entries are kept in full (authoritative). Entries from other sources are filtered by source tier:
   - Shabdkosh entries are included only when Wiktionary independently confirms them.
   - English-Bangla entries are included only when confirmed by at least one other source.
3. **Deduplication** — duplicate synonyms across sources are removed, keeping the first-seen source attribution.

The `quality` field in raw mode output describes which strategy was applied.

---

## Top-level API

The most common operations are available directly on the package — no class or instance needed.

```python
import bangla_synonyms as bs
```

### `download()`

```python
bs.download()                       # full dataset (~3000 words)
bs.download("mini")                 # small starter set (~500 words)
bs.download(force=True)             # re-download even if the file already exists
bs.download("latest", force=True)
```

The dataset is saved to `./bangla_synonyms_data/dataset.json`.

---

### `get()`

```python
bs.get(word, sources=None, raw=False)
```

| Parameter | Type           | Default | Description                                    |
| --------- | -------------- | ------- | ---------------------------------------------- |
| `word`    | `str`          | —       | The Bangla word to look up                     |
| `sources` | `list \| None` | `None`  | Sources to query (`None` uses all three)       |
| `raw`     | `bool`         | `False` | Return a metadata dict instead of a plain list |

```python
bs.get("সুন্দর")
# → ['মনোরম', 'সুশ্রী', 'চমৎকার']

bs.get("সুন্দর", sources=["wiktionary"])
bs.get("সুন্দর", sources=["wiktionary", "shabdkosh"])

bs.get("সুন্দর", raw=True)
# → {
#   'word': 'সুন্দর',
#   'sources_results': {
#       'wiktionary': ['মনোরম', 'সুশ্রী', 'চমৎকার'],
#       'shabdkosh': ['লাবণ্যময়', 'দৃষ্টিনন্দন', 'মনোরম']
#   },
#   'results': [
#       {'synonym': 'মনোরম', 'source': 'wiktionary'},
#       {'synonym': 'সুশ্রী', 'source': 'wiktionary'}
#   ],
#   'words': ['মনোরম', 'সুশ্রী', 'চমৎকার'],
#   'sources_hit': ['wiktionary', 'shabdkosh'],
#   'sources_tried': ['wiktionary', 'shabdkosh'],
#   'quality': 'wikiconfirmed',
#   'source': 'wiktionary'
# }

bs.get("xyz")
# → []
```

---

### `get_many()`

```python
bs.get_many(words, sources=None, raw=False)
```

| Parameter | Type           | Default | Description                                  |
| --------- | -------------- | ------- | -------------------------------------------- |
| `words`   | `list[str]`    | —       | List of Bangla words to look up              |
| `sources` | `list \| None` | `None`  | Sources to query                             |
| `raw`     | `bool`         | `False` | Return metadata dicts instead of plain lists |

```python
bs.get_many(["চোখ", "মা", "নদী"])
# → {'চোখ': [...], 'মা': [...], 'নদী': [...]}

bs.get_many(["চোখ", "মা"], sources=["wiktionary"])

bs.get_many(["চোখ", "মা"], raw=True)
# → {'চোখ': {raw dict}, 'মা': {raw dict}}
```

---

### `stats()`

```python
bs.stats()
# Words         : 2915
# Total synonyms: 18158
# Avg / word    :  6.23
# Source        : /home/user/bangla_synonyms_data/dataset.json
# Top 5 words   :
#   চোখ: চক্ষু, নেত্র, লোচন, আঁখি ...
#   মা: জননী, আম্মা, জন্মদাত্রী ...
```
Returns a `dict` with keys: `total_words`, `total_synonyms`, `avg_per_word`, `source`.

---

## Raw Mode

Pass `raw=True` to any lookup function to receive full source metadata alongside results. This is supported at every level: `get()`, `get_many()`, and `Scrapper`.

### Response structure

```python
{
    "word": str,                  # looked up word
    "source": str | None,         # primary source

    "sources_results": {
        "source_name": list[str]  # synonyms returned by that source
    },

    "results": [
        {
            "synonym": str,
            "source": str
        }
    ],

    "words": list[str],           # flat synonym list
    "sources_hit": list[str],     # sources that returned data
    "sources_tried": list[str],   # queried sources
    "quality": str                # filtering strategy
}
```

### `quality` values

| Value             | Meaning                                                             |
| ----------------- | ------------------------------------------------------------------- |
| `"wikiconfirmed"` | Wiktionary was present; other sources filtered by cross-validation  |
| `"cross_source"`  | No Wiktionary; synonyms confirmed by two or more sources            |
| `"single_source"` | Only one source was available; noise-cleaned results returned as-is |
| `"local"`         | Returned from local dataset cache; no scraping was performed        |
| `"empty"`         | No results survived filtering, or all sources returned errors       |

### `confirmed` flag

The `confirmed: True` flag is set on entries from secondary sources that passed cross-validation. Wiktionary entries are always authoritative and do not carry this flag.

```python
result = bs.get("চোখ", raw=True)

# Filter to Wiktionary entries only
wiki = [r["synonym"] for r in result["results"] if r["source"] == "wiktionary"]

# Filter to cross-validated entries (Wiktionary + confirmed secondaries)
high_confidence = [
    r["synonym"] for r in result["results"]
    if r["source"] == "wiktionary" or r.get("confirmed")
]

# Check which filtering strategy was applied
print(result["quality"])         # "wikiconfirmed"
print(result["sources_hit"])     # ["wiktionary", "shabdkosh"]
```

---

## Scrapper

Fine-grained control over every aspect of the scraping process. Intended for researchers and power users.

```python
from bangla_synonyms import Scrapper
```

### Constructor

| Parameter   | Type           | Default | Description                                                  |
| ----------- | -------------- | ------- | ------------------------------------------------------------ |
| `offline`   | `bool`         | `False` | Use local dataset only; make no network calls                |
| `auto_save` | `bool`         | `False` | Persist scraped results to disk                              |
| `delay`     | `float`        | `1.0`   | Seconds between HTTP requests                                |
| `timeout`   | `int`          | `10`    | HTTP request timeout in seconds                              |
| `sources`   | `list \| None` | `None`  | Sources to query (`None` = all three)                        |
| `merge`     | `bool`         | `True`  | Merge all sources (`True`) or stop at first result (`False`) |

```python
sc = Scrapper()                                       # online, no persistence
sc = Scrapper(offline=True)                           # local dataset only
sc = Scrapper(auto_save=True)                         # persist results
sc = Scrapper(sources=["wiktionary"])                 # single source
sc = Scrapper(sources=["wiktionary", "shabdkosh"])    # two sources
sc = Scrapper(merge=False)                            # stop at first hit
sc = Scrapper(delay=2.0, timeout=20)                  # slow connection
```
### `.get(word, raw=False)`

Fetch synonyms for a given Bengali word.

- Checks the **local dataset first**
- Falls back to **live sources** if not found
- Can merge results from multiple sources (depending on config)

---

#### Basic Usage

```python
sc.get("চোখ")
# → ['চক্ষু', 'নেত্র', 'লোচন', 'আঁখি', 'নয়ন']
```

---

#### Full Structured Output

```python
sc.get("চোখ", raw=True)
# → {
#     'word': 'চোখ',
#     'source': 'wiktionary',
#     'sources_results': {
#         'wiktionary': ['চক্ষু', 'নেত্র', 'লোচন', 'আঁখি', 'নয়ন'],
#         'shabdkosh': [...],
#         'english_bangla': [...]
#     },
#     'results': [
#         {'synonym': 'চক্ষু', 'source': 'wiktionary'},
#         {'synonym': 'নেত্র', 'source': 'wiktionary'},
#         {'synonym': 'লোচন', 'source': 'wiktionary'},
#         {'synonym': 'আঁখি', 'source': 'wiktionary'},
#         {'synonym': 'নয়ন', 'source': 'wiktionary'}
#     ],
#     'words': ['চক্ষু', 'নেত্র', 'লোচন', 'আঁখি', 'নয়ন'],
#     'sources_hit': ['wiktionary', 'shabdkosh', 'english_bangla'],
#     'sources_tried': ['wiktionary', 'shabdkosh', 'english_bangla'],
#     'quality': 'wikiconfirmed'
# }
```

---

#### 🧠 How It Works

- **`sources_results`** → raw results from all sources  
- **`results`** → cleaned + selected synonyms (based on priority)  
- **`words`** → final flattened synonym list (default output)  
- **`source`** → primary source used for final selection  
- **`quality`** → confidence level (e.g. `local`, `wikiconfirmed`)  
- **`sources_hit`** → sources that returned data  
- **`sources_tried`** → all attempted sources  

---

#### Notes

```python
# Local cache hit — no network call
sc.get("মা", raw=True)

# Offline mode — only local dataset is used
Scrapper(offline=True).get("নদী")
```

---

### `.get_many(words, raw=False)`

Fetch synonyms for multiple words at once.

```python
sc.get_many(["চোখ", "মা", "নদী"])
# → {'চোখ': [...], 'মা': [...], 'নদী': [...]}

sc.get_many(["চোখ", "মা"], raw=True)
# → {
#     'চোখ': { ...full structured response... },
#     'মা': { ...full structured response... }
# }
```

The request delay applies only to live HTTP calls. Local cache hits incur no delay.

### `.active_sources`

```python
Scrapper().active_sources
# → ["wiktionary", "shabdkosh", "english_bangla"]

Scrapper(sources=["wiktionary"]).active_sources
# → ["wiktionary"]
```

### `.download()` — class method

```python
Scrapper.download()
Scrapper.download("mini")
Scrapper.download(force=True)
```

### Source selection patterns

```python
# Structured data only — best for NLP pipelines
sc = Scrapper(sources=["wiktionary"])

# Maximum coverage — all sources merged
sc = Scrapper()

# Speed-first — stop at the first source that returns results
sc = Scrapper(merge=False)

# Exclude the lowest-reliability source
sc = Scrapper(sources=["wiktionary", "shabdkosh"])

# Long-running batch — persist results, polite rate limit
sc = Scrapper(auto_save=True, delay=2.0)
```

### Dataset helpers

```python
sc.add("পরিবেশ", ["প্রকৃতি", "জগত", "বিশ্ব"])  # add to local dataset
sc.stats()                                        # dataset statistics
sc.export("synonyms.json")                        # export as JSON
sc.export("synonyms.csv", fmt="csv")              # export as CSV
```

---

## Core API

Lower-level building blocks for advanced users.

### DatasetManager

Direct read/write access to the local synonym dataset.

```python
from bangla_synonyms.core import DatasetManager

dm = DatasetManager()
```

All instances share the same in-memory store. A change made through one instance is immediately visible through any other.

Dataset location: `./bangla_synonyms_data/dataset.json`

#### Reading data

```python
dm.get("চোখ")          # → ['চক্ষু', 'নেত্র', ...]   empty list if not found
dm.has("চোখ")          # → True / False
dm.all_words()         # → sorted list of all words in the dataset
"চোখ" in dm           # → True
len(dm)               # → 9842
```

#### Writing data

```python
# Merge new synonyms with any that already exist
dm.add("শব্দ", ["প্রতিশব্দ১", "প্রতিশব্দ২"])

# Replace the synonym list entirely
dm.update("শব্দ", ["নতুন১", "নতুন২"])

# Remove a word
dm.remove("শব্দ")   # returns True if the word existed, False otherwise
```

Each write automatically flushes to disk. To batch multiple writes into a single flush, pass `save=False` and export manually:

```python
dm.add("ক", ["খ", "গ"],  save=False)
dm.add("ঘ", ["ঙ"],       save=False)
dm.add("চ", ["ছ", "জ"],  save=False)
dm.export("synonyms.json")
```

#### Merging from a file

```python
added = dm.merge("extra_synonyms.json")
print(f"{added} new words added")
```

The JSON file should have the same format as the main dataset:

```json
{
  "নদী": ["তটিনী", "প্রবাহিনী", "সরিৎ"],
  "আকাশ": ["গগন", "অম্বর", "নভ"]
}
```

#### Exporting

```python
dm.export("synonyms.json")             # JSON (default)
dm.export("synonyms.csv", fmt="csv")   # CSV

dm.reload()   # reload from disk after an external change
```

CSV format:

```
word,synonyms,count
চোখ,চক্ষু | নেত্র | লোচন | আঁখি,4
মা,জননী | আম্মা | জন্মদাত্রী,3
```

#### Stats

```python
info = dm.stats()
# Words         : 2915
# Total synonyms: 18158
# Avg / word    : 6.23
# Source        : /home/user/bangla_synonyms_data/dataset.json
# Top 5 words   :
#   চোখ: চক্ষু, নেত্র, লোচন, আঁখি ...

info["total_words"]     
info["total_synonyms"]  
info["avg_per_word"]   
```

---

### WordlistFetcher

Fetches Bangla word lists from Wiktionary for use with `BatchScraper`.

```python
from bangla_synonyms.core import WordlistFetcher, DatasetManager

wf = WordlistFetcher()
dm = DatasetManager()
```

```python
# Fetch up to 500 words from Wiktionary
words = wf.fetch(limit=500)

# Filter to words not yet in the local dataset (enables safe resume)
new_words = wf.filter_new(words, dm)
print(f"{len(new_words)} words not yet scraped")

# Persist and reload word lists
wf.save(words, "wordlist.txt")
words = wf.load("wordlist.txt")
```

---

### BatchScraper

Scrapes synonyms for large word lists with progress tracking, checkpointing, and resume support.

```python
from bangla_synonyms.core import BatchScraper
```

#### Constructor

| Parameter    | Default | Description                                     |
| ------------ | ------- | ----------------------------------------------- |
| `dataset`    | shared  | `DatasetManager` instance to write results into |
| `delay`      | `1.0`   | Seconds between HTTP requests                   |
| `timeout`    | `10`    | HTTP request timeout in seconds                 |
| `save_every` | `50`    | Flush results to disk every N words             |
| `sources`    | `None`  | Sources to query (`None` = all three)           |
| `merge`      | `True`  | Merge all sources or stop at first hit          |

#### `.run(words, skip_existing=True, show_progress=True, sources=None)`

```python
scraper = BatchScraper(delay=1.0)

result = scraper.run(["চোখ", "মা", "নদী", "আকাশ"])
#   [ 1/4] চোখ: ✓ চক্ষু, নেত্র, লোচন ...
#   [ 2/4] মা:  ✓ জননী, আম্মা, জন্মদাত্রী
#   [ 3/4] নদী: ✓ তটিনী, প্রবাহিনী
#   [ 4/4] আকাশ: — not found
#
#   [bangla-synonyms] done: 3 found, 1 not found, 0 errors

# Safe to re-run; already-scraped words are skipped
result = scraper.run(words, skip_existing=True)

# Override sources for this run only
result = scraper.run(words, sources=["wiktionary"])

# Suppress progress output
result = scraper.run(words, show_progress=False)

# Return value: {word: [synonyms], ...} for newly scraped words
```

#### `.run_from_wiktionary(limit=200)`

Fetches a word list from Wiktionary and scrapes all of them in one step.

```python
scraper = BatchScraper(delay=1.5, sources=["wiktionary", "shabdkosh"])
scraper.run_from_wiktionary(limit=1000)
```

#### Full batch workflow

```python
from bangla_synonyms.core import DatasetManager, WordlistFetcher, BatchScraper

dm = DatasetManager()
wf = WordlistFetcher()

# Fetch word list
words = wf.fetch(limit=5000)
wf.save(words, "wordlist.txt")

# Skip words already in the dataset
new_words = wf.filter_new(words, dm)
print(f"{len(new_words)} words to scrape")

# Scrape
scraper = BatchScraper(
    delay=1.0,
    save_every=100,
    sources=["wiktionary", "shabdkosh"],
)
scraper.run(new_words, skip_existing=True)

# Export
dm.stats()
dm.export("bangla_synonyms_full.json")
dm.export("bangla_synonyms_full.csv", fmt="csv")
```

---

## CLI Reference

```bash
# Dataset management
bangla-synonyms download
bangla-synonyms download --version mini
bangla-synonyms download --force

# Synonym lookup
bangla-synonyms get চোখ
bangla-synonyms get চোখ মা সুন্দর
bangla-synonyms get চোখ --offline
bangla-synonyms get চোখ --sources wiktionary
bangla-synonyms get চোখ --sources wiktionary --sources shabdkosh
bangla-synonyms get চোখ --no-merge
bangla-synonyms get চোখ --raw


# Build / expand the local dataset
bangla-synonyms build
bangla-synonyms build --limit 1000
bangla-synonyms build --delay 2.0
bangla-synonyms build --sources wiktionary
bangla-synonyms build --sources wiktionary --sources shabdkosh
bangla-synonyms build --no-merge

# Information and export
bangla-synonyms stats
bangla-synonyms export synonyms.json
bangla-synonyms export synonyms.csv --format csv

# Help
bangla-synonyms --help
bangla-synonyms get --help
bangla-synonyms build --help
```

The CLI functions are also importable for use in scripts:

```python
from bangla_synonyms.cli import get, build, stats

result = get(["চোখ", "মা"])
result = get(["চোখ"], offline=True)
result = get(["চোখ"], sources=["wiktionary"], merge=False)

added  = build(limit=500, delay=1.5)
info   = stats()
```

---

## Dataset

A pre-built dataset is available for download via GitHub Releases.

| Version  | Words   | Approximate size | Command               |
| -------- | ------- | ---------------- | --------------------- |
| `latest` | ~2915 | ~100 MB            | `bs.download()`       |
| `mini`   | ~500    | ~150 KB          | `bs.download("mini")` |

The dataset is saved to `./bangla_synonyms_data/dataset.json`. All running instances pick up the new data immediately after a download — no restart required.

### Building a larger dataset

```bash
bangla-synonyms build --limit 5000 \
    --sources wiktionary --sources shabdkosh \
    --delay 1.5

bangla-synonyms stats
bangla-synonyms export my_dataset.json
```

### Dataset format

```json
{
  "চোখ": ["চক্ষু", "নেত্র", "লোচন", "আঁখি", "অক্ষি"],
  "মা": ["জননী", "আম্মা", "জন্মদাত্রী", "মাতা"],
  "নদী": ["তটিনী", "প্রবাহিনী", "সরিৎ", "স্রোতস্বিনী"]
}
```

---

## Contributing

Bengali is spoken by 230 million people but remains one of the most underserved
languages in NLP. `bangla-synonyms` is one of the few programmatic tools for
Bangla lexical resources — your contribution directly improves what the entire
community can build.

Bug reports, new sources, quality improvements, and dataset contributions are
all welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow —
how to open issues, create branches, and submit PRs.

> **BNLP users** — if you use [BNLP](https://github.com/sagorbrur/bnlp) for
> tokenization, embeddings, or NER, `bangla-synonyms` pairs naturally with it.
> Use this library to expand your training vocabulary, augment datasets, or
> build synonym-aware preprocessing pipelines on top of BNLP models.

---

---

## Acknowledgements

Data sources used by this package:

- [Bangla Wiktionary](https://bn.wiktionary.org) — CC BY-SA 3.0
- [Shabdkosh](https://www.shabdkosh.com)
- [English-Bangla Dictionary](https://www.english-bangla.com)
