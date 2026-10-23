"""Pre-fill alvará annotations for the sampled notices (rule-based, no LLM).

Reads eval/alvara_sample.csv (never modified) and the notice texts in
data/raw/dre/<nAnuncio with "/" -> "-">/notice.txt, and writes eval/archive/alvara_prefill.csv.
Section numbers, field names, subcategory codes and the class table come from
DR_Tender_Documentation.md (the class table and codes are loaded from that file).

Notes on the rules:
- Subcategory lists like "1.ª, 2.ª e 5.ª subcategorias da 1.ª categoria" are expanded into codes.
- states_alvara is "no" when the notice says Não (class left empty), "yes" when it says Sim and
  a subcategory is found, otherwise "unclear" (section 12 text is then copied to notes).
- class is derived from base_price_doc (the overall base price); with lots, check each lot.

Run: python -m eval.alvara_prefill
"""

import re
from pathlib import Path

import pandas as pd

from extract.reference import REFERENCE, load_reference  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CSV = ROOT / "eval" / "alvara_sample.csv"
OUTPUT_CSV = ROOT / "eval" / "archive" / "alvara_prefill.csv"
TEXT_DIR = ROOT / "data" / "raw" / "dre"

SECTION_12_RE = re.compile(r"^\s*12\s*-\s*DOCUMENTOS DE HABILITAÇÃO.*?(?=^\s*13\s*-\s|\Z)", re.S | re.M)
PRICE_RE = re.compile(r"Preço base s/IVA:\s*([\d.\s]+(?:,\d+)?)\s*EUR", re.I)
LOTS_RE = re.compile(r"Procedimento com lotes\?\s*(Sim|Não)", re.I)
CPV_WORKS_RE = re.compile(r"Tipo de Contrato Principal:\s*Empreitada", re.I)
ALVARA_RE = re.compile(r"Habilitação para o exercício da atividade profissional:\s*(Sim|Não)", re.I)
TYPE_RE = re.compile(r"^\s*Tipo:\s*(.+)$", re.M)
# One or more "<n>.ª" numbers followed by "subcategoria(s) da <m>.ª categoria".
SUBCAT_RE = re.compile(
    r"((?:\d+\s*\.?\s*[ªa]\.?\s*(?:,|\be\b)?\s*)+)\s*subcategorias?\s+da\s+(\d+)\s*\.?\s*[ªa]\s*categoria",
    re.I,
)
NUMBER_RE = re.compile(r"(\d+)\s*\.?\s*[ªa]", re.I)
CLASS_STATED_RE = re.compile(r"\bclasse\s+(\d)\b", re.I)
RULE_TOTAL_RE = re.compile(r"valor\s+total\s+da\s+(?:sua\s+)?proposta|valor\s+global", re.I)
RULE_SPECIALISED_RE = re.compile(r"trabalhos\s+especializados", re.I)
ACCEPTED_DOCS = {
    "Alvará": re.compile(r"alvar[áa]", re.I),
    "Certificado de Empreiteiro": re.compile(r"certificado\s+de\s+empreiteiro", re.I),
    "declaração emitida pelo IMPIC": re.compile(r"declaração\s+emitida\s+pelo\s+IMPIC", re.I),
}
# Sentence boundary: ";" or "." not preceded by a digit/ª (so "1.ª" is not split).
SENTENCE_SPLIT_RE = re.compile(r"(?<![\dª])\.\s+|;\s+")

COLUMNS = [
    "nAnuncio", "price_band", "PrecoBase", "buyer", "description", "url",
    "base_price_doc", "has_lots", "lot_prices", "states_alvara", "doc_type", "accepted_docs",
    "category", "subcategory", "all_subcategories", "class_stated", "class_rule", "class",
    "class_source", "phrasing", "notes", "verified", "reviewer_notes",
]


def parse_pt_number(raw: str) -> float:
    return float(raw.replace(" ", "").replace(".", "").replace(",", "."))


def derive_class(price: float, class_table: list[tuple[int, float]]) -> int:
    for cls, max_value in class_table:
        if price <= max_value:
            return cls
    return class_table[-1][0]


def fmt(value: float) -> str:
    return f"{value:.2f}"


