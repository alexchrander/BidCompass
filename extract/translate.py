"""Translate the Portuguese text in the master tables to English, for the reviewer only.

Collects every distinct quote, detail and free-text value in tender_requirements.csv / tender_terms.csv,
translates what is not yet cached with Gemini, and stores it in data/processed/extraction/translations.csv
(columns: pt, en). extract.build_requirements adds the English quote as `quote_en`; the review script
shows the English for detail and value too. The Portuguese text stays the source of truth.

Run: python -m extract.translate
"""
from __future__ import annotations

import json
import os
import re

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

from extract.build_requirements import CACHE, PROMPT_FILE, REQ_CSV, TERMS_CSV, load_cache
from ingest.common import PROJECT_ROOT

BATCH = 40
SCHEMA = {"type": "array", "items": {"type": "object", "properties": {
    "id": {"type": "integer"}, "en": {"type": "string"}}, "required": ["id", "en"]}}
INSTRUCTION = ("Translate each Portuguese (Portugal) excerpt from a public construction tender into plain English. "
               "Be literal and faithful: keep numbers, dates, percentages, article numbers and legal references "
               "unchanged, and do not add explanations. Keep terms of art recognisable, e.g. 'alvará' becomes "
               "'construction licence (alvará)', 'caução' becomes 'guarantee (caução)'. "
               "Return one entry per input with the same id.")


def needs_translation(text: str) -> bool:
    return bool(re.search(r"[A-Za-zÀ-ÿ]{3,}", text)) and text.lower() not in {"yes", "no", "pt", "true", "false"}


def collect() -> list[str]:
    texts = set()
    for path, columns in ((REQ_CSV, ["quote"]), (TERMS_CSV, ["quote", "detail", "value"])):
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        for col in columns:
            texts.update(t for t in df[col].unique() if t and needs_translation(t))
    return sorted(texts)


def translate_batch(client: genai.Client, model: str, texts: list[str]) -> dict[str, str]:
    payload = json.dumps([{"id": i, "pt": t} for i, t in enumerate(texts)], ensure_ascii=False)
    resp = client.models.generate_content(
        model=model, contents=payload,
        config=types.GenerateContentConfig(system_instruction=INSTRUCTION, response_mime_type="application/json",
                                           response_schema=SCHEMA, temperature=0))
    by_id = {r["id"]: r["en"] for r in json.loads(resp.text)}
    return {t: by_id[i] for i, t in enumerate(texts) if i in by_id}


def main() -> None:
    cache = load_cache()
    todo = [t for t in collect() if t not in cache]
    print(f"{len(cache)} cached, {len(todo)} to translate")
    if not todo:
        return
    load_dotenv(PROJECT_ROOT / ".env")
    key = os.getenv("GEMINI_API_KEY") or os.getenv("gemini_api_key")
    if not key:
        raise SystemExit("No Gemini key found in .env (gemini_api_key)")
    client = genai.Client(api_key=key)
    model = json.loads(PROMPT_FILE.read_text(encoding="utf-8"))["model"]
    for start in range(0, len(todo), BATCH):
        cache.update(translate_batch(client, model, todo[start:start + BATCH]))
        pd.DataFrame(sorted(cache.items()), columns=["pt", "en"]).to_csv(CACHE, index=False)
        print(f"  translated {min(start + BATCH, len(todo))}/{len(todo)}")
    missing = [t for t in todo if t not in cache]
    print(f"done, {len(missing)} missing (re-run to retry)")


if __name__ == "__main__":
    main()
