"""Measurement sample: do construction tender notices state the required alvará?

Samples 2026 construction procedures from data/processed/tenders.parquet, downloads the notice PDF
from the `url` column, extracts the text and prints passages around alvará-related keywords.
Annotation columns in eval/alvara_sample.csv are meant to be filled in by hand.

Run: python -m eval.alvara_sample
"""

import re
import time
from pathlib import Path

import pymupdf  # PyMuPDF (fitz)
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
TENDERS = ROOT / "data" / "processed" / "tenders.parquet"
SAMPLE_CSV = ROOT / "eval" / "alvara_sample.csv"
PDF_DIR = ROOT / "data" / "raw" / "dre"
KEYWORDS = ["alvará", "habilitação", "habilitações", "categoria", "subcategoria", "classe",
            "certificado de empreiteiro", "IMPIC"]
KEYWORD_RE = re.compile("|".join(re.escape(k) for k in KEYWORDS), re.IGNORECASE)
CONTEXT = 300
ANNOTATION_COLS = ["states_alvara", "category", "subcategory", "class", "phrasing", "notes"]


def build_sample() -> pd.DataFrame:
    df = pd.read_parquet(TENDERS)
    df = df[df["is_construction"] & df["is_procedure"] & (df["Ano"] == 2026) & df["PrecoBase"].notna()]
    price = df["PrecoBase"]
    strata = [(price <= 200_000, 12), ((price > 200_000) & (price <= 400_000), 12),
              ((price > 400_000) & (price <= 1_000_000), 6)]
    parts = [df[mask].sample(n=n, random_state=42) for mask, n in strata]
    sample = pd.concat(parts).reset_index(drop=True)
    sample = sample[["nAnuncio", "price_band", "PrecoBase", "designacaoEntidade", "descricaoAnuncio", "url"]]
    for col in ANNOTATION_COLS:
        sample[col] = ""
    return sample


def file_stem(n_anuncio: str) -> str:
    return n_anuncio.replace("/", "-")


def download(url: str, path: Path) -> bool:
    if path.exists():
        return True
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}")
        if not resp.content.startswith(b"%PDF"):
            raise RuntimeError("response is not a PDF")
        path.write_bytes(resp.content)
        return True
    except Exception as exc:
        print(f"DOWNLOAD FAILED {url}: {exc}")
        return False
    finally:
        time.sleep(1)


def extract_text(pdf_path: Path) -> str:
    txt_path = pdf_path.with_suffix(".txt")
    with pymupdf.open(pdf_path) as doc:
        text = "\n".join(page.get_text() for page in doc)
    txt_path.write_text(text, encoding="utf-8")
    return text


def find_snippets(text: str) -> tuple[int, list[str]]:
    spans = [(max(0, m.start() - CONTEXT), min(len(text), m.end() + CONTEXT))
             for m in KEYWORD_RE.finditer(text)]
    merged: list[list[int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return len(spans), [text[s:e].strip() for s, e in merged]


def main() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    sample = build_sample()
    sample.to_csv(SAMPLE_CSV, index=False)

    downloaded = with_matches = no_matches = 0
    for row in sample.itertuples():
        pdf_path = PDF_DIR / f"{file_stem(row.nAnuncio)}.pdf"
        if not download(row.url, pdf_path):
            continue
        downloaded += 1
        try:
            text = extract_text(pdf_path)
        except Exception as exc:
            print(f"EXTRACT FAILED {pdf_path.name}: {exc}")
            continue
        count, snippets = find_snippets(text)
        print("====")
        print(f"{row.nAnuncio} | {row.price_band} | {row.PrecoBase:,.2f} | {row.designacaoEntidade}")
        print(row.descricaoAnuncio[:100])
        print(row.url)
        print(f"keyword matches: {count}")
        if snippets:
            with_matches += 1
            print("\n---\n".join(snippets))
        else:
            no_matches += 1
            print("NO ALVARÁ KEYWORDS FOUND")

    print("\n==== SUMMARY")
    print(f"tenders sampled: {len(sample)}")
    print(f"PDFs downloaded: {downloaded}")
    print(f"PDFs with at least one keyword match: {with_matches}")
    print(f"PDFs with no matches: {no_matches}")


if __name__ == "__main__":
    main()
