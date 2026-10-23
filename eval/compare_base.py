"""Cross-check LLM-extracted values against the BASE announcement data.

Compared: base price, bid deadline (date, or number of days when the peças state days), and lots
(count and, where BASE names them, whether the LLM found the same number).

Reads data/processed/extraction/tender_terms.csv and data/processed/tenders/tenders.parquet.
Prints one line per tender and writes data/processed/eval/base_comparison.csv.
A mismatch is not automatically an LLM error: a rectification may have changed the value in the peças.

Usage: python -m eval.compare_base
"""
import pandas as pd

from extract.build_requirements import EXTRACTION_DIR
from ingest.common import PROCESSED_DIR

OUT = PROCESSED_DIR / "eval" / "base_comparison.csv"
PRICE_TOLERANCE = 0.005


def llm_price(terms: pd.DataFrame) -> float | None:
    rows = terms[terms["field"] == "base_price_excl_vat"]
    total = rows[rows["lot"] == ""]
    if len(total):
        rows = total
    values = pd.to_numeric(rows["value"], errors="coerce").dropna()
    if values.empty:
        return None
    # Without a procedure-level total, the lot prices add up to it.
    return float(values.sum())


def llm_deadline(terms: pd.DataFrame) -> tuple[str, str]:
    rows = terms[terms["field"] == "proposal_deadline"]
    return (str(rows["value"].iloc[0]), str(rows["unit"].iloc[0])) if len(rows) else ("", "")


def llm_lots(terms: pd.DataFrame) -> int:
    return terms.loc[terms["lot"] != "", "lot"].nunique()


def compare_lots(base_lots, llm: int) -> str:
    base = 0 if base_lots is None else len(base_lots)
    return "match" if base == llm else "MISMATCH"


def compare_price(base: float, llm: float | None) -> str:
    if llm is None or pd.isna(base):
        return "missing"
    return "match" if abs(base - llm) <= PRICE_TOLERANCE * max(base, 1) else "MISMATCH"


def compare_deadline(base_date, base_days, llm: str, unit: str) -> str:
    if not llm:
        return "missing"
    if unit == "days":
        return "match" if pd.notna(base_days) and str(int(base_days)) == llm else "MISMATCH"
    parsed = pd.to_datetime(llm, errors="coerce")
    if pd.isna(parsed):
        return "not a date"
    if pd.isna(base_date):
        return "missing"
    return "match" if parsed.normalize() == base_date.normalize() else "MISMATCH"


def main() -> None:
    terms = pd.read_csv(EXTRACTION_DIR / "tender_terms.csv", dtype=str).fillna("")
    terms = terms[terms["status"] != "rejected"]
    base = pd.read_parquet(PROCESSED_DIR / "tenders" / "tenders.parquet")
    base["tender_id"] = base["nAnuncio"].str.replace("/", "-", regex=False)
    base = base.sort_values("dataPublicacao").drop_duplicates("tender_id", keep="last").set_index("tender_id")

    rows = []
    for tender, group in terms.groupby("nAnuncio"):
        b = base.loc[tender] if tender in base.index else None
        if b is None:
            rows.append({"nAnuncio": tender, "price_result": "not in BASE"})
            continue
        price = llm_price(group)
        deadline, unit = llm_deadline(group)
        lots = llm_lots(group)
        rows.append({
            "nAnuncio": tender,
            "base_price": b["PrecoBase"],
            "llm_price": price,
            "price_result": compare_price(b["PrecoBase"], price),
            "base_deadline": b["DataLimitePropostas"].date() if pd.notna(b["DataLimitePropostas"]) else "",
            "llm_deadline": deadline,
            "base_deadline_days": b["PrazoPropostas"],
            "llm_deadline_unit": unit,
            "deadline_result": compare_deadline(b["DataLimitePropostas"], b["PrazoPropostas"], deadline, unit),
            "base_lots": 0 if b["Lotes"] is None else len(b["Lotes"]),
            "llm_lots": lots,
            "lots_result": compare_lots(b["Lotes"], lots),
            "has_amendment": b["has_amendment"],
        })

    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(out.to_string(index=False))
    print(f"\nprice:    {out['price_result'].value_counts().to_dict()}")
    print(f"deadline: {out['deadline_result'].value_counts().to_dict()}")
    print(f"lots:     {out['lots_result'].value_counts().to_dict()}")
    print(f"written to {OUT}")


if __name__ == "__main__":
    main()
