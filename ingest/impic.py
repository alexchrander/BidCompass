"""IMPIC (Instituto dos Mercados Públicos, do Imobiliário e da Construção) alvará lookup.

Source: IMPIC's public register of firms holding a public-works contractor licence
(alvará de empreiteiro de obras públicas). For a firm's NIF it gives the licence number,
the firm name and its qualifications: category, subcategory and class.

This is NOT an official API. The page loads its data from one internal AJAX endpoint,
which may change or break without notice. Raw responses are cached in data/raw/impic/.

TODO: check IMPIC's terms of use before any bulk use of this lookup.

Run: python -m ingest.impic [nif ...]   (default: two test NIFs)
"""

from __future__ import annotations

import csv
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PAGE_URL = "https://www.impic.pt/impic/pt-pt/consultar/empresas-titulares-de-alvara-de-empreiteiro-de-obras-publicas"
ENDPOINT_URL = "https://www.impic.pt/impic/ajax/call/impic_api/consultar/ajax/43"
BASE_FORM = {"id_type": "8", "id_object": "17"}  # 17 = public works alvarás register (assumed)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMPIC_DIR = PROJECT_ROOT / "data" / "raw" / "impic"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "impic"
LICENCES_CSV = IMPIC_DIR / "licences.csv"

TIMEOUT = 30
DELAY_SECONDS = 1
_last_request = 0.0


def _wait() -> None:
    """Sleep so that consecutive requests are at least DELAY_SECONDS apart."""
    global _last_request
    remaining = DELAY_SECONDS - (time.monotonic() - _last_request)
    if remaining > 0:
        time.sleep(remaining)
    _last_request = time.monotonic()


def _check(response: requests.Response) -> requests.Response:
    if response.status_code != 200:
        raise RuntimeError(f"IMPIC returned HTTP {response.status_code} for {response.request.method} {response.url}")
    return response


def new_session() -> requests.Session:
    """Create a session and GET the page once so it receives its PHPSESSID cookie."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "BidCompass research",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": PAGE_URL,
        }
    )
    _wait()
    _check(session.get(PAGE_URL, timeout=TIMEOUT))
    return session


def _cached_post(session: requests.Session, cache_file: Path, form: dict[str, str]) -> str:
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    _wait()
    response = _check(session.post(ENDPOINT_URL, data={**BASE_FORM, **form}, timeout=TIMEOUT))
    IMPIC_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(response.text, encoding="utf-8")
    return response.text


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(value).strip())


def search_nif(session: requests.Session, nif: str) -> str:
    """Return the raw search response for a NIF (cached as <nif>_search.html)."""
    form = {"pesquisar": "true", "loadTable": "1", "pageSearch": "1", "nif_npic": str(nif)}
    return _cached_post(session, IMPIC_DIR / f"{_safe(nif)}_search.html", form)


def licence_detail(session: requests.Session, licence: str) -> str:
    """Return the raw detail response for a licence number (cached as <licence>_detail.html)."""
    form = {"informacao": "true", "info": "NUMERO_LICENCA", "value": str(licence), "nl": str(licence)}
    return _cached_post(session, IMPIC_DIR / f"{_safe(licence)}_detail.html", form)


def parse_search(html: str) -> list[dict]:
    """Parse the search response into [{"licence", "licence_id", "nif", "name"}, ...]."""
    soup = BeautifulSoup(html, "html.parser")
    hits = []
    for row in soup.select("tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        link = cells[0].find("a")
        hits.append(
            {
                "licence": cells[0].get_text(" ", strip=True),
                "licence_id": link.get("data-nl") if link else None,
                "nif": cells[1].get_text(" ", strip=True),
                "name": cells[2].get_text(" ", strip=True),
            }
        )
    return hits


CATEGORY_RE = re.compile(r"(\d+)\.?\s*ª\s*Categoria\s*-\s*(.+)")
SUBCATEGORY_RE = re.compile(r"(\d+)\.\s*ª\s*-\s*(.+)")


def parse_detail(html: str) -> dict:
    """Parse the licence detail response into header fields plus a list of qualifications."""
    soup = BeautifulSoup(html, "html.parser")
    fields = {}
    for field in soup.select(".information-field"):
        label, value = field.find("label"), field.find("span")
        if label and value:
            fields[label.get_text(strip=True)] = value.get_text(" ", strip=True)

    qualifications = []
    category = category_name = None
    for row in soup.select(".others tbody tr"):
        cells = row.find_all("td")
        if len(cells) == 1:
            match = CATEGORY_RE.match(cells[0].get_text(" ", strip=True))
            if match:
                category, category_name = int(match.group(1)), match.group(2).strip()
        elif len(cells) == 2:
            match = SUBCATEGORY_RE.match(cells[0].get_text(" ", strip=True))
            class_text = cells[1].get_text(strip=True)
            if match and class_text.isdigit():
                qualifications.append(
                    {
                        "category": category,
                        "category_name": category_name,
                        "subcategory": int(match.group(1)),
                        "subcategory_name": match.group(2).strip(),
                        "class": int(class_text),
                    }
                )

    max_class = fields.get("Classe Máxima", "")
    return {
        "licence": fields.get("Alvará"),
        "nif": fields.get("NIF/NIPC"),
        "name": fields.get("Denominação"),
        "max_class": int(max_class) if max_class.isdigit() else None,
        "registered": fields.get("Data de inscrição"),
        "municipality": fields.get("Concelho"),
        "district": fields.get("Distrito"),
        "qualifications": qualifications,
    }


def _from_csv(nif: str) -> dict | None:
    """Fallback: build the result from the manual CSV (nif, category, subcategory, class)."""
    if not LICENCES_CSV.exists():
        return None
    with LICENCES_CSV.open(encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["nif"].strip() == str(nif).strip()]
    if not rows:
        return None
    qualifications = [
        {"category": r["category"], "subcategory": r["subcategory"], "class": r["class"]} for r in rows
    ]
    return {"nif": str(nif), "licence": None, "name": None, "qualifications": qualifications}


def get_licence(nif: str) -> dict | None:
    """Return the parsed licence for a NIF, or None if IMPIC has no public-works licence for it.

    If the IMPIC lookup fails (network, HTTP error), falls back to data/raw/impic/licences.csv.
    """
    try:
        session = new_session()
        hits = parse_search(search_nif(session, nif))
        if not hits:
            return None  # TODO: also check the certificate register later
        result = parse_detail(licence_detail(session, hits[0]["licence_id"]))
    except (requests.RequestException, RuntimeError) as error:
        print(f"IMPIC lookup unavailable ({error}); using {LICENCES_CSV}")
        return _from_csv(nif)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    (PROCESSED_DIR / f"{_safe(nif)}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    for test_nif in sys.argv[1:] or ("503451541", "506805450"):
        licence = get_licence(test_nif)
        if licence is None:
            print(test_nif, "no licence found")
            continue
        print(test_nif, licence["name"], "max class", licence["max_class"], "-", len(licence["qualifications"]), "qualifications")
        for q in licence["qualifications"][:3]:
            print("  ", q)
