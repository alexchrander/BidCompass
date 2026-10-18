"""Offline test of the IMPIC parsers using saved responses (no network)."""

from ingest.impic import IMPIC_DIR, parse_detail, parse_search


def test_parse_search():
    hits = parse_search((IMPIC_DIR / "503451541_search.html").read_text(encoding="utf-8"))
    assert len(hits) == 1
    assert hits[0]["licence_id"] == "23919"
    assert hits[0]["nif"] == "503451541"


def test_parse_detail():
    detail = parse_detail((IMPIC_DIR / "23919_detail.html").read_text(encoding="utf-8"))
    assert detail["max_class"] == 7
    assert len(detail["qualifications"]) == 41
    first = detail["qualifications"][0]
    assert (first["category"], first["subcategory"], first["class"]) == (1, 1, 7)
