"""Extract everything a bidder needs to know from the peças with Gemini (one call per tender).

Extracts the alvará requirements (per lot and subcategory) and the other tender terms (price, deadlines,
guarantees, award criteria, technical and financial capacity, eligibility). The prompt, model, field
list and response schema live in extract/pecas_prompt.json (edit there, not here).
For each tender: picks the programa/caderno-like text files from data/raw/dre/<id>/pecas/text,
sends them in one request and saves the answer to data/raw/dre/<id>/pecas/alvara_llm.json.
Build the master tables from these files with: python -m extract.build_requirements

Run: python -m extract.pecas_llm                 (all tenders that have peças text)
     python -m extract.pecas_llm 8844-2026 ...   (specific folders; --force to re-run)
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from ingest.common import PROJECT_ROOT, RAW_DIR

DRE_DIR = RAW_DIR / "dre"
PROMPT = json.loads((Path(__file__).parent / "pecas_prompt.json").read_text(encoding="utf-8"))
TERM_FIELDS: dict[str, dict[str, str]] = PROMPT["term_fields"]


def build_task_and_schema() -> tuple[str, dict]:
    """Append the term field list to the task text and restrict the schema's group/field to it."""
    lines = [f"- {group}: {field} = {meaning}" for group, fields in TERM_FIELDS.items() for field, meaning in fields.items()]
    task = f"{PROMPT['task']}\n\n{PROMPT['terms_task']}\nFields:\n" + "\n".join(lines)
    schema = json.loads(json.dumps(PROMPT["response_schema"]))
    item = schema["properties"]["terms"]["items"]["properties"]
    item["group"]["enum"] = list(TERM_FIELDS)
    item["field"]["enum"] = [f for fields in TERM_FIELDS.values() for f in fields]
    return task, schema


def collect_text(folder: Path) -> str:
    text_dir = folder / "pecas" / "text"
    files = sorted(text_dir.rglob("*.txt"))
    keywords = PROMPT["file_name_keywords"]
    # Numeric names (e.g. 419966862.txt) are the DRE notice copy bundled in the peças; always include them.
    chosen = [f for f in files if f.stem.isdigit() or any(k in f.name.lower() for k in keywords)] or files
    limit = PROMPT["max_chars_per_file"]
    parts = []
    for f in chosen:
        body = f.read_text(encoding="utf-8")[:limit]
        parts.append(f"=== FILE: {f.relative_to(text_dir)} ===\n{body}")
    return "\n\n".join(parts)


def run_one(client: genai.Client, folder: Path, force: bool) -> dict | None:
    out = folder / "pecas" / "alvara_llm.json"
    if out.exists() and not force:
        return json.loads(out.read_text(encoding="utf-8"))
    text = collect_text(folder)
    if not text.strip():
        return None
    task, schema = build_task_and_schema()
    resp = client.models.generate_content(
        model=PROMPT["model"],
        contents=f"{task}\n\n{text}",
        config=types.GenerateContentConfig(
            system_instruction=PROMPT["system_instruction"],
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0,
        ),
    )
    result = json.loads(resp.text)
    result["_meta"] = {"model_requested": PROMPT["model"], "model_served": getattr(resp, "model_version", None), "prompt_version": PROMPT["version"], "chars_sent": len(text)}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("folders", nargs="*")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    key = os.getenv("GEMINI_API_KEY") or os.getenv("gemini_api_key")
    if not key:
        raise SystemExit("No Gemini key found in .env (gemini_api_key)")
    client = genai.Client(api_key=key)

    names = args.folders or sorted(p.parent.parent.name for p in DRE_DIR.glob("*/pecas/text"))
    for name in names:
        try:
            result = run_one(client, DRE_DIR / name, args.force)
        except Exception as exc:
            print(f"{name:>11}  ERROR {type(exc).__name__}: {str(exc)[:150]}")
            continue
        if result is None:
            print(f"{name:>11}  no text")
            continue
        codes = [f"{r['category']}.{r['subcategory']}" for lot in result["lots"] for r in lot["requirements"]]
        print(f"{name:>11}  {result['states_alvara']:<8} alvará: {';'.join(dict.fromkeys(codes)) or '-'} | terms: {len(result.get('terms', []))}")


if __name__ == "__main__":
    main()
