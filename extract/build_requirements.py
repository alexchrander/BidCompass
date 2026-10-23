"""Build the master tender tables from the per-tender LLM extractions.

Inputs:  data/raw/dre/<id>/pecas/alvara_llm.json        (python -m extract.pecas_llm)
         eval/archive/alvara_prefill.csv                (notice regex, only used for the disagreement flag)
Outputs: data/processed/extraction/tender_requirements.csv         alvará requirements, one row per (tender, lot, subcategory)
         data/processed/extraction/tender_terms.csv                other terms (price, deadlines, guarantees, award, technical,
                                                        financial, eligibility), one row per (tender, lot, field, detail)
         data/processed/extraction/tender_alvara_status.csv        one row per tender
         data/processed/extraction/tender_columns.csv              what every column means and where it comes from
         data/processed/extraction/tender_terms_fields.csv         the allowed term fields and their meaning

Review columns (status, reviewer, reviewed_at, review_note) are preserved across rebuilds.
Reviews survive a rebuild: 'corrected' and 'rejected' rows keep the reviewer's version, 'confirmed' rows are kept
only if the new extraction has the same content (otherwise they go back to 'unreviewed' with a note), and
'added' rows (manually added in review) are always kept.

Run: python -m extract.build_requirements
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ingest.common import PROCESSED_DIR, PROJECT_ROOT, RAW_DIR

EXTRACTION_DIR = PROCESSED_DIR / "extraction"

REQ_CSV = EXTRACTION_DIR / "tender_requirements.csv"
STATUS_CSV = EXTRACTION_DIR / "tender_alvara_status.csv"
TERMS_CSV = EXTRACTION_DIR / "tender_terms.csv"
DICTIONARY_CSV = EXTRACTION_DIR / "tender_columns.csv"
FIELDS_CSV = EXTRACTION_DIR / "tender_terms_fields.csv"
CACHE = EXTRACTION_DIR / "translations.csv"
PROMPT_FILE = Path(__file__).parent / "pecas_prompt.json"
KEY = ["nAnuncio", "lot", "code"]
CONTENT = ["determinant", "class_rule", "class_number", "alternative_group"]
REVIEW = ["status", "reviewer", "reviewed_at", "review_note"]
PROVENANCE = ["extraction_method", "model_served", "prompt_version", "extracted_at"]
COLUMNS = ["nAnuncio", "lot", "code", "category", "subcategory", *CONTENT, "quote", "quote_en", "source_file", *PROVENANCE, *REVIEW]
TERMS_KEY = ["nAnuncio", "lot", "group", "field", "detail"]
TERMS_CONTENT = ["value", "unit"]
TERMS_COLUMNS = ["nAnuncio", "lot", "group", "field", "value", "unit", "detail", "quote", "quote_en", "source_file", *PROVENANCE, *REVIEW]


REQ_DOCS = [
    ("nAnuncio", "Tender id, the DRE notice number with '-' (e.g. 8844-2026). Same as the folder name in data/raw/dre.", "Portal BASE (nAnuncio); folder name in data/raw/dre/"),
    ("lot", "Lot the requirement applies to; empty when the tender has no lots or the requirement is common to all lots.", "LLM, read from the peças"),
    ("code", "Alvará habilitação as category.subcategory, e.g. 4.12 = 12.ª subcategoria da 4.ª categoria.", "LLM, read from the peças; validated against DR_Tender_Documentation.md"),
    ("category", "Category number (1-5) of the habilitação.", "Part of code"),
    ("subcategory", "Subcategory number within the category.", "Part of code"),
    ("determinant", "True if the document flags this as the determining (main) subcategory.", "LLM, read from the peças"),
    ("class_rule", "How the required class is defined: global_value (covers the whole proposal), work_value (covers the works of this subcategory), explicit_class (a class number is stated), not_stated.", "LLM, read from the peças"),
    ("class_number", "Class 1-9 when the documents state one explicitly; otherwise empty. The class is never derived from the price here.", "LLM, read from the peças"),
    ("alternative_group", "Label shared by requirements that are alternatives ('ou'); empty when the requirement is cumulative.", "LLM, read from the peças"),
    ("quote", "Short verbatim excerpt from the document supporting the row (max 300 characters).", "LLM, copied from the peças"),
    ("quote_en", "English translation of the quote, for the reviewer only; the Portuguese quote is the source of truth.", "Gemini, via extract.translate (cached in translations.csv)"),
    ("source_file", "Text file the quote comes from, relative to data/raw/dre/<id>/pecas/text/ (a numeric name is the DRE notice copy).", "LLM, from the '=== FILE:' header it was given"),
    ("extraction_method", "'llm' for rows extracted by the model, 'manual' for rows added during review.", "extract.build_requirements / eval.review_requirements"),
    ("model_served", "Model the API reports having served (may differ from the model requested).", "_meta.model_served in pecas/alvara_llm.json"),
    ("prompt_version", "Version of eval/pecas_prompt.json used for the extraction.", "_meta.prompt_version in pecas/alvara_llm.json"),
    ("extracted_at", "When the extraction file was written (local time).", "Modification time of pecas/alvara_llm.json"),
    ("status", "Review state: unreviewed, confirmed, corrected, rejected, or added (missed by the LLM, added by hand).", "eval.review_requirements"),
    ("reviewer", "Who reviewed the row.", "eval.review_requirements"),
    ("reviewed_at", "When the row was reviewed.", "eval.review_requirements"),
    ("review_note", "Free-text reviewer note, or an automatic note when the content changed after a review.", "eval.review_requirements / extract.build_requirements"),
]
TERMS_DOCS = [
    ("nAnuncio", "Tender id (same as in tender_requirements.csv).", "Folder name in data/raw/dre"),
    ("lot", "Lot the term applies to; empty when it applies to the whole procedure.", "LLM, read from the peças"),
    ("group", "Field group: price, deadlines, guarantees, award, technical, financial or eligibility.", "term_fields in extract/pecas_prompt.json"),
    ("field", "What the term is, from the fixed list in tender_terms_fields.csv (the LLM cannot invent fields).", "term_fields in extract/pecas_prompt.json"),
    ("value", "Normalised value: numbers without separators, dates as YYYY-MM-DD, yes/no, or short text.", "LLM, read from the peças"),
    ("unit", "Unit of the value (EUR, days, months, %, years); empty if none.", "LLM, read from the peças"),
    ("detail", "Qualifier: factor name, insurance type, role, document name, formula and so on.", "LLM, read from the peças"),
    ("quote", "Short verbatim excerpt from the document supporting the row (max 300 characters).", "LLM, copied from the peças"),
    ("quote_en", "English translation of the quote, for the reviewer only; the Portuguese quote is the source of truth.", "Gemini, via extract.translate (cached in translations.csv)"),
    ("source_file", "Text file the quote comes from, relative to data/raw/dre/<id>/pecas/text/.", "LLM, from the '=== FILE:' header it was given"),
    ("extraction_method", "'llm' or 'manual' (added during review).", "extract.build_requirements / eval.review_requirements"),
    ("model_served", "Model the API reports having served.", "_meta.model_served in pecas/alvara_llm.json"),
    ("prompt_version", "Version of extract/pecas_prompt.json used.", "_meta.prompt_version in pecas/alvara_llm.json"),
    ("extracted_at", "When the extraction file was written (local time).", "Modification time of pecas/alvara_llm.json"),
    ("status", "Review state: unreviewed, confirmed, corrected, rejected or added.", "eval.review_requirements"),
    ("reviewer", "Who reviewed the row.", "eval.review_requirements"),
    ("reviewed_at", "When the row was reviewed.", "eval.review_requirements"),
    ("review_note", "Free-text reviewer note, or an automatic note when content changed after a review.", "eval.review_requirements / extract.build_requirements"),
]
STATUS_DOCS = [
    ("nAnuncio", "Tender id (same as in tender_requirements.csv).", "Folder name in data/raw/dre"),
    ("states_alvara", "yes = peças require an alvará with named subcategories; no = they say none is required; unclear = required but not identifiable or contradictory.", "LLM, read from the peças"),
    ("n_requirements", "Number of alvará requirement rows extracted for the tender.", "Count of the LLM's requirements"),
    ("n_terms", "Number of other-term rows extracted for the tender.", "Count of the LLM's terms"),
    ("llm_notes", "One-sentence note from the model about anything ambiguous.", "LLM"),
    ("notice_states_alvara", "What the regex on the DRE notice (section 12) said; kept to measure how reliable the notice is.", "eval/archive/alvara_prefill.csv"),
    ("notice_disagrees", "True when the notice answer differs from the peças answer.", "Derived: states_alvara != notice_states_alvara"),
    ("n_reviewed", "Number of this tender's alvará requirement rows that have been reviewed.", "Derived from status in tender_requirements.csv"),
    ("n_terms_reviewed", "Number of this tender's term rows that have been reviewed.", "Derived from status in tender_terms.csv"),
]


def load_cache() -> dict[str, str]:
    if not CACHE.exists():
        return {}
    df = pd.read_csv(CACHE, dtype=str, keep_default_na=False)
    return dict(zip(df["pt"], df["en"]))


def norm(value) -> str:
    return "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value).strip()


def load_extractions() -> tuple[list[dict], list[dict], list[dict]]:
    rows, terms, statuses = [], [], []
    for path in sorted((RAW_DIR / "dre").glob("*/pecas/alvara_llm.json")):
        n_anuncio = path.parent.parent.name
        result = json.loads(path.read_text(encoding="utf-8"))
        meta = result.get("_meta", {})
        extracted_at = pd.Timestamp(path.stat().st_mtime, unit="s").strftime("%Y-%m-%dT%H:%M:%S")
        model = meta.get("model_served") or meta.get("model_requested") or meta.get("model") or ""
        count = 0
        for lot in result["lots"]:
            for r in lot["requirements"]:
                count += 1
                rows.append({
                    "nAnuncio": n_anuncio, "lot": norm(lot["lot_name"]), "code": f"{r['category']}.{r['subcategory']}",
                    "category": r["category"], "subcategory": r["subcategory"],
                    "determinant": bool(r.get("determinant", False)), "class_rule": r["class_rule"],
                    "class_number": norm(r.get("class_number")), "alternative_group": norm(r.get("alternative_group")),
                    "quote": r["quote"], "source_file": r["source_file"], "extraction_method": "llm",
                    "model_served": model, "prompt_version": meta.get("prompt_version", ""), "extracted_at": extracted_at,
                })
        provenance = {"extraction_method": "llm", "model_served": model,
                      "prompt_version": meta.get("prompt_version", ""), "extracted_at": extracted_at}
        for t in result.get("terms", []):
            terms.append({"nAnuncio": n_anuncio, "lot": norm(t.get("lot")), "group": t["group"], "field": t["field"],
                          "value": norm(t["value"]), "unit": norm(t.get("unit")), "detail": norm(t.get("detail")),
                          "quote": t["quote"], "source_file": t["source_file"], **provenance})
        statuses.append({"nAnuncio": n_anuncio, "states_alvara": result["states_alvara"], "n_requirements": count,
                         "n_terms": len(result.get("terms", [])), "llm_notes": result.get("notes", "")})
    return rows, terms, statuses


def merge_reviews(new: pd.DataFrame, path: Path, key_cols: list[str], content_cols: list[str]) -> pd.DataFrame:
    new = new.astype(str)
    for col in REVIEW:
        new[col] = ""
    new["status"] = "unreviewed"
    if not path.exists():
        return new
    old = pd.read_csv(path, dtype=str, keep_default_na=False)
    old_idx = old.set_index(key_cols)
    for i, row in new.iterrows():
        key = tuple(row[k] for k in key_cols)
        if key not in old_idx.index:
            continue
        prev = old_idx.loc[key]
        if isinstance(prev, pd.DataFrame):
            prev = prev.iloc[0]
        if prev["status"] == "unreviewed":
            continue
        if prev["status"] in ("corrected", "rejected"):
            # The reviewer's version wins over a fresh extraction.
            for col in [*content_cols, *REVIEW]:
                new.at[i, col] = prev[col]
        elif all(norm(prev[c]) == norm(row[c]) for c in content_cols):
            for col in REVIEW:
                new.at[i, col] = prev[col]
        else:
            new.at[i, "review_note"] = f"content changed since review ({prev['status']}); previous note: {prev['review_note']}"
    added = old[old["status"] == "added"].copy()
    return pd.concat([new, added], ignore_index=True)


def write_dictionary() -> None:
    """Column dictionary for both master files; fails if a column is undocumented."""
    assert [c for c, _, _ in REQ_DOCS] == COLUMNS, "REQ_DOCS out of sync with COLUMNS"
    assert [c for c, _, _ in TERMS_DOCS] == TERMS_COLUMNS, "TERMS_DOCS out of sync with TERMS_COLUMNS"
    rows = ([("tender_requirements.csv", *d) for d in REQ_DOCS] + [("tender_terms.csv", *d) for d in TERMS_DOCS]
            + [("tender_alvara_status.csv", *d) for d in STATUS_DOCS])
    pd.DataFrame(rows, columns=["file", "column", "meaning", "source"]).to_csv(DICTIONARY_CSV, index=False)
    fields = json.loads(PROMPT_FILE.read_text(encoding="utf-8"))["term_fields"]
    pd.DataFrame([(g, f, m) for g, fs in fields.items() for f, m in fs.items()],
                 columns=["group", "field", "meaning"]).to_csv(FIELDS_CSV, index=False)


def reviewed_counts(df: pd.DataFrame) -> pd.Series:
    return df[df["status"] != "unreviewed"].groupby("nAnuncio").size()


def main() -> None:
    rows, term_rows, statuses = load_extractions()
    translations = load_cache()
    req = merge_reviews(pd.DataFrame(rows, columns=COLUMNS), REQ_CSV, KEY, CONTENT).astype(str)
    req["quote_en"] = req["quote"].map(translations).fillna("")
    req["_c"], req["_s"] = pd.to_numeric(req["category"]), pd.to_numeric(req["subcategory"])
    req = req.sort_values(["nAnuncio", "lot", "_c", "_s"]).drop(columns=["_c", "_s"])
    req[COLUMNS].to_csv(REQ_CSV, index=False)

    terms = merge_reviews(pd.DataFrame(term_rows, columns=TERMS_COLUMNS), TERMS_CSV, TERMS_KEY, TERMS_CONTENT).astype(str)
    terms["quote_en"] = terms["quote"].map(translations).fillna("")
    terms = terms.sort_values(["nAnuncio", "lot", "group", "field"], kind="stable")
    terms[TERMS_COLUMNS].to_csv(TERMS_CSV, index=False)

    notice = pd.read_csv(PROJECT_ROOT / "eval" / "archive" / "alvara_prefill.csv", dtype=str, keep_default_na=False)
    notice["nAnuncio"] = notice["nAnuncio"].str.replace("/", "-")
    notice = notice.set_index("nAnuncio")["states_alvara"]
    status = pd.DataFrame(statuses)
    status["notice_states_alvara"] = status["nAnuncio"].map(notice).fillna("")
    status["notice_disagrees"] = status["states_alvara"] != status["notice_states_alvara"]
    status["n_reviewed"] = status["nAnuncio"].map(reviewed_counts(req)).fillna(0).astype(int)
    status["n_terms_reviewed"] = status["nAnuncio"].map(reviewed_counts(terms)).fillna(0).astype(int)
    status = status[[c for c, _, _ in STATUS_DOCS]]
    status.to_csv(STATUS_CSV, index=False)
    write_dictionary()
    print(f"{len(req)} requirements + {len(terms)} terms, {len(status)} tenders; "
          f"reviewed: {int(status['n_reviewed'].sum())} + {int(status['n_terms_reviewed'].sum())}")
    print(f"notice disagrees with peças in {int(status['notice_disagrees'].sum())} tenders")


if __name__ == "__main__":
    main()
