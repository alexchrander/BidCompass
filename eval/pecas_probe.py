"""Pilot: run the notice regexes on the peças (Processo Concurso) text and compare with the notice result.

Run: python -m eval.pecas_probe
"""

import re

import pandas as pd

from eval.alvara_prefill import (
    NUMBER_RE, ROOT, SENTENCE_SPLIT_RE, SUBCAT_RE, TEXT_DIR, load_reference,
)

_, VALID = load_reference()
CATEGORY_WORDS = {"primeira": 1, "segunda": 2, "terceira": 3, "quarta": 4, "quinta": 5}


def probe(folder) -> dict:
    codes, evidence = [], []
    for path in sorted((folder / "pecas" / "text").rglob("*.txt")):
        flat = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
        # "quinta categoria" etc. -> digits so the same pattern applies
        for word, num in CATEGORY_WORDS.items():
            flat = re.sub(rf"\b{word}\s+categoria", f"{num}ª categoria", flat, flags=re.I)
        for sentence in SENTENCE_SPLIT_RE.split(flat):
            found = [f"{m.group(2)}.{n}" for m in SUBCAT_RE.finditer(sentence) for n in NUMBER_RE.findall(m.group(1))]
            if found:
                evidence.append(f"[{path.name[:25]}] {sentence.strip()[:200]}")
                codes += [c for c in found if c not in codes]
    return {"codes": codes, "unknown": [c for c in codes if c not in VALID], "evidence": evidence}


def main() -> None:
    prefill = pd.read_csv(ROOT / "eval" / "archive" / "alvara_prefill.csv", dtype=str, keep_default_na=False)
    for rec in prefill.itertuples():
        folder = TEXT_DIR / rec.nAnuncio.replace("/", "-")
        if not (folder / "pecas" / "files").exists():
            continue
        res = probe(folder)
        print(f"== {rec.nAnuncio} | notice: {rec.states_alvara} {rec.all_subcategories or '-'} | peças: {';'.join(res['codes']) or '-'}"
              + (f" | unknown: {res['unknown']}" if res["unknown"] else ""))
        for line in res["evidence"][:6]:
            print("   ", line)


if __name__ == "__main__":
    main()
