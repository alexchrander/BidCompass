"""Reference data from DR_Tender_Documentation.md: IMPIC class table and valid subcategory codes."""

import re
from pathlib import Path

REFERENCE = Path(__file__).resolve().parent.parent / "DR_Tender_Documentation.md"


def load_reference() -> tuple[list[tuple[int, float]], set[str]]:
    """Class table [(class, max_value)] and valid subcategory codes from the reference file."""
    text = REFERENCE.read_text(encoding="utf-8")
    classes = []
    for num, value in re.findall(r"^\|\s*(\d)\s*\|\s*([\d,]+)\s*\|", text, re.M):
        classes.append((int(num), float(value.replace(",", ""))))
    above = re.search(r"^\|\s*(\d)\s*\|\s*Above", text, re.M | re.I)
    if above:
        classes.append((int(above.group(1)), float("inf")))
    codes = set(re.findall(r"^\|\s*(\d+\.\d+)\s*\|", text, re.M))
    if not classes or not codes:
        raise ValueError(f"Could not load class table or subcategory codes from {REFERENCE}")
    return sorted(classes), codes
