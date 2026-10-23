# BidCompass data overview

Quick map of every data source and file. Contents of `raw/` and `processed/` are gitignored (only `.gitkeep` is tracked), so everything here can be re-created with the commands shown.

```
data/
├── raw/                      Untouched downloads / cached responses
│   ├── base/                 Portal BASE (public procurement)
│   │   ├── anuncios_<year>/  Announcements (pre-award)
│   │   └── contratos_<year>/ Contracts (post-award)
│   ├── dre/<nAnuncio>/       One folder per tender: DRE notice + peças do procedimento
│   └── impic/                Cached IMPIC alvará lookup responses
└── processed/                Cleaned, derived files used by the product
    ├── tenders/              Clean tender pool from BASE
    │   └── tenders.parquet
    ├── extraction/           Master tables extracted from the peças (reviewed in the terminal)
    │   ├── tender_requirements.csv   Alvará requirements per tender, with review status
    │   ├── tender_terms.csv          Price, deadlines, guarantees, award, technical, financial, eligibility terms
    │   ├── tender_alvara_status.csv  One row per tender: counts, notice-vs-peças disagreement, review progress
    │   ├── translations.csv          Portuguese → English cache for the review screen
    │   ├── tender_columns.csv        Column dictionary (meaning and source of every column)
    │   └── tender_terms_fields.csv   Term groups/fields extracted
    ├── eval/                 Outputs of the eval/ scripts
    │   └── base_comparison.csv       LLM price/deadline/lots vs BASE (from eval.compare_base)
    └── impic/                Parsed alvará per company
```

## Sources at a glance

| Source | What it is | Role in BidCompass | Created by |
|---|---|---|---|
| **BASE anuncios** | Public tender announcements (buyer, description, base price, CPVs, bid deadline, document links) | **Active tenders** shown to customers; history for reasoning | `python -m ingest.base anuncios <year>` |
| **BASE contratos** | Awarded contracts (winner, contract price, competitors, CPVs) | Training and reasoning: who wins what, at what price. Only ~17% link back to an announcement via `nAnuncio` | `python -m ingest.base contratos <year>` |
| **DRE notice PDFs** | Official notice for each tender, linked from the announcement `url` field | Source of the required alvará (category, subcategory, class) and base price per notice | `python -m eval.alvara_sample` |
| **IMPIC alvará register** | A company's construction licence: categories, subcategories, classes | The company side of the eligibility match | `python -m ingest.impic <nif>` |

---

## raw/base: Portal BASE

Years 2012–2026. Each year folder has the JSON file plus (for contratos) the original `.zip`. The zip is kept next to the extracted JSON and can be deleted to save space.

| Path | Content |
|---|---|
| `raw/base/anuncios_<year>/anuncios<year>.json` | JSON array of announcements, ~20 fields each (e.g. `nAnuncio`, `IdIncm`, `tipoActo`, `PrecoBase`, `DataLimitePropostas`, `CPVs`, `url`, `PecasProcedimento`) |
| `raw/base/contratos_<year>/Contratos<year>.json` (+ `.zip`) | JSON array of contracts, ~39 fields each (winner, price, procedure type, competitors, CPVs, `nAnuncio` link) |

Notes
- Announcements have the bid deadline, so only they define "active" tenders. Contracts do not.
- Dates are `dd/mm/yyyy`; `PrecoBase` is a string; some names contain HTML entities; some winners have no NIF.
- Full field list: [BASE_DATA_BRIEF.md](../BASE_DATA_BRIEF.md).

## raw/dre/<nAnuncio>/: one folder per tender

Everything we hold for a tender lives in one folder (`/` in the number replaced by `-`, e.g. `8844-2026/`). 30 notices from the 2026 construction sample.

| Path | Content | Created by |
|---|---|---|
| `notice.pdf` / `notice.txt` | DRE notice and its PyMuPDF text | `eval.alvara_sample` |
| `pecas/source.json` | Link, platform, status, method, file list | `ingest.pecas` |
| `pecas/pecas.zip`, `pecas/files/` | Original peças (programa, caderno de encargos, annexes), zips unpacked | `ingest.pecas` |
| `pecas/text/` | Text of every PDF, mirroring `files/` | `ingest.pecas` |
| `pecas/alvara_llm.json` | Gemini extraction of the alvará requirement (per lot, per subcategory, with quote and source file) | `extract.pecas_llm` |
| `pecas/landing.html` | Platform landing page when the link is not a direct file | `ingest.pecas` |

