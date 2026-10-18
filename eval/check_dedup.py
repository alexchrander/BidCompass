"""Check duplicate nAnuncio values in the raw 2025 and 2026 announcements (before dedup).

Run: python -m eval.check_dedup
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "base"
YEARS = (2025, 2026)
PROCEDURE = "Anúncio de procedimento"


def load_groups() -> dict[str, list[tuple[int, dict]]]:
    """Return nAnuncio -> [(file_year, record), ...] for all records."""
    groups = defaultdict(list)
    for year in YEARS:
        path = RAW_DIR / f"anuncios_{year}" / f"anuncios{year}.json"
        for record in json.loads(path.read_text(encoding="utf-8")):
            groups[str(record["nAnuncio"]).strip()].append((year, record))
    return groups


def main() -> None:
    groups = {key: rows for key, rows in load_groups().items() if len(rows) > 1}
    mixed = identical = both_years = 0

    for key in sorted(groups):
        rows = groups[key]
        print(f"\n{key} ({len(rows)} rows)")
        for file_year, r in rows:
            print(
                f"  file={file_year} Ano={r.get('Ano')} | {r.get('dataPublicacao')} | {r.get('tipoActo')} | "
                f"{r.get('designacaoEntidade')} | {str(r.get('descricaoAnuncio'))[:60]} | {r.get('url')}"
            )
        types = {r.get("tipoActo") for _, r in rows}
        mixed += PROCEDURE in types and len(types) > 1
        identical += len({json.dumps(r, sort_keys=True) for _, r in rows}) == 1
        both_years += len({file_year for file_year, _ in rows}) > 1

    print("\nSummary")
    print(f"  duplicate groups: {len(groups)}")
    print(f"  groups mixing '{PROCEDURE}' with another tipoActo: {mixed}")
    print(f"  groups with identical rows (all fields): {identical}")
    print(f"  groups spanning both years (files): {both_years}")


if __name__ == "__main__":
    main()