def extract(text: str, class_table: list[tuple[int, float]], valid_codes: set[str]) -> dict:
    out = {col: "" for col in COLUMNS[6:-2]}
    notes = []

    price_matches = PRICE_RE.findall(text)
    base_price = parse_pt_number(price_matches[0]) if price_matches else None
    if base_price is not None:
        out["base_price_doc"] = fmt(base_price)

    lots = LOTS_RE.search(text)
    if lots:
        out["has_lots"] = "yes" if lots.group(1).lower() == "sim" else "no"
    if out["has_lots"] == "yes":
        lots_part = text.split("Lotes:", 1)[1] if "Lotes:" in text else ""
        lot_prices = PRICE_RE.findall(lots_part) or price_matches[1:]
        out["lot_prices"] = ";".join(fmt(parse_pt_number(p)) for p in lot_prices)
        notes.append("per lot")

    section = SECTION_12_RE.search(text)
    section_text = section.group(0) if section else ""
    flat = re.sub(r"\s+", " ", section_text).strip()

    stated = ALVARA_RE.search(section_text)
    doc_type = TYPE_RE.search(section_text)
    if doc_type:
        out["doc_type"] = doc_type.group(1).strip()
    out["accepted_docs"] = ";".join(name for name, rx in ACCEPTED_DOCS.items() if rx.search(section_text))

    codes, sentences = [], []
    for sentence in SENTENCE_SPLIT_RE.split(flat):
        matches = list(SUBCAT_RE.finditer(sentence))
        found = [f"{m.group(2)}.{n}" for m in matches for n in NUMBER_RE.findall(m.group(1))]
        if found:
            sentences.append(sentence.strip())
        for code in found:
            if code not in codes:
                codes.append(code)
    if codes:
        first_cat, first_sub = codes[0].split(".")
        out["category"], out["subcategory"] = first_cat, first_sub
        out["all_subcategories"] = ";".join(codes)
        unknown = [c for c in codes if c not in valid_codes]
        if unknown:
            notes.append("unknown subcategory codes: " + ";".join(unknown))

    class_sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(flat)
                       if re.search(r"\bclasse", s, re.I) and s.strip() not in sentences]
    out["phrasing"] = " | ".join(sentences + class_sentences)

    stated_class = CLASS_STATED_RE.search(section_text)
    if stated_class:
        out["class_stated"] = stated_class.group(1)
    rules = []
    if RULE_TOTAL_RE.search(section_text):
        rules.append("total")
    if RULE_SPECIALISED_RE.search(section_text):
        rules.append("specialised")
    out["class_rule"] = ";".join(rules)

    if out["class_stated"]:
        out["class"], out["class_source"] = out["class_stated"], "stated"
    elif base_price is not None:
        out["class"], out["class_source"] = str(derive_class(base_price, class_table)), "derived"

    flag = stated.group(1).lower() if stated else None
    if flag == "não":
        out["states_alvara"] = "no"
        out["class"] = out["class_source"] = ""
        if CPV_WORKS_RE.search(text):
            notes.append("works contract but notice requires no alvará")
    elif flag == "sim" and codes:
        out["states_alvara"] = "yes"
    else:
        out["states_alvara"] = "unclear"
        notes.append(flat[:300] if section else "section 12 not found")

    out["notes"] = " | ".join(notes)
    return out


def main() -> None:
    class_table, valid_codes = load_reference()
    sample = pd.read_csv(SAMPLE_CSV, dtype=str, keep_default_na=False)

    rows = []
    for rec in sample.itertuples():
        row = {
            "nAnuncio": rec.nAnuncio, "price_band": rec.price_band, "PrecoBase": rec.PrecoBase,
            "buyer": rec.designacaoEntidade, "description": rec.descricaoAnuncio, "url": rec.url,
        }
        path = TEXT_DIR / rec.nAnuncio.replace('/', '-') / "notice.txt"
        if path.exists():
            row.update(extract(path.read_text(encoding="utf-8"), class_table, valid_codes))
        else:
            row.update({"states_alvara": "unclear", "notes": f"text file not found: {path.name}"})
        rows.append(row)

    result = pd.DataFrame(rows).reindex(columns=COLUMNS).fillna("")
    result.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")

    states = result["states_alvara"].value_counts()
    print(f"Notices processed: {len(result)}")
    print("states_alvara: " + ", ".join(f"{k}={int(states.get(k, 0))}" for k in ("yes", "no", "unclear")))
    print(f"Notices with at least one subcategory: {int((result['all_subcategories'] != '').sum())}")
    print(f"Notices with lots: {int((result['has_lots'] == 'yes').sum())}")
    print(f"Class stated: {int((result['class_source'] == 'stated').sum())} | "
          f"derived: {int((result['class_source'] == 'derived').sum())}")
    print(f"Saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