Peças come from the `PecasProcedimento` link in BASE. So far only the 13 notices the prefill could not resolve have peças (up to ~300 MB each; `data/raw/` is gitignored).

Platforms (all work without login):
- ACINGOV: plain HTTP with a browser User-Agent returns a zip.
- Vortal: JS app; Playwright opens the page, goes to "5 - DOCUMENTOS" and fetches the tokenised `a.buttonDownload` links.
- Anogov: Playwright reads the `decryptservlet` links from the document list page.

Needs `playwright install chromium`. Platform terms of use have not been reviewed, so this is for pilot use only (an API would be preferable).

Data-discovery findings (13 notices checked against peças):
- The notice's section 12 is unreliable. Where it says "Não" or is silent, the programa/caderno still requires an alvará in all 13 cases checked, so the real requirement is in the peças.
- The class rule varies per subcategory within one tender ("valor global" vs "valor dos trabalhos especializados"), and some tenders add subcategories per lot, so a single `class` column is insufficient.
- The notice regex finds the codes in only some peças (wording variants: "A6ª", parentheses, "4ª, e 5ª", heading-then-list, categories in words). The Gemini pass (`extract.pecas_llm`) resolved all 30 tenders (133 requirements, all valid codes) and needs manual review. Always send the DRE notice copy bundled in the peças (numeric filename): for 19561 and 20271 it is the only place the requirement appears.

Fields we read from the notice: section 5 (base price), lots, section 12 (qualification documents, alvará category and subcategory). Reference: [DR_Tender_Documentation.md](../DR_Tender_Documentation.md).

## processed/extraction/tender_requirements.csv: master table (what the webapp shows)

One row per (tender, lot, subcategory) required in the peças. Built by `python -m extract.build_requirements` from the LLM extractions; reviewed with `python -m eval.review_requirements`.

Every column, what it means and where it comes from is listed in `processed/extraction/tender_columns.csv` (written by the build script, which fails if a column is undocumented). In short:

| Group | Columns | Source |
|---|---|---|
| Identity | `nAnuncio`, `lot`, `code`, `category`, `subcategory` | tender folder name; the rest read by the LLM from the peças |
| Content | `determinant`, `class_rule`, `class_number`, `alternative_group` | LLM, from the peças (the class is never derived from the price) |
| Evidence | `quote`, `source_file` | verbatim excerpt and its file, from the peças |
| Provenance | `extraction_method`, `model_served`, `prompt_version`, `extracted_at` | `pecas/alvara_llm.json` metadata |
| Review | `status`, `reviewer`, `reviewed_at`, `review_note` | `eval.review_requirements` |

This is the extraction step only: it records what the documents say. A plain-language "what you need to bid" analysis is a later, separate step.

Rebuilds keep reviews when the row content is unchanged; changed rows go back to `unreviewed` with a note. `processed/extraction/tender_alvara_status.csv` has one row per tender (`states_alvara`, requirement count, reviewed count, and `notice_disagrees` when the DRE notice's answer differs from the peças).

---

## raw/impic: cached IMPIC responses

Raw HTML from IMPIC's internal lookup endpoint (unofficial, may change). Used as a disk cache so IMPIC is not called twice for the same query.

| Path | Content |
|---|---|
| `raw/impic/<nif>_search.html` | Search result by NIF: licence number, NIF, name |
| `raw/impic/<licence>_detail.html` | Licence detail: header fields and the table of qualifications |

Currently cached: NIFs 503451541 (Restradas) and 506805450 (Pedroso), plus licence details 23919 and 57728.

---

## processed/tenders/tenders.parquet: clean tender pool

Built from BASE anuncios 2025 and 2026 by `python -m ingest.tenders`. About 58,700 rows, one per notice.

- **Dedup:** on `IdIncm`. A procedure and its rectification are kept as separate rows. Rows with placeholder `IdIncm = -1` are deduped on `nAnuncio` + `tipoActo`.
- **Cleaned fields:** dates parsed, `PrecoBase` as float (EUR), HTML unescaped, `cpv_codes` (8-digit list).
- **Flag columns:**

| Column | Meaning |
|---|---|
| `is_procedure` | `tipoActo` is "Anúncio de procedimento" (not an amendment or other notice) |
| `is_works_type` | `tiposContrato` contains "Empreitadas de obras públicas" |
| `has_cpv45` | Any CPV code starts with 45 |
| `is_construction` | `is_works_type` OR `has_cpv45` |
| `is_open` | `DataLimitePropostas` is today or later |
| `has_amendment` | Procedure sharing its `nAnuncio` with a non-procedure row |
| `price_band` | `<=200k`, `200k-400k`, `400k-800k`, `800k-1M`, `>1M`, `unknown` |

Active tenders for customers: filter `is_construction & is_procedure & is_open`.

## processed/impic/<nif>.json: parsed alvará

One file per looked-up company, created by `python -m ingest.impic <nif>`:

```json
{"licence": "23919 - PUB", "nif": "503451541", "name": "...", "max_class": 7,
 "registered": "...", "municipality": "...", "district": "...",
 "qualifications": [{"category": 1, "category_name": "...", "subcategory": 1,
                     "subcategory_name": "...", "class": 7}]}
```

Currently: 503451541 (41 qualifications) and 506805450.

---

## Evaluation files (not in `data/`, in `eval/`)

| File | Purpose |
|---|---|
| `eval/alvara_sample.csv` | 30 sampled 2026 construction tenders (12 ≤200k, 12 200–400k, 6 400k–1M) with empty annotation columns |
| `eval/archive/alvara_prefill.csv` | Rule-based pre-fill from the notice texts (subcategories, class, lots) plus empty `verified` / `reviewer_notes` columns for manual review |
| `eval/pecas_probe.py` | Runs the notice regex on the peças text and compares with the notice result |
| `extract/pecas_prompt.json` | (in `extract/`) Prompt, model, term field list and response schema for the Gemini extraction. Edit here |
| `extract/pecas_llm.py` | (in `extract/`) One Gemini call per tender; writes `pecas/alvara_llm.json` (alvará + terms) |
| `extract/build_requirements.py`, `extract/reference.py` | (in `extract/`) Build the master tables; class table / valid codes |
| `extract/translate.py` | (in `extract/`) English translations of quotes/details for the reviewer (`python -m extract.translate`, cached in `translations.csv`) |
| `eval/review_requirements.py`, `eval/compare_base.py` | Terminal review of the master tables; LLM-vs-BASE cross-check (price, deadline, lots) | |
| `eval/check_dedup.py` | Checks duplicate `nAnuncio` groups in the raw announcements |
| `eval/test_impic_parse.py` | Offline test of the IMPIC parsers |

## Rebuild order

1. `python -m ingest.base anuncios 2025 2026` (and `contratos` as needed)
2. `python -m ingest.tenders` → `processed/tenders/tenders.parquet`
3. `python -m eval.alvara_sample` → `raw/dre/` + `eval/alvara_sample.csv`
4. `python -m eval.alvara_prefill` → `eval/archive/alvara_prefill.csv` (regex on notices, kept for comparison)
5. `python -m ingest.pecas --from-csv eval/archive/alvara_prefill.csv` → `raw/dre/<id>/pecas/` (skips tenders already downloaded; `--not-yes` limits to unresolved ones)
6. `python -m extract.pecas_llm` → `raw/dre/<id>/pecas/alvara_llm.json` (needs `gemini_api_key` in `.env`; prompt in `extract/pecas_prompt.json`)
7. `python -m extract.build_requirements` → `processed/extraction/tender_requirements.csv`, `tender_terms.csv`, `tender_alvara_status.csv`, `tender_columns.csv`, `tender_terms_fields.csv`
8. `python -m extract.translate` → `processed/extraction/translations.csv`, then re-run step 7 to fill `quote_en` (translation reads the tables from step 7)
9. `python -m eval.compare_base` → `processed/eval/base_comparison.csv` (cross-check of price, deadline and lots against BASE)
10. `python -m eval.review_requirements` → fills the review columns
11. `python -m ingest.impic <nif>` → `raw/impic/` + `processed/impic/`
